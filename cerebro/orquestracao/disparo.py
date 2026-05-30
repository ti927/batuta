"""Disparo de uma automação — o ponto único onde uma execução nasce.

Todos os gatilhos (botão manual, agendamento/CRON, webhook de entrada) chegam
aqui: criam uma `Execucao`, rodam a cadeia sobre o LangGraph e gravam o
resultado. Cada chamador entra com sua própria sessão de banco — o botão usa a
sessão da requisição; o agendador e o webhook abrem uma sessão própria.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from modelos import Automacao, Execucao, PassoExecucao
from orquestracao.cadeia import executar_cadeia
from sessao import CriadorDeSessao

logger = logging.getLogger("batuta.disparo")


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
    """Cria o registro da execução (estado `em_andamento`) e devolve já com id.

    Separado de `rodar_execucao` para o disparo poder responder na hora (com o
    id) enquanto a cadeia roda em segundo plano — é o que permite a tela mostrar
    o progresso ao vivo (Tarefa 5.2)."""
    execucao = Execucao(
        automacao_id=automacao.id,
        estado="em_andamento",
        entrada={"texto": entrada},
        iniciada_em=datetime.now(timezone.utc),
    )
    sessao.add(execucao)
    sessao.commit()
    sessao.refresh(execucao)
    return execucao


def rodar_execucao(sessao: Session, execucao: Execucao) -> Execucao:
    """Roda a cadeia de uma execução já criada, gravando cada passo e o estado
    final (concluida, aguardando_humano ou falhou). Devolve a execução."""
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


def executar_automacao(
    sessao: Session, automacao: Automacao, entrada: str
) -> Execucao:
    """Cria e roda uma execução de ponta a ponta (síncrono). Usado por quem
    espera o resultado pronto: o gatilho de agendamento e o webhook.

    Não decide *quem* pode disparar nem checa o gatilho — apenas executa.
    """
    execucao = criar_execucao(sessao, automacao, entrada)
    return rodar_execucao(sessao, execucao)


def rodar_execucao_em_segundo_plano(execucao_id: uuid.UUID) -> None:
    """Roda uma execução já criada, numa sessão própria. É o que o disparo
    manual agenda como tarefa de fundo para responder na hora à tela."""
    sessao = CriadorDeSessao()
    try:
        execucao = sessao.get(Execucao, execucao_id)
        if execucao is None:
            return
        rodar_execucao(sessao, execucao)
    except Exception:  # rede/LLM já viram 'falhou' em rodar_execucao; isto é defesa
        logger.exception("Falha ao rodar execução em segundo plano %s", execucao_id)
    finally:
        sessao.close()
