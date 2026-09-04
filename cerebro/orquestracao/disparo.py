"""Disparo de uma automação — onde uma execução nasce e como ela roda.

Todos os gatilhos (botão manual, agendamento/CRON, webhook) **enfileiram**: criam
a execução no estado `aguardando` (`criar_execucao`) e devolvem na hora. Quem de
fato roda a cadeia é o pool de trabalhadores da fila (`fila.py`), que chama
`rodar_execucao`. Assim muitas execuções simultâneas são organizadas sem travar
(PRODUTO §18, Tarefa 5.3).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

import medicao_instrumentos
import precos
from chaves import resolver_chaves_por_time
from modelos import Automacao, Execucao, PassoExecucao, Time
from observabilidade import contexto
from observabilidade.escritor import registrar_evento
from orquestracao import atividade
from orquestracao import circuito
from orquestracao import ficha as ficha_mod
from orquestracao import grafo
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
                    # Ficha (Onda 2): as regras exatas que o MOTOR conferiu neste passo
                    # e os campos que o agente anotou. Aditivos — passos antigos não os
                    # têm e a tela lê com `.get(...)`.
                    **({"regras": passo["regras"]} if passo.get("regras") else {}),
                    **({"anotou": passo["anotou"]} if passo.get("anotou") else {}),
                    # Nó "Chamar outra automação" (Onda 3): o elo para a execução-filha
                    # ({id, time_id, nome}), para a inspeção abrir o rastro dela.
                    **(
                        {"sub_execucao": passo["sub_execucao"]}
                        if passo.get("sub_execucao")
                        else {}
                    ),
                },
                # O passo que FALHOU fica gravado como falho (antes tudo era gravado
                # "concluido" e a timeline pulava do último passo bom para "falhou",
                # sem dizer em qual nó).
                estado=passo.get("estado") or "concluido",
                iniciado_em=passo["iniciado_em"],
                finalizado_em=passo["finalizado_em"],
            )
        )
        # A FICHA a cada passo, e não só no fim: se o processo cair no meio (deploy,
        # queda), o que já foi anotado sobrevive — e a tela mostra a ficha ao vivo
        # enquanto a execução anda. `dados` é o mesmo dicionário que o motor mutou.
        if passo.get("ficha"):
            sessao.execute(
                update(Execucao)
                .where(Execucao.id == execucao_id)
                .values(dados=passo["ficha"])
            )
        sessao.commit()

    return registrar


def _teto_de_custo(automacao: Automacao | None) -> float:
    """O teto de custo por execução do fluxo, em USD. Zero = sem teto (o padrão).

    Lê a MESMA cascata do resto do comportamento do fluxo (global < perfil < ajustes),
    para o teto ser configurado no mesmo painel que os outros limites — e não virar
    mais uma fonte de verdade."""
    from mensageria.config import config_da_automacao

    try:
        return float(config_da_automacao(automacao).get("teto_usd_execucao") or 0.0)
    except (TypeError, ValueError):
        return 0.0  # valor estragado na config não pode derrubar a execução


def _tetos_de_tempo(automacao: Automacao | None) -> tuple[int, int]:
    """Os tetos de tempo do fluxo, em minutos: (por passo, pela execução). Zero = sem
    teto (o padrão). Mesma cascata do resto do comportamento do fluxo."""
    from mensageria.config import config_da_automacao

    cfg = config_da_automacao(automacao)
    def _int(chave: str) -> int:
        try:
            return max(0, int(cfg.get(chave) or 0))
        except (TypeError, ValueError):
            return 0  # valor estragado na config não pode derrubar a execução
    return _int("teto_min_passo"), _int("teto_min_execucao")


def _ordem_ja_gravada(sessao: Session, execucao_id: uuid.UUID) -> int:
    """A maior `ordem` de passo já gravada nesta execução. É o piso da numeração ao
    voltar de uma espera: sem isso a contagem recomeçaria do zero, a linha do tempo
    teria dois "passo 1" e o teto de passos por execução perderia o sentido."""
    return int(
        sessao.scalar(
            select(func.max(PassoExecucao.ordem)).where(
                PassoExecucao.execucao_id == execucao_id
            )
        )
        or 0
    )


def _passos_da_arvore(sessao: Session, execucao_id: uuid.UUID) -> list[PassoExecucao]:
    """Os passos desta execução e os das automações que ela chamou como sub-fluxo.

    Os TETOS (custo e tempo) olham a árvore inteira, e não só a execução: sem isso
    bastaria pôr o trabalho caro num nó "Chamar outra automação" para o teto do
    chamador nunca ser alcançado — o limite viraria enfeite. A aba Uso não muda: lá
    cada execução continua contando por si, e ninguém soma o mesmo dinheiro duas
    vezes."""
    from orquestracao import sub_fluxo

    ids = sub_fluxo.ids_da_arvore(sessao, execucao_id)
    return list(
        sessao.scalars(
            select(PassoExecucao).where(PassoExecucao.execucao_id.in_(ids))
        ).all()
    )


def tempo_ja_trabalhado_s(sessao: Session, execucao_id: uuid.UUID) -> float:
    """Quanto esta execução já TRABALHOU nos passos gravados, em segundos.

    A soma da duração dos passos — não o relógio desde que ela nasceu. Uma execução
    que esperou três dias por uma aprovação não trabalhou três dias, e contar a espera
    a mataria na retomada, punindo justamente o comportamento que o produto pede.
    Soma também o trabalho dos sub-fluxos que ela chamou (ver `_passos_da_arvore`)."""
    return sum(
        max(0.0, (p.finalizado_em - p.iniciado_em).total_seconds())
        for p in _passos_da_arvore(sessao, execucao_id)
        if p.iniciado_em and p.finalizado_em
    )


def custo_ja_gasto(sessao: Session, execucao_id: uuid.UUID) -> float:
    """Quanto esta execução já custou nos passos GRAVADOS (USD).

    É o análogo do `ordem_inicial` para dinheiro: sem isto, o teto zeraria a cada
    retomada de aprovação e uma execução que espera duas vezes gastaria o teto três
    vezes. Fonte única de preço: `precos.custo_de_entrada`, a mesma da aba Uso. Conta
    também o que os sub-fluxos gastaram (ver `_passos_da_arvore`)."""
    passos = _passos_da_arvore(sessao, execucao_id)
    return sum(precos.custo_de_entrada(e) for e in precos.entradas_dos_passos(passos))


def _aplicar_resultado(execucao: Execucao, r: dict) -> None:
    """Aplica à execução o que a cadeia devolveu: pausa, cancelamento ou
    conclusão."""
    # A ficha como ficou (Onda 2). Vale para os TRÊS desfechos: numa pausa ela precisa
    # sobreviver à espera (que pode durar horas), e num cancelamento ela é o registro
    # do que já tinha sido apurado.
    if r.get("ficha") is not None:
        execucao.dados = dict(r["ficha"])
    if r["estado"] == "aguardando_sub_fluxo":
        # Nó "Chamar outra automação" (Onda 3): a execução dorme enquanto a filha
        # roda, e quem a solta é a própria filha ao chegar num veredito. Mesma
        # mecânica da pausa por aprovação e da espera por tempo — muda só o gatilho
        # do retorno. As `pendencias` levam, no ramo que espera, qual filha aguardar.
        execucao.estado = "aguardando_sub_fluxo"  # sem finalizada_em: ainda viva
        execucao.pendencias = r.get("pendentes") or None
    elif r["estado"] == "aguardando_tempo":
        # Nó "Esperar" (Onda 3): a execução dorme até `retomar_em` e o vigia a devolve
        # à fila. Mesma mecânica da pausa por aprovação — o que muda é quem a solta.
        execucao.estado = "aguardando_tempo"  # sem finalizada_em: ainda viva
        execucao.retomar_em = r.get("retomar_em")
        execucao.pendencias = r.get("pendentes") or None
    elif r["estado"] == "aguardando_humano":
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
    sessao: Session,
    automacao: Automacao,
    entrada: str,
    *,
    origem: str = "sistema",
    desenho: dict | None = None,
    dados: dict | None = None,
    no_inicial: str | None = None,
    origem_execucao_id: uuid.UUID | None = None,
    teste_de_no: bool = False,
    chamada_por_execucao_id: uuid.UUID | None = None,
) -> Execucao:
    """Enfileira uma execução: cria o registro no estado `aguardando` e devolve
    já com id. Quem roda é o pool de trabalhadores (`fila.py`); por isso o
    disparo responde na hora e a tela mostra o progresso (Tarefas 5.2 e 5.3).
    `iniciada_em` fica nulo até um trabalhador pegar a execução.

    `origem` (manual|agendamento|webhook|sistema) é registrado no log do disparo, com a
    IDENTIDADE DO SERVIDOR (host/ambiente) — o carimbo que teria delatado o cérebro local:
    duas execuções nascidas de `ambiente` diferentes = dois processos disparando.

    Aqui também nasce o DESENHO da execução (Onda 4): a foto do grafo NESTE instante.
    É o funil único dos quatro gatilhos (manual, agendamento, webhook, comentário do
    Instagram), então uma linha só congela o fluxo para todos. A foto é do momento do
    DISPARO, não do momento em que o trabalhador pega a execução: entre um e outro pode
    haver minutos de fila, e quem disparou espera o fluxo que existia quando disparou.

    "Rodar de novo a partir daqui" (fatia 2) passa pelo MESMO funil, só que trazendo o
    que herda da execução de origem: o `desenho` (para a re-rodada percorrer o mesmo
    fluxo), os `dados` (a ficha, para não recomeçar sem o que já se sabia), o
    `no_inicial` (por onde começar) e de quem ela nasceu.

    "Testar este nó" (fatia 5) também: `no_inicial` + `teste_de_no=True` + a entrada de
    mentira. Passar pelo funil é o que dá ao teste, de graça, a fila (nada preso num
    request longo), o heartbeat, o rastro e a tela de inspeção.

    E o nó "Chamar outra automação" (Onda 3, fatia 4) também: a filha nasce AQUI, com
    `chamada_por_execucao_id` apontando para quem a chamou e uma cópia da ficha dele em
    `dados`. Ela é uma execução como qualquer outra — aparece na lista, deixa rastro e
    pode ela mesma pedir aprovação —, e o que a distingue é só saber a quem devolver o
    resultado."""
    execucao = Execucao(
        automacao_id=automacao.id,
        estado="aguardando",
        entrada={"texto": entrada},
        # A origem também FICA na execução (Onda 4, fatia 3), não só no log: o
        # disjuntor precisa saber se esta rodada tinha gente olhando ou não.
        origem=origem,
        desenho=desenho or grafo.normalizar(automacao.cadeia or {}) or None,
        dados=dict(dados) if dados else None,
        no_inicial=no_inicial or None,
        origem_execucao_id=origem_execucao_id,
        teste_de_no=teste_de_no,
        chamada_por_execucao_id=chamada_por_execucao_id,
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
            circuito.apos_falha(sessao, execucao, str(e))
        sessao.commit()
        sessao.refresh(execucao)
        # A filha pode ter parado numa aprovação e só agora terminado: quem espera por
        # ela é liberado aqui também (§12-A — nenhum estado "em andamento" sem quem o
        # varra; e o vigia periódico segue como rede).
        _devolver_ao_chamador(sessao, execucao)
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
        min_passo, min_execucao = _tetos_de_tempo(automacao)
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
                    # O DESENHO desta execução (Onda 4): a foto do disparo, ou a cadeia
                    # viva nas execuções anteriores a esta onda. Fonte única em `grafo`.
                    grafo.desenho_que_roda(
                        execucao.desenho, automacao.cadeia if automacao else None
                    ),
                    entrada,
                    # A FICHA nasce aqui, com o que o gatilho trouxe — e é o que faz a
                    # entrada deixar de morrer no primeiro nó (Onda 2, lacuna 15).
                    # Execução re-rodada do zero reaproveita a ficha que já tinha.
                    ficha=dict(execucao.dados or {}) or ficha_mod.nova(entrada),
                    # VOLTANDO DE UMA ESPERA (nó "Esperar", Onda 3): as pendências
                    # dizem por onde continuar. Uma execução reivindicada com
                    # pendências e sem resposta de aprovação só pode ser isto — a
                    # pausa por aprovação sai por `rodar_retomada`, e execução nova
                    # nasce sem pendências. Nulo = começa do início, como sempre.
                    frente_inicial=list(execucao.pendencias or []) or None,
                    ordem_inicial=_ordem_ja_gravada(sessao, execucao.id),
                    # "Rodar de novo a partir daqui" (fatia 2): começa do nó pedido, em
                    # vez do início do grafo. Nulo = o caso de sempre.
                    no_inicial=execucao.no_inicial or None,
                    # Teto de custo do fluxo (Onda 4, fatia 4). Zero = sem teto, que
                    # é o padrão. O já gasto vem dos passos: numa re-rodada do zero
                    # não há nenhum, mas a fonte é a mesma da retomada — uma conta só.
                    teto_usd=_teto_de_custo(automacao),
                    custo_inicial=custo_ja_gasto(sessao, execucao.id),
                    # Tetos de TEMPO do fluxo (Onda 3, fatia 2). Zero = sem teto.
                    teto_min_passo=min_passo,
                    teto_min_execucao=min_execucao,
                    tempo_inicial_s=tempo_ja_trabalhado_s(sessao, execucao.id),
                    # "Testar este nó" (fatia 5): roda o nó do `no_inicial` e para,
                    # sem seguir as setas. Falso = o caso de sempre.
                    so_um_passo=bool(execucao.teste_de_no),
                    # Quem está rodando (Onda 3, fatia 4): o nó "Chamar outra
                    # automação" precisa dele para subir a linhagem (barrar o laço
                    # A→B→A) e para carimbar a filha com quem a chamou.
                    execucao_id=execucao.id,
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
            # §12-A / PRODUTO §16: a falha não pode morrer só no banco. O funil único
            # do caminho de erro avisa quem opera pelo canal do time e, se esta for a
            # terceira falha seguida de uma automação que roda sozinha, desliga a
            # automação (Onda 4, fatia 3). Best-effort e com rastro próprio.
            circuito.apos_falha(
                sessao, execucao, str((execucao.resultado or {}).get("erro") or "")
            )
            sessao.commit()
        _devolver_ao_chamador(sessao, execucao)
        return execucao


def _devolver_ao_chamador(sessao: Session, execucao: Execucao) -> None:
    """Se esta execução é o sub-fluxo de alguém e acabou de dar seu veredito, devolve
    o chamador à fila NA HORA, em vez de deixá-lo esperar o próximo giro do vigia.

    Chama a MESMA função do vigia (`soltar_chamadores_concluidos`) de propósito: um
    segundo caminho de retorno seria exatamente o tipo de duplicação que um dia
    diverge — um deles ganharia um conserto e o outro não."""
    from orquestracao import sub_fluxo

    if not execucao.chamada_por_execucao_id:
        return
    if execucao.estado not in sub_fluxo.ESTADOS_FINAIS:
        return
    sub_fluxo.soltar_chamadores_concluidos(sessao)
