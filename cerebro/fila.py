"""Fila de execuções e pool de trabalhadores — Tarefa 5.3 (PRODUTO §18).

Muitas tarefas podem ser disparadas ao mesmo tempo (dia 15, dia 1º). Em vez de
rodar todas de uma vez (e socar a LLM / travar), o disparo só **enfileira** —
cria a execução no estado `aguardando`. Um pool de N trabalhadores dentro do
cérebro puxa as execuções em ordem (FIFO), no máximo N ao mesmo tempo; o resto
espera. A própria tabela `execucoes` é a fila — sem broker externo.

A reivindicação usa `FOR UPDATE SKIP LOCKED` do Postgres: dois trabalhadores
nunca pegam a mesma execução, e nenhum fica esperando o outro.
"""

import logging
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from modelos import Execucao
from orquestracao.disparo import rodar_execucao
from sessao import CriadorDeSessao

# Quantas execuções rodam ao mesmo tempo (limite de concorrência).
N_TRABALHADORES = 3
# De quanto em quanto tempo um trabalhador ocioso reconfere a fila (s).
INTERVALO_OCIOSO_S = 1.0

logger = logging.getLogger("batuta.fila")

_acordar = threading.Event()  # cutucado a cada enfileiramento
_parar = threading.Event()
_threads: list[threading.Thread] = []


def enfileirar() -> None:
    """Sinaliza que há trabalho novo — acorda os trabalhadores ociosos."""
    _acordar.set()


def _reivindicar() -> uuid.UUID | None:
    """Pega atomicamente a próxima execução `aguardando` (FIFO) e a marca
    `em_andamento`, registrando o início. Devolve o id, ou None se a fila
    está vazia. A trava de linha garante que dois trabalhadores não colidam."""
    sessao = CriadorDeSessao()
    try:
        eid = sessao.execute(
            select(Execucao.id)
            .where(Execucao.estado == "aguardando")
            .order_by(Execucao.criado_em)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).scalar()
        if eid is None:
            sessao.rollback()
            return None
        sessao.execute(
            update(Execucao)
            .where(Execucao.id == eid)
            .values(estado="em_andamento", iniciada_em=datetime.now(timezone.utc))
        )
        sessao.commit()
        return eid
    finally:
        sessao.close()


def _ciclo_trabalhador(n: int) -> None:
    """Laço de um trabalhador: pega uma execução e a roda; se a fila está vazia,
    espera ser cutucado (ou reconfere a cada INTERVALO_OCIOSO_S)."""
    while not _parar.is_set():
        try:
            eid = _reivindicar()
        except Exception:
            logger.exception("Trabalhador %d falhou ao reivindicar", n)
            _parar.wait(INTERVALO_OCIOSO_S)
            continue

        if eid is None:
            _acordar.wait(INTERVALO_OCIOSO_S)
            _acordar.clear()
            continue

        sessao = CriadorDeSessao()
        try:
            execucao = sessao.get(Execucao, eid)
            if execucao is not None:
                rodar_execucao(sessao, execucao)
                logger.info(
                    "Trabalhador %d concluiu execução %s (%s)", n, eid, execucao.estado
                )
        except Exception:
            logger.exception("Trabalhador %d falhou ao rodar execução %s", n, eid)
        finally:
            sessao.close()


def _recuperar_orfas() -> None:
    """Execuções deixadas `em_andamento` por um reinício do servidor não têm
    mais quem as rode: marca `falhou`, de forma visível (nunca em silêncio).
    As pausadas (`aguardando_humano`) e enfileiradas (`aguardando`) seguem
    intactas — serão retomadas/processadas normalmente."""
    sessao = CriadorDeSessao()
    try:
        r = sessao.execute(
            update(Execucao)
            .where(Execucao.estado == "em_andamento")
            .values(
                estado="falhou",
                resultado={"erro": "Execução interrompida por reinício do servidor."},
                finalizada_em=datetime.now(timezone.utc),
            )
        )
        sessao.commit()
        if r.rowcount:
            logger.warning(
                "%d execução(ões) órfã(s) marcada(s) como falhou no boot.", r.rowcount
            )
    finally:
        sessao.close()


def iniciar() -> None:
    """Recupera órfãs do boot anterior e sobe o pool de trabalhadores."""
    _recuperar_orfas()
    _parar.clear()
    _threads.clear()
    for n in range(N_TRABALHADORES):
        t = threading.Thread(
            target=_ciclo_trabalhador, args=(n,), name=f"fila-{n}", daemon=True
        )
        t.start()
        _threads.append(t)
    _acordar.set()  # processa o que já estava aguardando
    logger.info("Fila no ar com %d trabalhador(es).", N_TRABALHADORES)


def desligar() -> None:
    """Pede para os trabalhadores pararem (são daemon; não bloqueia o shutdown)."""
    _parar.set()
    _acordar.set()
