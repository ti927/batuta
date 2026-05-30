"""Disparo de uma automação — onde uma execução nasce e como ela roda.

Todos os gatilhos (botão manual, agendamento/CRON, webhook) **enfileiram**: criam
a execução no estado `aguardando` (`criar_execucao`) e devolvem na hora. Quem de
fato roda a cadeia é o pool de trabalhadores da fila (`fila.py`), que chama
`rodar_execucao`. Assim muitas execuções simultâneas são organizadas sem travar
(PRODUTO §18, Tarefa 5.3).
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


def criar_execucao(
    sessao: Session, automacao: Automacao, entrada: str
) -> Execucao:
    """Enfileira uma execução: cria o registro no estado `aguardando` e devolve
    já com id. Quem roda é o pool de trabalhadores (`fila.py`); por isso o
    disparo responde na hora e a tela mostra o progresso (Tarefas 5.2 e 5.3).
    `iniciada_em` fica nulo até um trabalhador pegar a execução."""
    execucao = Execucao(
        automacao_id=automacao.id,
        estado="aguardando",
        entrada={"texto": entrada},
    )
    sessao.add(execucao)
    sessao.commit()
    sessao.refresh(execucao)
    return execucao


def rodar_execucao(sessao: Session, execucao: Execucao) -> Execucao:
    """Roda a cadeia de uma execução já reivindicada pelo trabalhador, gravando
    cada passo e o estado final (concluida, aguardando_humano ou falhou).
    Devolve a execução."""
    automacao = sessao.get(Automacao, execucao.automacao_id)
    entrada = (execucao.entrada or {}).get("texto", "")
    try:
        r = executar_cadeia(
            sessao,
            (automacao.cadeia if automacao else None) or {},
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
