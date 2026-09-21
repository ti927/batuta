"""Quem está mexendo numa execução AGORA — a trava que faltava (§4.1 de
`docs/FALHAS-DO-MOTOR.md`).

O problema que isto resolve. Uma espera por humano tem DUAS portas: a tela
(`POST /execucoes/{id}/responder`) e o canal (uma resposta no Telegram). Cada uma tinha a
sua própria trava e nenhuma enxergava a outra — a tela olhava `execucoes.estado`, o canal
marcava `conversas.estado = 'bot_respondendo'`. Em 2026-09-21 o maestro respondeu pelas
duas: às 15:18:28 pelo Telegram (turno que levou 184 s regenerando três imagens) e às
15:20:05 pela tela. As duas abriram o MESMO thread do LangGraph
(`{execucao.id}:{no_id}`, um endereço que as duas superfícies montam igual) e o checkpoint
BIFUROU — dois filhos do mesmo pai, o mesmo número de step. A tela leu o estado no meio de
três chamadas de ferramenta em voo, mandou à Anthropic um histórico com `tool_use` sem
`tool_result`, levou um 400, e uma execução de quase quatro horas morreu.

A regra, então, é uma só e vale para todas as portas: **quem vai mexer numa execução pega
o dono primeiro**. Quem não consegue recebe recusa honesta e não entra.

Duas decisões que valem explicar:

- **O dono é a SUPERFÍCIE (`tela`, `canal`, `fila`), não a pessoa.** Retomar pelo mesmo
  lugar é seguro e já é serializado por outros meios (a tela pelo estado da execução, o
  canal pelo estado da conversa, a fila pelo `FOR UPDATE SKIP LOCKED`). O que precisava de
  trava era o cruzamento entre superfícies — e um dono com nome de superfície é o que a
  tela consegue mostrar em português para quem clicou ("respondendo pelo Telegram…").

- **Todo dono tem PRAZO.** Um processo que morre segurando a trava não pode deixar a
  execução inacessível para sempre — seria trocar um caos por uma paralisia. Vencido o
  prazo, o próximo que chegar assume. Quem está trabalhando de verdade renova pelo mesmo
  sinal de vida que já publica na tela (`orquestracao/atividade`).
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from modelos import Execucao

logger = logging.getLogger("batuta.dono")

# Nomes de superfície. Fixos e poucos de propósito: é o vocabulário que aparece na tela e
# nas mensagens ao usuário, e um nome novo aqui é uma porta nova para a execução.
TELA = "tela"
CANAL = "canal"
FILA = "fila"

# Quanto tempo um dono vale sem renovar. Generoso: um turno de portão que gera três
# imagens levou 184 s no incidente que originou este módulo, e um vídeo pode levar 12 min.
# É o MESMO valor do teto de inatividade da fila (`fila.TETO_INATIVIDADE_EXEC_MIN`) por uma
# razão: os dois respondem à mesma pergunta — "a partir de quando assumimos que quem estava
# aqui morreu?". Duas respostas diferentes para a mesma pergunta viram divergência.
MINUTOS_PADRAO = 15

# Como cada superfície se apresenta a quem está do outro lado. O usuário não sabe o que é
# "canal": ele sabe que respondeu no Telegram.
_EM_PORTUGUES = {
    TELA: "pelo aplicativo",
    CANAL: "pelo Telegram",
    FILA: "em segundo plano",
}


def em_portugues(quem: str | None) -> str:
    """O nome da superfície como se diz a uma pessoa."""
    return _EM_PORTUGUES.get(quem or "", "em outro lugar")


class ExecucaoOcupada(Exception):
    """Outra superfície está mexendo nesta execução agora. `dono` diz qual."""

    def __init__(self, dono: str | None):
        self.dono = dono
        super().__init__(f"Execução ocupada por: {dono or 'desconhecido'}")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def tomar(
    sessao: Session, execucao_id, quem: str, *, minutos: int = MINUTOS_PADRAO
) -> bool:
    """Toma (ou renova) o dono desta execução. Devolve se conseguiu.

    É um UPDATE condicional ÚNICO — a atomicidade é do banco, não nossa. Consegue quem
    chega e encontra a execução livre, com dono vencido, ou já sua (renovação). Não comita:
    quem chama fecha a transação junto com o resto do seu trabalho."""
    agora = _agora()
    r = sessao.execute(
        update(Execucao)
        .where(Execucao.id == execucao_id)
        .where(
            (Execucao.dono.is_(None))
            | (Execucao.dono == quem)
            | (Execucao.dono_ate.is_(None))
            | (Execucao.dono_ate < agora)
        )
        .values(dono=quem, dono_ate=agora + timedelta(minutes=minutos))
    )
    return bool(r.rowcount)


def devolver(sessao: Session, execucao_id, quem: str) -> None:
    """Solta o dono, se ainda for de `quem`. Nunca rouba de outro: se o prazo venceu e
    alguém já assumiu, o trabalho daquele outro é que vale agora."""
    sessao.execute(
        update(Execucao)
        .where(Execucao.id == execucao_id)
        .where(Execucao.dono == quem)
        .values(dono=None, dono_ate=None)
    )


def quem_tem(sessao: Session, execucao_id) -> str | None:
    """Qual superfície está mexendo nesta execução agora, ou None se está livre. Dono com
    prazo vencido conta como livre — é o que a tela precisa saber para não mentir."""
    linha = sessao.execute(
        select(Execucao.dono, Execucao.dono_ate).where(Execucao.id == execucao_id)
    ).first()
    if linha is None or not linha.dono:
        return None
    if linha.dono_ate is not None and linha.dono_ate < _agora():
        return None
    return linha.dono


def renovar(sessao: Session, execucao_id, quem: str, *, minutos: int = MINUTOS_PADRAO) -> None:
    """Estica o prazo de quem já é dono. É o que o sinal de vida do trabalho em curso
    chama, para um passo legitimamente longo não perder a trava no meio."""
    sessao.execute(
        update(Execucao)
        .where(Execucao.id == execucao_id)
        .where(Execucao.dono == quem)
        .values(dono_ate=_agora() + timedelta(minutes=minutos))
    )


@contextmanager
def posse(sessao: Session, execucao_id, quem: str, *, minutos: int = MINUTOS_PADRAO):
    """Bloco que só roda se esta superfície conseguir o dono; solta ao sair, inclusive
    quando o bloco falha (senão uma exceção deixaria a execução trancada até o prazo).

    Levanta `ExecucaoOcupada` com o nome de quem está lá — o chamador transforma isso na
    recusa honesta que a pessoa lê."""
    if not tomar(sessao, execucao_id, quem, minutos=minutos):
        raise ExecucaoOcupada(quem_tem(sessao, execucao_id))
    try:
        yield
    finally:
        try:
            devolver(sessao, execucao_id, quem)
        except Exception:  # soltar a trava nunca pode mascarar o erro do bloco
            logger.exception("Falha ao devolver o dono da execução %s", execucao_id)
