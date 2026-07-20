"""Fila de TURNOS da IA criadora — a conversa roda em SEGUNDO PLANO.

Um turno da conversa pode levar MINUTOS (a IA raciocina e usa ferramentas em laço).
Antes, ele rodava DENTRO do `POST /mensagens` — uma requisição longa e bloqueante que
qualquer timeout de proxy ou oscilação de rede cortava no meio, sem resposta: a tela via
só um erro genérico e a mensagem se perdia. Agora o POST só ENFILEIRA (cria o turno
`aguardando`) e devolve na hora; um pool de trabalhadores aqui puxa e roda, publicando
`atividade` ao vivo ("o que a IA está fazendo agora") para a tela acompanhar com um
cronômetro — e, no fim, grava `concluido`+`resultado` ou `erro`+`erro_mensagem` HUMANA.

Espelha `fila.py` (execuções): reivindicação atômica (`FOR UPDATE SKIP LOCKED`),
recuperação de órfãos no boot e varredura periódica de turnos presos. A própria tabela
`turnos_criacao` é a fila — sem broker externo. A IA criadora é peça de BORDA; o núcleo
de orquestração congelado não é tocado.
"""

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from criacao.loop import MODELO_CRIADORA, responder_turno
from modelos import Automacao, ConversaCriacao, Organizacao, TurnoCriacao, Usuario
from observabilidade import contexto
from observabilidade.escritor import registrar_evento
from orquestracao import atividade
from sessao import CriadorDeSessao

# Quantos turnos rodam ao mesmo tempo (a rota garante ≤1 turno em voo por conversa, então
# são turnos de conversas DIFERENTES — seguros em paralelo).
N_TRABALHADORES = 2
# De quanto em quanto tempo um trabalhador ocioso reconfere a fila (s).
INTERVALO_OCIOSO_S = 1.0
# Teto de INATIVIDADE de um turno em andamento: se passa tanto tempo SEM atualizar a
# atividade (heartbeat = início OU última atividade publicada), o worker travou. Generoso:
# um turno legítimo com buscas/leituras jamais é morto; só o que ficou pendurado de verdade.
TETO_INATIVIDADE_TURNO_MIN = 10

logger = logging.getLogger("batuta.fila_turnos")

_acordar = threading.Event()  # cutucado a cada enfileiramento
_parar = threading.Event()
_threads: list[threading.Thread] = []


def enfileirar() -> None:
    """Sinaliza que há um turno novo — acorda os trabalhadores ociosos."""
    _acordar.set()


def _mensagem_humana(e: Exception) -> str:
    """Traduz uma falha do turno numa frase HUMANA e acionável (nunca stack trace).
    Sempre lembra que a mensagem foi preservada e pode ser reenviada."""
    texto = str(e).lower()
    if any(s in texto for s in ("overloaded", "529", "rate", "429", "quota", "capacity")):
        return (
            "A IA está sobrecarregada neste momento. Sua mensagem foi preservada — "
            "toque em Reenviar em instantes."
        )
    if any(s in texto for s in ("timeout", "timed out", "connection", "network", "conexao")):
        return (
            "A IA demorou demais para responder desta vez. Sua mensagem foi preservada — "
            "toque em Reenviar."
        )
    return (
        "Algo deu errado ao processar sua mensagem. Ela foi preservada — toque em "
        "Reenviar. Se continuar, me avise."
    )


def _escrever_atividade(turno_id: uuid.UUID, texto: str) -> None:
    """Publica a atividade ao vivo numa transação PRÓPRIA e curta (heartbeat), sem tocar
    a sessão do turno. Só grava se o turno ainda está `em_andamento`. Best-effort (o
    chamador em `atividade.registrar` engole erros)."""
    s = CriadorDeSessao()
    try:
        s.execute(
            update(TurnoCriacao)
            .where(TurnoCriacao.id == turno_id, TurnoCriacao.estado == "em_andamento")
            .values(
                atividade=(texto or "")[:200], atividade_em=datetime.now(timezone.utc)
            )
        )
        s.commit()
    finally:
        s.close()


def _reivindicar() -> uuid.UUID | None:
    """Pega atomicamente o próximo turno `aguardando` (FIFO) e o marca `em_andamento`,
    já publicando 'Pensando…'. Devolve o id, ou None se a fila está vazia. A trava de
    linha garante que dois trabalhadores não colidam."""
    sessao = CriadorDeSessao()
    try:
        tid = sessao.execute(
            select(TurnoCriacao.id)
            .where(TurnoCriacao.estado == "aguardando")
            .order_by(TurnoCriacao.criado_em)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).scalar()
        if tid is None:
            sessao.rollback()
            return None
        agora = datetime.now(timezone.utc)
        sessao.execute(
            update(TurnoCriacao)
            .where(TurnoCriacao.id == tid)
            .values(
                estado="em_andamento",
                iniciado_em=agora,
                atividade="Pensando…",
                atividade_em=agora,
            )
        )
        sessao.commit()
        return tid
    finally:
        sessao.close()


