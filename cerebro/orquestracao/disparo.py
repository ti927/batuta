"""Disparo de uma automação — onde uma execução nasce e como ela roda.

Todos os gatilhos (botão manual, agendamento/CRON, webhook) **enfileiram**: criam
a execução no estado `aguardando` (`criar_execucao`) e devolvem na hora. Quem de
fato roda a cadeia é o pool de trabalhadores da fila (`fila.py`), que chama
`rodar_execucao`. Assim muitas execuções simultâneas são organizadas sem travar
(PRODUTO §18, Tarefa 5.3).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

import medicao_instrumentos
from chaves import resolver_chaves_por_time
from modelos import Automacao, Execucao, PassoExecucao, Time
from observabilidade import contexto
from observabilidade.escritor import registrar_evento
from orquestracao import atividade
from orquestracao.cadeia import executar_cadeia
from orquestracao.llm import usar_chaves
from orquestracao.modelos_ia import provedor_do_modelo_seguro
from sessao import CriadorDeSessao


def _org_do_time(sessao: Session, time_id: uuid.UUID | None) -> uuid.UUID | None:
    """A organização de um time (para carimbar os eventos com a partição por cliente)."""
    if time_id is None:
        return None
    time = sessao.get(Time, time_id)
    return time.organizacao_id if time else None


def _fazer_registrador(
    sessao: Session,
    execucao_id: uuid.UUID,
    origens: dict[str, str] | None = None,
    categoria: str = "execucao",
):
    """Callback que grava cada passo da cadeia em `passos_execucao`. `origens`
    (Fases 7.6/7-A) mapeia provedor → origem da chave; cada entrada de `uso` é
    carimbada com a origem do PROVEDOR do seu modelo, registrando de qual chave
    (cliente/consultoria/legado) saiu o consumo — por provedor, já que agentes
    da mesma cadeia podem usar provedores diferentes. `categoria` carimba em que
    FUNÇÃO a IA foi gasta (execução de agentes); o roteamento de bifurcação entra
    no mesmo passo, então fica contabilizado como execução. Carimbar aqui, na
    borda, não toca o núcleo congelado de orquestração."""

    def registrar(passo: dict, ordem: int) -> None:
        uso = passo.get("uso") or []
        for e in uso:
            e.setdefault("categoria", categoria)
            if origens:
                provedor = provedor_do_modelo_seguro(e.get("modelo") or "")
                origem = origens.get(provedor) if provedor else None
                if origem:
                    e.setdefault("origem", origem)
        # Instrumentos com IA paga (ex.: gerar_imagem) acionados neste passo: o
        # custo é contabilizado na borda (categoria 'instrumento'), sem tocar o
        # núcleo nem o contrato do instrumento.
        uso = uso + medicao_instrumentos.uso_de_instrumentos_pagos(
            sessao,
            passo.get("agente_id"),
            passo.get("instrumentos_acionados"),
            origens=origens,
        )
        sessao.add(
            PassoExecucao(
                execucao_id=execucao_id,
                ordem=ordem,
                no_id=passo.get("no_id"),
                tipo=passo.get("tipo"),  # Fatia 4.1: classificação do passo na timeline

                # agente_id pode ser nulo num nó roteador (que não roda agente).
                agente_id=(
                    uuid.UUID(passo["agente_id"]) if passo.get("agente_id") else None
                ),
                entrada={"texto": passo["entrada"]},
                saida={
                    "texto": passo["saida"],
                    "instrumentos_acionados": passo["instrumentos_acionados"],
                    "saida_escolhida": passo["saida_escolhida"],
                    "uso": uso,
                    # Só quando houve falha de instrumento — mantém o passo comum
                    # idêntico ao de antes (o diagnóstico lê com `.get(...) or []`).
                    **(
                        {"erros_instrumentos": passo["erros_instrumentos"]}
                        if passo.get("erros_instrumentos")
                        else {}
                    ),
                    # Fan-out (2026-08-31): TODOS os caminhos seguidos, o porquê que o
                    # agente declarou e o aviso quando o ramo morreu sem caminho. Aditivos
                    # — passos antigos não os têm e a tela lê com `.get(...)`.
                    **(
                        {"saidas_escolhidas": passo["saidas_escolhidas"]}
                        if passo.get("saidas_escolhidas")
                        else {}
                    ),
                    **({"motivo_ramo": passo["motivo_ramo"]} if passo.get("motivo_ramo") else {}),
                    **({"aviso": passo["aviso"]} if passo.get("aviso") else {}),
                    **({"erro": passo["erro"]} if passo.get("erro") else {}),
                    # Por onde o agente pediu aprovação neste passo (canal + de quem
                    # se espera a resposta). É o que amarra a conversa de quem aprova
                    # a esta execução — antes essa config vivia no NÓ do desenho.
                    **({"aprovacao": passo["aprovacao"]} if passo.get("aprovacao") else {}),
                },
                # O passo que FALHOU fica gravado como falho (antes tudo era gravado
                # "concluido" e a timeline pulava do último passo bom para "falhou",
                # sem dizer em qual nó).
                estado=passo.get("estado") or "concluido",
                iniciado_em=passo["iniciado_em"],
                finalizado_em=passo["finalizado_em"],
            )
        )
        sessao.commit()

    return registrar


def _aplicar_resultado(execucao: Execucao, r: dict) -> None:
    """Aplica à execução o que a cadeia devolveu: pausa, cancelamento ou
    conclusão."""
    if r["estado"] == "aguardando_humano":
        execucao.estado = "aguardando_humano"  # sem finalizada_em: ainda viva
        # Fan-out: os ramos da onda que ainda não rodaram quando o portão pausou. Sem
        # guardá-los, a retomada seguiria só o caminho do portão e o trabalho dos
        # outros ramos sumiria em silêncio.
        execucao.pendencias = r.get("pendentes") or None
    elif r["estado"] == "cancelada":
        execucao.estado = "cancelada"
        if not execucao.resultado:
            execucao.resultado = {"texto": "Cancelada pelo operador."}
        execucao.finalizada_em = datetime.now(timezone.utc)
        execucao.pendencias = None
    else:
        execucao.estado = "concluida"
        # `avisos` = ramos que terminaram sem seguir por nenhum caminho. Concluir em
        # silêncio nesse caso era o "verde falso" que escondia automação mal ligada.
        avisos = r.get("avisos") or []
        execucao.resultado = {
            "texto": r["resultado"], **({"avisos": avisos} if avisos else {})
        }
        execucao.finalizada_em = datetime.now(timezone.utc)
        execucao.pendencias = None
    # Saiu de `em_andamento`: apaga o feedback ao vivo (não deixa texto obsoleto).
    execucao.atividade = None
    execucao.atividade_em = None


def _escrever_atividade(execucao_id: uuid.UUID, texto: str) -> None:
    """Publica a atividade ao vivo numa transação PRÓPRIA e curta (como um heartbeat),
    sem tocar a sessão da cadeia. Só grava se a execução ainda está `em_andamento` —
    não ressuscita atividade de execução já pausada/finalizada. Best-effort (o chamador
    em `atividade.registrar` engole erros)."""
    s = CriadorDeSessao()
    try:
        s.execute(
            update(Execucao)
            .where(Execucao.id == execucao_id, Execucao.estado == "em_andamento")
            .values(atividade=(texto or "")[:200], atividade_em=datetime.now(timezone.utc))
        )
        s.commit()
    finally:
        s.close()


def _esta_cancelada(sessao: Session, execucao_id: uuid.UUID) -> bool:
    """Relê o estado da execução no banco (vê o que outra sessão já gravou)."""
    return (
        sessao.execute(
            select(Execucao.estado).where(Execucao.id == execucao_id)
        ).scalar()
        == "cancelada"
    )


def criar_execucao(
    sessao: Session, automacao: Automacao, entrada: str, *, origem: str = "sistema"
) -> Execucao:
    """Enfileira uma execução: cria o registro no estado `aguardando` e devolve
    já com id. Quem roda é o pool de trabalhadores (`fila.py`); por isso o
    disparo responde na hora e a tela mostra o progresso (Tarefas 5.2 e 5.3).
    `iniciada_em` fica nulo até um trabalhador pegar a execução.

    `origem` (manual|agendamento|webhook|sistema) é registrado no log do disparo, com a
    IDENTIDADE DO SERVIDOR (host/ambiente) — o carimbo que teria delatado o cérebro local:
    duas execuções nascidas de `ambiente` diferentes = dois processos disparando."""
    execucao = Execucao(
        automacao_id=automacao.id,
        estado="aguardando",
        entrada={"texto": entrada},
    )
    sessao.add(execucao)
    sessao.commit()
    sessao.refresh(execucao)
    registrar_evento(
        categoria="disparo",
        acao="automacao.disparada",
        origem=origem,
        automacao_id=str(automacao.id),
        time_id=automacao.time_id,
        organizacao_id=_org_do_time(sessao, automacao.time_id),
        recurso_tipo="execucao",
        recurso_id=execucao.id,
        detalhe={"automacao": automacao.nome, "gatilho": automacao.tipo_gatilho},
    )
    return execucao


def rodar_retomada(sessao: Session, execucao: Execucao) -> Execucao:
    """Roda em SEGUNDO PLANO a retomada de um portão aprovado (§12-A). O worker da fila
    já reivindicou a execução (`em_andamento`) e detectou `retomada_resposta` preenchida.
    Espelha `rodar_execucao`: resolve as chaves da organização, fixa o contexto de log e
    publica atividade ao vivo (heartbeat p/ a tela + sweeper), e delega o miolo a
    `retoma.retomar_execucao` — que roda o próximo passo, que pode ser PESADO (publicar,
    gerar mídia). Assim aprovar devolve NA HORA e o trabalho não fica preso num request.

    `retomar_execucao` gerencia os próprios commits/estados (concluida/aguardando_humano/
    falhou). Aqui envolvemos com chaves+atividade+contexto e tratamos a falha da re-rodada
    do agente (que ele pode levantar) de forma visível, sem deixar a execução pendurada."""
    resposta = execucao.retomada_resposta or ""
    execucao.retomada_resposta = None
    sessao.commit()
    automacao = sessao.get(Automacao, execucao.automacao_id)
    time_id = automacao.time_id if automacao else None
    org_id = _org_do_time(sessao, time_id)
    with contexto.usar_contexto(
        execucao_id=str(execucao.id),
        automacao_id=str(execucao.automacao_id),
        time_id=time_id,
        organizacao_id=org_id,
        origem="fila",
    ):
        chaves, origens = resolver_chaves_por_time(sessao, time_id)
        from mensageria import aprovacao, retoma
        try:
            with usar_chaves(chaves), atividade.usar_atividade(
                lambda t: _escrever_atividade(execucao.id, t)
            ):
                retoma.retomar_execucao(
                    sessao, execucao, resposta, chaves=chaves, origens=origens
                )
            # Saiu de `em_andamento` (concluiu/pausou de novo/falhou): zera o feedback ao
            # vivo para a tela não mostrar atividade obsoleta.
            if execucao.estado != "em_andamento":
                execucao.atividade = None
                execucao.atividade_em = None
            # Coexistência (aprovação por canal): resolver pela tela desvincula a conversa
            # que aguardava — a não ser que a cadeia tenha pausado de novo (aí a retoma já
            # re-vinculou). Mesmo critério que a rota `responder` aplicava antes.
            if execucao.estado != "aguardando_humano":
                aprovacao.desvincular(sessao, execucao.id)
        except Exception as e:  # falha na re-rodada do agente do portão — visível, não muda
            execucao.estado = "falhou"
            execucao.resultado = {"erro": str(e)}
            execucao.finalizada_em = datetime.now(timezone.utc)
            execucao.atividade = None
            execucao.atividade_em = None
            registrar_evento(
                categoria="execucao", acao="retomada.falhou", nivel="error",
                resultado="falha", erro=e, recurso_tipo="execucao", recurso_id=execucao.id,
            )
            from mensageria.aviso import avisar_falha
            avisar_falha(sessao, execucao, str(e))
        sessao.commit()
        sessao.refresh(execucao)
        return execucao


def rodar_execucao(sessao: Session, execucao: Execucao) -> Execucao:
    """Roda a cadeia de uma execução já reivindicada pelo trabalhador, gravando
    cada passo e o estado final (concluida, aguardando_humano ou falhou).
    Devolve a execução."""
    automacao = sessao.get(Automacao, execucao.automacao_id)
    entrada = (execucao.entrada or {}).get("texto", "")
    time_id = automacao.time_id if automacao else None
    org_id = _org_do_time(sessao, time_id)
    # Fixa o contexto de log desta execução (execucao/automacao/time/org + origem) para
    # todo evento/log daqui pra frente — inclusive as threads de instrumentos — herdar a
    # correlação. O worker roda FORA de um request, então fixa o seu próprio contexto.
    with contexto.usar_contexto(
        execucao_id=str(execucao.id),
        automacao_id=str(execucao.automacao_id),
        time_id=time_id,
        organizacao_id=org_id,
        origem="fila",
    ):
        # Fases 7.3/7.6/7-A: resolve as chaves de cada provedor da organização desta
        # automação (fallback chave-mãe da consultoria → .env legado p/ Anthropic),
        # com a ORIGEM por provedor para a medição, e fixa o mapa no contexto durante
        # toda a cadeia, sem tocar no motor de grafo.
        chaves, origens = resolver_chaves_por_time(sessao, time_id)
        try:
            # `usar_atividade`: publica "o que está acontecendo agora" (feedback ao vivo)
            # numa sessão própria, para a tela mostrar progresso mesmo quando um instrumento
            # lento (montar_imagem, gerar_video) prende o passo por minutos. Mesmo padrão
            # do `usar_chaves`: um ContextVar atravessa o motor sem mudar assinatura nenhuma.
            with usar_chaves(chaves), atividade.usar_atividade(
                lambda t: _escrever_atividade(execucao.id, t)
            ):
                r = executar_cadeia(
                    sessao,
                    (automacao.cadeia if automacao else None) or {},
                    entrada,
                    registrar_passo=_fazer_registrador(sessao, execucao.id, origens),
                    cancelado=lambda: _esta_cancelada(sessao, execucao.id),
                )
            _aplicar_resultado(execucao, r)
            if execucao.estado == "aguardando_humano":
                # Pausou: se a automação tem canal de aprovação, amarra a conversa do
                # aprovador a esta execução (a resposta dele religa o fluxo). Borda.
                from mensageria import aprovacao
                aprovacao.vincular_pausa(sessao, execucao)
        except Exception as e:  # falha de LLM/rede/cadeia inválida — registra e segue
            execucao.estado = "falhou"
            execucao.resultado = {"erro": str(e)}
            execucao.finalizada_em = datetime.now(timezone.utc)
            execucao.atividade = None
            execucao.atividade_em = None
            # Antes a exceção era engolida (só str(e) no banco de negócio); agora vai ao
            # banco de logs COM stack — o buraco de diagnóstico que motivou este sistema.
            registrar_evento(
                categoria="execucao", acao="execucao.falhou", nivel="error",
                resultado="falha", erro=e, recurso_tipo="execucao", recurso_id=execucao.id,
            )
        sessao.commit()
        sessao.refresh(execucao)
        if execucao.estado in ("concluida", "aguardando_humano"):
            registrar_evento(
                categoria="execucao", acao=f"execucao.{execucao.estado}",
                recurso_tipo="execucao", recurso_id=execucao.id,
            )
        if execucao.estado == "falhou":
            # §12-A / PRODUTO §16: a falha não pode morrer só no banco. Avisa quem
            # opera, pelo canal do time. Best-effort e com rastro próprio.
            from mensageria.aviso import avisar_falha
            avisar_falha(sessao, execucao, str((execucao.resultado or {}).get("erro") or ""))
        return execucao
