"""Miolo de retoma de uma execução pausada (espera-por-humano), reutilizável.

Extraído de `rotas/automacoes.py::responder` para que a camada de mensageria
(mão dupla) retome uma conversa sem depender do request/usuário HTTP. NÃO toca o
núcleo (`cadeia.py`); só o usa. O chamador continua dono da autorização, do
estado (409) e da auditoria; aqui fica a MECÂNICA: achar o ponto de pausa, rotear
pela resposta e seguir a cadeia do próximo nó.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from modelos import Automacao, Execucao, PassoExecucao
from orquestracao.cadeia import _DESTINOS_FIM, _escolher_saida, executar_cadeia
from orquestracao.disparo import _aplicar_resultado, _fazer_registrador
from orquestracao.llm import usar_chaves


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
    if ultimo is None or ultimo.agente_id is None:
        raise ValueError("passo de pausa ausente")

    cadeia = auto.cadeia or {}
    no = (cadeia.get("nos") or {}).get(str(ultimo.agente_id)) or {}
    saidas = no.get("saidas") or []

    # Portão de aprovação (PRODUTO §14): a RESPOSTA escolhe o caminho.
    if len(saidas) == 0:
        escolhida = None
    elif len(saidas) == 1:
        escolhida = saidas[0]
    else:
        with usar_chaves(chaves):
            escolhida, _ = _escolher_saida(resposta, saidas)
    destino = escolhida.get("destino") if escolhida else None
    proximo = None if destino in _DESTINOS_FIM else destino

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