def _sincronizar_agendador(sessao: Session, conversa: ConversaCriacao) -> None:
    """Após o turno, a IA pode ter criado/ativado automações ou mudado gatilhos:
    (re)agenda TODAS as automações do time no relógio. Import tardio de `agendador`
    para evitar ciclo de import (agendador importa este módulo para a varredura)."""
    if not conversa.time_id:
        return
    import agendador

    for auto in sessao.scalars(
        select(Automacao)
        .where(Automacao.time_id == conversa.time_id)
        .order_by(Automacao.criado_em)
    ):
        agendador.sincronizar(auto)


def _marcar_erro(sessao: Session, turno_id: uuid.UUID, mensagem: str) -> None:
    """Depois de um rollback, relê o turno e grava a falha de forma VISÍVEL (nunca em
    silêncio) — com a mensagem humana e limpando a atividade ao vivo."""
    turno = sessao.get(TurnoCriacao, turno_id)
    if turno is None:
        return
    turno.estado = "erro"
    turno.erro_mensagem = mensagem
    turno.atividade = None
    turno.atividade_em = None
    turno.finalizado_em = datetime.now(timezone.utc)
    sessao.commit()


def executar_turno(sessao: Session, turno: TurnoCriacao) -> None:
    """Roda um turno já reivindicado, NA SESSÃO DADA (o worker é o dono da transação,
    como `disparo.rodar_execucao`). Resolve as chaves, roda a IA publicando atividade ao
    vivo, e grava `concluido`+`resultado` ou `erro`+`erro_mensagem`. Recebe a sessão
    explícita para ser testável (o worker de produção passa a sua própria)."""
    # Imports tardios: mantêm o topo do módulo leve e evitam ciclos.
    from chaves import ORIGEM_LEGADO, resolver_chaves_por_organizacao
    from orquestracao.modelos_ia import provedor_do_modelo

    conversa = sessao.get(ConversaCriacao, turno.conversa_id)
    if conversa is None:
        turno.estado = "erro"
        turno.erro_mensagem = "A conversa não existe mais."
        turno.atividade = None
        turno.atividade_em = None
        turno.finalizado_em = datetime.now(timezone.utc)
        sessao.commit()
        return
    turno_id = turno.id
    usuario = sessao.get(Usuario, turno.usuario_id) if turno.usuario_id else None
    # Fixa o contexto de log do turno (org/usuário/correlação) — o worker roda fora de um
    # request. `request_id` = id do turno, para correlacionar todos os seus eventos.
    with contexto.usar_contexto(
        origem="criacao",
        organizacao_id=conversa.organizacao_id,
        usuario_id=turno.usuario_id,
        request_id=str(turno_id),
    ):
        try:
            chaves, origens = resolver_chaves_por_organizacao(sessao, conversa.organizacao_id)
            org = sessao.get(Organizacao, conversa.organizacao_id)
            modelo = (org.modelo_criadora if org else None) or MODELO_CRIADORA
            origem = origens.get(provedor_do_modelo(modelo), ORIGEM_LEGADO)
            # `usar_atividade`: publica "o que a IA está fazendo agora" (as ferramentas
            # chamam `atividade.registrar` no wrapper `_serial`) numa sessão própria, para
            # a tela mostrar progresso mesmo num turno longo. Mesmo padrão do disparo.
            with atividade.usar_atividade(lambda t: _escrever_atividade(turno_id, t)):
                resultado = responder_turno(
                    sessao,
                    conversa,
                    turno.pergunta,
                    usuario=usuario,
                    chaves=chaves,
                    origem=origem,
                    modelo=modelo,
                )
            sessao.commit()
            _sincronizar_agendador(sessao, conversa)
            turno.estado = "concluido"
            turno.resultado = resultado
            turno.atividade = None
            turno.atividade_em = None
            turno.finalizado_em = datetime.now(timezone.utc)
            sessao.commit()
        except Exception as e:  # falha de LLM/rede/ferramenta — registra VISÍVEL e segue
            sessao.rollback()
            _marcar_erro(sessao, turno_id, _mensagem_humana(e))
            logger.exception("Turno %s falhou", turno_id)
            registrar_evento(
                categoria="criacao", acao="turno.falhou", nivel="error", resultado="falha",
                erro=e, recurso_tipo="turno_criacao", recurso_id=turno_id,
            )


