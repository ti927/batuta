"""Miolo de retoma de uma execução pausada (espera-por-humano), reutilizável.

Extraído de `rotas/automacoes.py::responder` para que a camada de mensageria
(mão dupla) retome uma conversa sem depender do request/usuário HTTP. NÃO toca o
núcleo (`cadeia.py`); só o usa. O chamador continua dono da autorização, do
estado (409) e da auditoria; aqui fica a MECÂNICA: achar o ponto de pausa, rotear
pela resposta e seguir a cadeia do próximo nó.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao import grafo
from orquestracao.agente import executar_agente
from orquestracao.cadeia import _carregar_cinto, _escolher_saida, executar_cadeia
from orquestracao.disparo import _aplicar_resultado, _fazer_registrador
from orquestracao.llm import usar_chaves

# Portão conversacional: quantas RODADAS (turnos do agente) num mesmo nó de gate
# antes de cair no roteamento mecânico. Trilho anti-loop — o agente não conversa
# para sempre. Cada resposta da pessoa dispara uma rodada, então o limite é alto.
MAX_RODADAS_GATE = 8


def entrada_retomada(saida_pausada: str, resposta: str) -> str:
    """A entrada do próximo nó ao retomar uma pausa: o trabalho que o agente
    produziu + a decisão/feedback do humano, separados e rotulados."""
    return f"{saida_pausada}\n\n---\n[Resposta do humano]\n{resposta}"


def retomar_execucao(
    sessao: Session,
    execucao: Execucao,
    resposta: str,
    *,
    chaves: dict,
    origens: dict,
) -> Execucao:
    """Retoma uma execução em `aguardando_humano`: a `resposta` escolhe a saída do
    nó pausado (PRODUTO §14) e a cadeia segue do próximo nó. Muta e dá commit na
    `execucao`; devolve-a atualizada.

    Pré-condição: o chamador já garantiu `execucao.estado == 'aguardando_humano'`.
    Levanta `ValueError` se não há passo de pausa para derivar o ponto de retomada.
    """
    auto = sessao.get(Automacao, execucao.automacao_id)

    # O ponto de retomada é derivado do último passo (onde pausou) + a cadeia.
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    # O nó pausado é localizado por id de nó (`no_id`). Para execuções antigas (sem
    # `no_id` gravado), cai no `agente_id` — que, na cadeia convertida, é o id do nó.
    no_pausado = (ultimo.no_id if ultimo else None) or (
        str(ultimo.agente_id) if ultimo and ultimo.agente_id else None
    )
    if no_pausado is None:
        raise ValueError("passo de pausa ausente")

    cadeia = grafo.normalizar(auto.cadeia or {})
    idx = grafo.indexar(cadeia)
    no = idx.no(no_pausado) or {}
    saidas = no.get("saidas") or []

    # Portão CONVERSACIONAL: nó-agente com 2+ saídas → quem decide o caminho é o
    # PRÓPRIO agente, conversando (pode perguntar de volta), em vez de uma LLM
    # roteadora casar a palavra. Trilho anti-loop: passado o teto de rodadas no
    # mesmo nó, cai no roteamento mecânico (não conversa para sempre).
    eh_gate_agente = bool(no.get("gate") and no.get("ref") and len(saidas) >= 2)
    if eh_gate_agente and _rodadas_no_gate(sessao, execucao.id, no_pausado) < MAX_RODADAS_GATE:
        return _retomar_conversando(
            sessao, execucao, resposta,
            ultimo=ultimo, cadeia=cadeia, idx=idx, no=no, saidas=saidas,
            chaves=chaves, origens=origens,
        )

    # Portão de aprovação (PRODUTO §14): a RESPOSTA escolhe o caminho.
    if len(saidas) == 0:
        escolhida = None
    elif len(saidas) == 1:
        escolhida = saidas[0]
    else:
        with usar_chaves(chaves):
            escolhida, _ = _escolher_saida(resposta, saidas)
    destino = escolhida.get("destino") if escolhida else None
    proximo = None if (destino is None or idx.eh_fim(destino)) else destino

    entrada_proxima = entrada_retomada((ultimo.saida or {}).get("texto", ""), resposta)

    # Sem próximo agente (destino fim): encerra com o trabalho + a decisão.
    if proximo is None:
        execucao.estado = "concluida"
        execucao.resultado = {"texto": entrada_proxima}
        execucao.finalizada_em = datetime.now(timezone.utc)
        sessao.commit()
        sessao.refresh(execucao)
        return execucao

    execucao.estado = "em_andamento"
    sessao.commit()
    try:
        with usar_chaves(chaves):
            r = executar_cadeia(
                sessao,
                cadeia,
                entrada_proxima,
                no_inicial=proximo,
                ordem_inicial=ultimo.ordem,
                registrar_passo=_fazer_registrador(sessao, execucao.id, origens),
            )
        _aplicar_resultado(execucao, r)
        if execucao.estado == "aguardando_humano":
            # Pausou de novo (outro portão): re-amarra a conversa do aprovador para
            # a próxima resposta também religar o fluxo (aprovação por canal).
            from mensageria import aprovacao
            aprovacao.vincular_pausa(sessao, execucao)
    except Exception as e:
        execucao.estado = "falhou"
        execucao.resultado = {"erro": str(e)}
        execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(execucao)
    return execucao


def _rodadas_no_gate(sessao: Session, execucao_id, no_id: str) -> int:
    """Quantos passos já rodaram neste nó de gate (presentação inicial + cada
    pergunta de volta do agente). Base do trilho anti-loop."""
    return (
        sessao.scalar(
            select(func.count(PassoExecucao.id))
            .where(PassoExecucao.execucao_id == execucao_id)
            .where(PassoExecucao.no_id == no_id)
        )
        or 0
    )


def _retomar_conversando(
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
    """Portão conversacional: re-roda o AGENTE do nó com a resposta da pessoa (e o
    histórico do passo), reusando o mesmo `executar_agente` da orquestração. O
    agente então DECIDE: se declarou um ramo (`seguir_para`), o fluxo anda; se não
    (perguntou de volta, esclareceu), a execução segue `aguardando_humano` para a
    próxima resposta. O agente fala pelo SEU canal (como faz na 1ª apresentação);
    a borda só registra/entrega o ack — nunca duplica o envio."""
    no_id = ultimo.no_id or (str(ultimo.agente_id) if ultimo.agente_id else None)
    agente = sessao.get(Agente, uuid.UUID(str(no.get("ref"))))

    # A entrada do re-run encadeia o que o agente recebeu + o que apresentou + a
    # resposta da pessoa, preservando o contexto entre rodadas.
    entrada_rerun = (
        f"{(ultimo.entrada or {}).get('texto', '')}\n\n"
        f"{(ultimo.saida or {}).get('texto', '')}\n\n"
        f"---\n[Resposta do humano]\n{resposta}"
    ).strip()

    iniciado = datetime.now(timezone.utc)
    with usar_chaves(chaves):
        cinto = _carregar_cinto(sessao, agente.id)
        resultado = executar_agente(
            agente, cinto, entrada_rerun, saidas=saidas, gate=True
        )
    finalizado = datetime.now(timezone.utc)

    # O que segue/persiste é o que o agente APRESENTOU à pessoa (não o status que
    # ele narra) — mesma regra do motor no portão.
    saida_texto = resultado["saida"]
    mensagens_enviadas = resultado.get("mensagens_enviadas") or {}
    if mensagens_enviadas:
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
        "no_id": no_id,
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

    # O agente NÃO decidiu (perguntou / esclareceu) → segue aguardando a pessoa.
    if escolhida is None:
        execucao.estado = "aguardando_humano"
        sessao.commit()
        from mensageria import aprovacao
        aprovacao.vincular_pausa(sessao, execucao)
        sessao.commit()
        sessao.refresh(execucao)
        return execucao

    # O agente DECIDIU → o fluxo anda pelo ramo escolhido.
    destino = escolhida.get("destino")
    proximo = None if (destino is None or idx.eh_fim(destino)) else destino
    entrada_proxima = entrada_retomada(saida_texto, resposta)
    if proximo is None:
        execucao.estado = "concluida"
        execucao.resultado = {"texto": entrada_proxima}
        execucao.finalizada_em = datetime.now(timezone.utc)
        sessao.commit()
        sessao.refresh(execucao)
        return execucao

    execucao.estado = "em_andamento"
    sessao.commit()
    try:
        with usar_chaves(chaves):
            r = executar_cadeia(
                sessao,
                cadeia,
                entrada_proxima,
                no_inicial=proximo,
                ordem_inicial=ordem,
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
