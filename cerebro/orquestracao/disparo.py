"""Disparo de uma automação — o ponto único onde uma execução nasce.

Todos os gatilhos (botão manual, agendamento/CRON, webhook de entrada) chegam
aqui: criam uma `Execucao`, rodam a cadeia sobre o LangGraph e gravam o
resultado. Cada chamador entra com sua própria sessão de banco — o botão usa a
sessão da requisição; o agendador e o webhook abrem uma sessão própria.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from modelos import Automacao, Execucao, PassoExecucao
from orquestracao.cadeia import executar_cadeia


def _fazer_registrador(sessao: Session, execucao_id: uuid.UUID):
    """Callback que grava cada passo da cadeia em `passos_execucao`."""

    def registrar(passo: dict, ordem: int) -> None:
        sessao.add(
            PassoExecucao(
                execucao_id=execucao_id,
                ordem=ordem,
                agente_id=uuid.UUID(passo["agente_id"]),
                entrada={"texto": passo["entrada"]},
                saida={
                    "texto": passo["saida"],
                    "instrumentos_acionados": passo["instrumentos_acionados"],
                    "saida_escolhida": passo["saida_escolhida"],
                },
                estado="concluido",
                iniciado_em=passo["iniciado_em"],
                finalizado_em=passo["finalizado_em"],
            )
        )
        sessao.commit()

    return registrar


def _aplicar_resultado(execucao: Execucao, r: dict) -> None:
    """Aplica à execução o que a cadeia devolveu: pausa ou conclusão."""
    if r["estado"] == "aguardando_humano":
        execucao.estado = "aguardando_humano"  # sem finalizada_em: ainda viva
    else:
        execucao.estado = "concluida"
        execucao.resultado = {"texto": r["resultado"]}
        execucao.finalizada_em = datetime.now(timezone.utc)


def executar_automacao(
    sessao: Session, automacao: Automacao, entrada: str
) -> Execucao:
    """Cria e roda uma execução da automação a partir de uma entrada.

    Não decide *quem* pode disparar (isso é do chamador) nem checa o gatilho —
    apenas executa. Devolve a `Execucao` já persistida, em seu estado final
    (concluida, aguardando_humano ou falhou).
    """
    execucao = Execucao(
        automacao_id=automacao.id,
        estado="em_andamento",
        entrada={"texto": entrada},
        iniciada_em=datetime.now(timezone.utc),
    )
    sessao.add(execucao)
    sessao.commit()
    sessao.refresh(execucao)

    try:
        r = executar_cadeia(
            sessao,
            automacao.cadeia or {},
            entrada,
            registrar_passo=_fazer_registrador(sessao, execucao.id),
        )
        _aplicar_resultado(execucao, r)
    except Exception as e:  # falha de LLM/rede/cadeia inválida — registra e segue
        execucao.estado = "falhou"
        execucao.resultado = {"erro": str(e)}
        execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(execucao)
    return execucao
