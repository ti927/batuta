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
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update

from modelos import Execucao, PassoExecucao
from observabilidade.escritor import registrar_evento
from orquestracao.disparo import rodar_execucao, rodar_retomada
from sessao import CriadorDeSessao

# Quantas execuções rodam ao mesmo tempo (limite de concorrência).
N_TRABALHADORES = 3
# De quanto em quanto tempo um trabalhador ocioso reconfere a fila (s).
INTERVALO_OCIOSO_S = 1.0
# Teto de INATIVIDADE de uma execução em andamento: se ela passa tanto tempo SEM
# concluir nenhum passo novo (heartbeat = início OU último passo concluído), o
# worker que a roda travou (chamada externa pendurada, sem restart do processo —
# que o boot já recuperaria). Generoso de propósito: um passo lento (geração de
# imagem ~2min + rodadas do agente) jamais é morto; só o que travou de verdade.
TETO_INATIVIDADE_EXEC_MIN = 15

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
                # Uma execução reivindicada é uma RETOMADA de portão (aprovação em segundo
                # plano, §12-A) quando tem `retomada_resposta`; senão é um disparo do zero.
                if execucao.retomada_resposta is not None:
                    rodar_retomada(sessao, execucao)
                else:
                    rodar_execucao(sessao, execucao)
                logger.info(
                    "Trabalhador %d concluiu execução %s (%s)", n, eid, execucao.estado
                )
        except Exception as e:
            logger.exception("Trabalhador %d falhou ao rodar execução %s", n, eid)
            registrar_evento(
                categoria="fila", acao="worker.falhou", nivel="error", resultado="falha",
                erro=e, recurso_tipo="execucao", recurso_id=eid,
            )
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
            registrar_evento(
                categoria="fila", acao="execucao.orfas_recuperadas", nivel="warning",
                origem="boot", detalhe={"quantidade": r.rowcount},
            )
    finally:
        sessao.close()


def recuperar_execucoes_presas(sessao) -> int:
    """Recuperação PERIÓDICA (roda no agendador): execução `em_andamento` cujo
    worker travou SEM o processo reiniciar — o boot (`_recuperar_orfas`) não a
    alcança. "Travada" = sem progresso (heartbeat) além de `TETO_INATIVIDADE_EXEC_MIN`.

    O heartbeat é o instante MAIS RECENTE entre o início desta reivindicação
    (`iniciada_em`) e o último passo concluído — assim uma cadeia longa que vai
    concluindo passos NUNCA é morta; só morre o que ficou pendurado dentro de um passo
    além do teto. `iniciada_em` é reescrito a CADA reivindicação, INCLUSIVE na RETOMADA
    de um portão: por isso uma execução que ficou horas `aguardando_humano` e acabou de
    ser aprovada NÃO pode morrer no instante da retomada só porque o último passo
    (anterior à espera) é antigo. Marca `falhou` de forma visível. Devolve quantas
    recuperou."""
    corte = datetime.now(timezone.utc) - timedelta(minutes=TETO_INATIVIDADE_EXEC_MIN)
    ultimo_passo = (
        select(func.max(PassoExecucao.finalizado_em))
        .where(PassoExecucao.execucao_id == Execucao.id)
        .correlate(Execucao)
        .scalar_subquery()
    )
    # "Presa" só quando OS DOIS sinais de progresso são antigos: o início desta
    # reivindicação E o último passo concluído. Como a retomada de um portão reescreve
    # `iniciada_em` para AGORA, a condição `iniciada_em < corte` fica falsa e a execução
    # recém-retomada sobrevive — antes, o `coalesce(último_passo, …)` preferia o passo
    # anterior à espera e matava a execução no exato instante em que o humano aprovava.
    presas = sessao.scalars(
        select(Execucao).where(
            Execucao.estado == "em_andamento",
            Execucao.iniciada_em.is_not(None),
            Execucao.iniciada_em < corte,
            func.coalesce(ultimo_passo, Execucao.iniciada_em) < corte,
        )
    ).all()
    agora = datetime.now(timezone.utc)
    for ex in presas:
        ex.estado = "falhou"
        ex.resultado = {
            "erro": "Execução travada (sem progresso além do tempo limite) — "
            "interrompida automaticamente pelo Batuta."
        }
        ex.finalizada_em = agora
    if presas:
        sessao.commit()
        logger.warning("%d execução(ões) presa(s) recuperada(s) (falhou).", len(presas))
        registrar_evento(
            categoria="fila", acao="execucao.presas_recuperadas", nivel="warning",
            detalhe={"quantidade": len(presas)},
        )
    return len(presas)


def varrer_presas_job() -> None:
    """Entrada do agendador: abre a própria sessão e recupera execuções presas."""
    sessao = CriadorDeSessao()
    try:
        recuperar_execucoes_presas(sessao)
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
