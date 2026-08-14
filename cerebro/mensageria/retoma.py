"""Miolo de retoma de uma execução pausada (espera-por-humano), reutilizável.

Duas superfícies retomam um portão:
- TELA (`rotas/automacoes.py::responder`): `retomar_execucao` (conversacional: re-roda
  o agente, que pode perguntar de volta; a pergunta vira um passo na tela).
- CANAL (`mensageria/servico.py`): o turno de portão roda pela BORDA (entrega +
  ciclo de vida de mensageria) e usa `avancar_apos_gate` direto; quando o nó é
  MECÂNICO (forma "direto", 1 saída, gate-roteador), chama `retomar_execucao` com
  `permitir_conversa=False`.

NÃO toca o núcleo (`cadeia.py`); só o usa. `avancar_apos_gate` e `_localizar_no_pausado`
são o que tela e canal compartilham.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mensageria.config import com_ajuste_do_no, config_da_automacao
from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao import grafo, memoria_conversa
from orquestracao.agente import executar_agente
from orquestracao.cadeia import _carregar_cinto, _escolher_saida, executar_cadeia
from orquestracao.disparo import _aplicar_resultado, _fazer_registrador
from orquestracao.llm import usar_chaves

# Anti-loop do portão NA TELA (a tela não tem teto de conversa). No CANAL, quem
# limita as rodadas é o teto de turnos/custo da conversa (regra geral de mensageria).
MAX_RODADAS_GATE = 8


def entrada_retomada(saida_pausada: str, resposta: str) -> str:
    """A entrada do próximo nó ao retomar uma pausa: o trabalho que o agente
    produziu + a decisão/feedback do humano, separados e rotulados."""
    return f"{saida_pausada}\n\n---\n[Resposta do humano]\n{resposta}"


def localizar_no_pausado(sessao: Session, execucao: Execucao):
    """Acha (último passo, nó do grafo, no_id, cadeia normalizada, índice) do ponto
    onde a execução pausou. Levanta ValueError se não há passo de pausa."""
    auto = sessao.get(Automacao, execucao.automacao_id)
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    no_id = (ultimo.no_id if ultimo else None) or (
        str(ultimo.agente_id) if ultimo and ultimo.agente_id else None
    )
    if no_id is None:
        raise ValueError("passo de pausa ausente")
    cadeia = grafo.normalizar((auto.cadeia if auto else None) or {})
    idx = grafo.indexar(cadeia)
    no = idx.no(no_id) or {}
    return ultimo, no, no_id, cadeia, idx


def rodadas_no_gate(sessao: Session, execucao_id, no_id: str) -> int:
    """Quantos passos já rodaram neste nó de gate (apresentação inicial + cada
    pergunta de volta na TELA). Base do anti-loop da tela."""
    return (
        sessao.scalar(
            select(func.count(PassoExecucao.id))
            .where(PassoExecucao.execucao_id == execucao_id)
            .where(PassoExecucao.no_id == no_id)
        )
        or 0
    )


def avancar_apos_gate(
    sessao: Session,
    execucao: Execucao,
    *,
    idx,
    cadeia: dict,
    escolhida: dict | None,
    entrada_proxima: str,
    ordem_inicial: int,
    chaves: dict,
    origens: dict,
) -> Execucao:
    """Decisão tomada: o fluxo ANDA pelo ramo `escolhida`. Destino fim (ou nenhum) →
    conclui com o trabalho + a decisão; senão segue a cadeia do destino. Re-vincula
    se pausar em outro portão. Compartilhado por TELA e CANAL."""
    destino = escolhida.get("destino") if escolhida else None
    proximo = None if (destino is None or idx.eh_fim(destino)) else destino

    if proximo is None:
        execucao.estado = "concluida"
        execucao.resultado = {"texto": entrada_proxima}
        execucao.finalizada_em = datetime.now(timezone.utc)
        sessao.commit()
        sessao.refresh(execucao)
        return execucao

    execucao.estado = "em_andamento"
    # Reinicia o relógio de inatividade do sweeper. A execução pode ter ficado HORAS em
    # `aguardando_humano` e só AGORA volta a rodar os passos pós-portão. `iniciada_em` é o
    # piso do heartbeat em `fila.recuperar_execucoes_presas`: sem reiniciá-lo aqui, o sweeper
    # mede o tempo desde ANTES da espera e mata a execução no instante da retomada. O caminho
    # por CANAL (Telegram) roda INLINE, sem passar pelo `_reivindicar` da fila (que já
    # reinicia no worker) — e este é o ponto ÚNICO por onde toda retomada entra em
    # `em_andamento` (mecânico e conversacional, canal e tela). FONTE ÚNICA com o sweeper.
    execucao.iniciada_em = datetime.now(timezone.utc)
    sessao.commit()
    try:
        with usar_chaves(chaves):
            r = executar_cadeia(
                sessao,
                cadeia,
                entrada_proxima,
                no_inicial=proximo,
                ordem_inicial=ordem_inicial,
                registrar_passo=_fazer_registrador(sessao, execucao.id, origens),
            )
        _aplicar_resultado(execucao, r)
        if execucao.estado == "aguardando_humano":
            from mensageria import aprovacao
            aprovacao.vincular_pausa(sessao, execucao)
    except Exception as e:
        execucao.estado = "falhou"
        execucao.resultado = {"erro": str(e)}
        execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(execucao)
    return execucao


def retomar_execucao(
    sessao: Session,
    execucao: Execucao,
    resposta: str,
    *,
    chaves: dict,
    origens: dict,
    permitir_conversa: bool = True,
) -> Execucao:
    """Retoma uma execução em `aguardando_humano` (TELA, e CANAL mecânico).

    `permitir_conversa=True` (tela): se o nó é gate-agente com 2+ saídas e dentro do
    teto de rodadas, RE-RODA o agente (ele pode perguntar de volta). Senão (ou
    `permitir_conversa=False`, usado pelo canal mecânico), a RESPOSTA escolhe a saída
    (roteamento mecânico). Pré-condição: o chamador garantiu o estado
    `aguardando_humano`. Levanta ValueError se não há passo de pausa.
    """
    ultimo, no, no_id, cadeia, idx = localizar_no_pausado(sessao, execucao)
    saidas = no.get("saidas") or []

    # Teto de idas-e-vindas do portão na TELA: DERIVADO da config (Tipo de fluxo <
    # ajuste do nó). Antes era só o fixo `MAX_RODADAS_GATE`; agora `portao_max_rodadas`
    # passa a valer (a tela não tem conversa/canal → `config_da_automacao`). O fixo é o
    # default. Cura a chave morta apontada na varredura.
    auto = sessao.get(Automacao, execucao.automacao_id)
    max_rodadas = com_ajuste_do_no(config_da_automacao(auto), no).get(
        "portao_max_rodadas", MAX_RODADAS_GATE
    )

    eh_gate_agente = bool(no.get("gate") and no.get("ref") and len(saidas) >= 2)
    if (
        permitir_conversa
        and eh_gate_agente
        and rodadas_no_gate(sessao, execucao.id, no_id) < max_rodadas
    ):
        return _retomar_conversando_tela(
            sessao, execucao, resposta,
            ultimo=ultimo, cadeia=cadeia, idx=idx, no=no, saidas=saidas,
            chaves=chaves, origens=origens,
        )

    # Mecânico: a RESPOSTA escolhe a saída.
    if len(saidas) == 0:
        escolhida = None
    elif len(saidas) == 1:
        escolhida = saidas[0]
    else:
        with usar_chaves(chaves):
            escolhida, _ = _escolher_saida(resposta, saidas)
    entrada_proxima = entrada_retomada((ultimo.saida or {}).get("texto", ""), resposta)
    return avancar_apos_gate(
        sessao, execucao, idx=idx, cadeia=cadeia, escolhida=escolhida,
        entrada_proxima=entrada_proxima, ordem_inicial=ultimo.ordem,
        chaves=chaves, origens=origens,
    )


def _retomar_conversando_tela(
    sessao: Session,
    execucao: Execucao,
    resposta: str,
    *,
    ultimo: PassoExecucao,
    cadeia: dict,
    idx,
    no: dict,
    saidas: list[dict],
    chaves: dict,
    origens: dict,
) -> Execucao:
    """Portão conversacional NA TELA: re-roda o agente do nó com a resposta da pessoa
    (encadeando o histórico do passo). Declarou um ramo (`seguir_para`) → o fluxo
    anda; não declarou (perguntou) → a pergunta vira um novo passo (visível na tela)
    e a execução segue `aguardando_humano`."""
    agente = sessao.get(Agente, uuid.UUID(str(no.get("ref"))))
    no_id = ultimo.no_id or (str(ultimo.agente_id) if ultimo.agente_id else None)
    entrada_rerun = (
        f"{(ultimo.entrada or {}).get('texto', '')}\n\n"
        f"{(ultimo.saida or {}).get('texto', '')}\n\n"
        f"---\n[Resposta do humano]\n{resposta}"
    ).strip()

    # Memória do portão de ESTEIRA (Fatia 4.3 / P3c-B): o agente do portão deixa de
    # "renascer" a cada rodada. Um checkpointer + thread próprio da execução
    # (`execucao:nó`) guarda o fio das rodadas deste portão. Na 1ª retomada (sem estado)
    # SEMEIA com o `entrada_rerun` (o apresentado + a resposta) — idêntico a hoje; nas
    # rodadas seguintes a entrada é SÓ a resposta do humano (o agente lembra o resto).
    # Sem checkpointer disponível → modo LEGADO (sempre `entrada_rerun`), byte-idêntico ao
    # de antes. NÃO usa portão nativo/interrupt (isso é a Opção A, recusada): o agente roda
    # até o fim (apresenta/decide) com memória — o mesmo padrão da conversa (P2a).
    ckpt = memoria_conversa.obter()
    memoria = ckpt is not None and no_id is not None
    tid = f"{execucao.id}:{no_id}" if memoria else None
    if memoria and memoria_conversa.tem_estado(tid):
        entrada = f"---\n[Resposta do humano]\n{resposta}"
    else:
        entrada = entrada_rerun
    kwargs_mem = {"checkpointer": ckpt, "thread_id": tid} if memoria else {}

    iniciado = datetime.now(timezone.utc)
    # Instruções de FECHAMENTO do portão (o "portao.md"): o que o agente deve FAZER
    # depois que a pessoa respondeu (ex.: agendar E encaminhar). Fallback ao texto padrão.
    texto_portao = (no.get("instrucoes") or {}).get("fechamento")
    with usar_chaves(chaves):
        cinto = _carregar_cinto(sessao, agente.id)
        resultado = executar_agente(
            agente, cinto, entrada, saidas=saidas, gate=True,
            texto_portao=texto_portao, **kwargs_mem,
        )
    finalizado = datetime.now(timezone.utc)

    saida_texto = resultado["saida"]
    mensagens_enviadas = resultado.get("mensagens_enviadas") or {}
    if mensagens_enviadas:
        # No PASSO registrado mostramos o que a pessoa de fato viu nesta rodada (a
        # mensagem enviada pelo canal), não o status que o agente narrou. Mesmo
        # critério da pausa inicial (`cadeia.py`). Vale SÓ para o registro do passo
        # (e, em rodadas conversacionais, para a `ultimo.saida` da próxima rodada) —
        # NÃO para o que segue ao próximo nó depois de aprovado (ver abaixo).
        canal_id = str((no.get("aprovacao") or {}).get("instrumento_id") or "")
        apresentadas = mensagens_enviadas.get(canal_id) or [
            t for textos in mensagens_enviadas.values() for t in textos
        ]
        if apresentadas:
            saida_texto = "\n\n".join(apresentadas)

    ramo = resultado.get("ramo_escolhido")
    por_rotulo = {s["rotulo"]: s for s in saidas if s.get("rotulo")}
    escolhida = por_rotulo.get(ramo) if ramo else None
    ordem = ultimo.ordem + 1

    passo = {
        "no_id": ultimo.no_id or (str(ultimo.agente_id) if ultimo.agente_id else None),
        "tipo": "espera_humano",  # Fatia 4.1: re-run do nó de PORTÃO = espera por humano
        "agente_id": str(agente.id),
        "agente_nome": agente.nome,
        "entrada": entrada_rerun,
        "saida": saida_texto,
        "instrumentos_acionados": resultado.get("instrumentos_acionados") or [],
        "saida_escolhida": escolhida["rotulo"] if escolhida else None,
        "uso": list(resultado.get("uso") or []),
        "iniciado_em": iniciado,
        "finalizado_em": finalizado,
    }
    _fazer_registrador(sessao, execucao.id, origens)(passo, ordem)

    if escolhida is None:
        execucao.estado = "aguardando_humano"
        sessao.commit()
        from mensageria import aprovacao
        aprovacao.vincular_pausa(sessao, execucao)
        sessao.commit()
        sessao.refresh(execucao)
        return execucao

    # O que segue ao próximo nó é SEMPRE o conteúdo APRESENTADO no portão — o que a
    # pessoa viu e aprovou (`ultimo.saida`, o passo pausado) — somado à resposta dela.
    # NUNCA o texto que o agente narra DEPOIS de aprovar ("aprovado, seguindo…"), ainda
    # que ele mande essa confirmação por um canal nesta rodada: a pessoa aprovou o que
    # já estava na tela, não a confirmação. Unifica o critério com o caminho mecânico
    # (acima) e o por canal (`servico._turno_de_portao`, que repassa o histórico — o
    # apresentado está nele). Sem isto, aprovar pela TELA um agente que também confirma
    # pelo Telegram perdia o conteúdo: descia "aprovado!" no lugar do artigo (a falha da
    # execução 132bcaa6, 2026-06-23 — agente que aprova E tagarela no canal na mesma
    # rodada).
    apresentado_aprovado = (ultimo.saida or {}).get("texto", "")
    return avancar_apos_gate(
        sessao, execucao, idx=idx, cadeia=cadeia, escolhida=escolhida,
        entrada_proxima=entrada_retomada(apresentado_aprovado, resposta),
        ordem_inicial=ordem, chaves=chaves, origens=origens,
    )