def processar_turno(turno_id: uuid.UUID) -> None:
    """Entrada do worker: abre a PRÓPRIA sessão, carrega o turno reivindicado e o roda."""
    sessao = CriadorDeSessao()
    try:
        turno = sessao.get(TurnoCriacao, turno_id)
        if turno is not None:
            executar_turno(sessao, turno)
    finally:
        sessao.close()


def _ciclo_trabalhador(n: int) -> None:
    """Laço de um trabalhador: pega um turno e o roda; se a fila está vazia, espera ser
    cutucado (ou reconfere a cada INTERVALO_OCIOSO_S)."""
    while not _parar.is_set():
        try:
            tid = _reivindicar()
        except Exception:
            logger.exception("Trabalhador de turno %d falhou ao reivindicar", n)
            _parar.wait(INTERVALO_OCIOSO_S)
            continue

        if tid is None:
            _acordar.wait(INTERVALO_OCIOSO_S)
            _acordar.clear()
            continue

        try:
            processar_turno(tid)
        except Exception:
            logger.exception("Trabalhador de turno %d falhou ao rodar turno %s", n, tid)


def marcar_orfas(sessao: Session) -> int:
    """Turnos deixados `em_andamento` por um reinício do servidor não têm mais quem os
    rode: marca `erro`, de forma VISÍVEL, avisando que a mensagem foi preservada. Os
    `aguardando` seguem na fila. Devolve quantos recuperou."""
    r = sessao.execute(
        update(TurnoCriacao)
        .where(TurnoCriacao.estado == "em_andamento")
        .values(
            estado="erro",
            erro_mensagem=(
                "A resposta foi interrompida por um reinício do servidor. Sua mensagem "
                "foi preservada — é só reenviar."
            ),
            atividade=None,
            atividade_em=None,
            finalizado_em=datetime.now(timezone.utc),
        )
    )
    sessao.commit()
    return r.rowcount


def _recuperar_orfas() -> None:
    """Recuperação no BOOT: abre a própria sessão e marca as órfãs."""
    sessao = CriadorDeSessao()
    try:
        n = marcar_orfas(sessao)
        if n:
            logger.warning("%d turno(s) órfão(s) marcado(s) como erro no boot.", n)
            registrar_evento(
                categoria="criacao", acao="turno.orfaos_recuperados", nivel="warning",
                origem="boot", detalhe={"quantidade": n},
            )
    finally:
        sessao.close()


def recuperar_turnos_presos(sessao: Session) -> int:
    """Recuperação PERIÓDICA (agendador): turno `em_andamento` cujo worker travou SEM o
    processo reiniciar — o boot não o alcança. "Preso" = sem heartbeat além de
    TETO_INATIVIDADE_TURNO_MIN (heartbeat = última atividade OU início). Marca `erro`
    visível. Devolve quantos recuperou."""
    corte = datetime.now(timezone.utc) - timedelta(minutes=TETO_INATIVIDADE_TURNO_MIN)
    heartbeat = func.coalesce(TurnoCriacao.atividade_em, TurnoCriacao.iniciado_em)
    presos = sessao.scalars(
        select(TurnoCriacao).where(
            TurnoCriacao.estado == "em_andamento",
            heartbeat.is_not(None),
            heartbeat < corte,
        )
    ).all()
    agora = datetime.now(timezone.utc)
    for t in presos:
        t.estado = "erro"
        t.erro_mensagem = (
            "A IA demorou além do tempo limite e foi interrompida. Sua mensagem foi "
            "preservada — é só reenviar."
        )
        t.atividade = None
        t.atividade_em = None
        t.finalizado_em = agora
    if presos:
        sessao.commit()
        logger.warning("%d turno(s) preso(s) recuperado(s) (erro).", len(presos))
        registrar_evento(
            categoria="criacao", acao="turno.presos_recuperados", nivel="warning",
            detalhe={"quantidade": len(presos)},
        )
    return len(presos)


def varrer_presos_job() -> None:
    """Entrada do agendador: abre a própria sessão e recupera turnos presos."""
    sessao = CriadorDeSessao()
    try:
        recuperar_turnos_presos(sessao)
    finally:
        sessao.close()


def iniciar() -> None:
    """Recupera órfãos do boot anterior e sobe o pool de trabalhadores de turno."""
    _recuperar_orfas()
    _parar.clear()
    _threads.clear()
    for n in range(N_TRABALHADORES):
        t = threading.Thread(
            target=_ciclo_trabalhador, args=(n,), name=f"turno-{n}", daemon=True
        )
        t.start()
        _threads.append(t)
    _acordar.set()  # processa o que já estava aguardando
    logger.info("Fila de turnos no ar com %d trabalhador(es).", N_TRABALHADORES)


def desligar() -> None:
    """Pede para os trabalhadores pararem (são daemon; não bloqueia o shutdown)."""
    _parar.set()
    _acordar.set()
