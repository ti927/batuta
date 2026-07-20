"""Agendador de gatilhos por horário (CRON) — Tarefa 4.7.

Mantém um relógio em memória (APScheduler) que dispara as automações de gatilho
'agendamento' no horário definido. O banco é a fonte da verdade: ao subir, o
relógio é reconstruído a partir das automações; a cada criação/edição/remoção,
é re-sincronizado. Só automações marcadas `ativa` entram no relógio.

O horário é interpretado no fuso de Brasília (os exemplos do PRODUTO — "todo dia
15", "toda segunda às 8h" — são do Brasil).
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_, delete, or_, select

import fila
import fila_turnos
from modelos import Agendamento, Automacao, Credencial, EventoLog
from orquestracao.disparo import criar_execucao
from sessao import CriadorDeSessao

FUSO = "America/Sao_Paulo"
TIPO_AGENDAMENTO = "agendamento"
_DIAS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # índice 0 = segunda

logger = logging.getLogger("batuta.agendador")

_scheduler = BackgroundScheduler(timezone=FUSO)


def _trigger_da_config(config: dict) -> CronTrigger:
    """Traduz o formulário guiado da tela num CronTrigger.

    config = {frequencia: 'diaria'|'semanal'|'mensal', hora: 0-23,
              minuto: 0-59, dia_semana: 0-6 (0=segunda, só semanal),
              dia_mes: 1-31 (só mensal)}.

    O `timezone=FUSO` é OBRIGATÓRIO e explícito: um CronTrigger criado SEM fuso
    NÃO herda o fuso do scheduler — ele cai no fuso do SISTEMA OPERACIONAL
    (`get_localzone()`). No container do Railway o SO é UTC, então "8h" virava 8h
    UTC = 5h BRT (a máquina de dev fica em BRT, por isso o bug não aparecia no QA
    local). Com o fuso explícito, "8h" é sempre 8h de Brasília, em qualquer host.
    """
    frequencia = config.get("frequencia", "diaria")
    hora = int(config.get("hora", 0))
    minuto = int(config.get("minuto", 0))
    if frequencia == "semanal":
        dia = _DIAS[int(config.get("dia_semana", 0)) % 7]
        return CronTrigger(day_of_week=dia, hour=hora, minute=minuto, timezone=FUSO)
    if frequencia == "mensal":
        dia_mes = int(config.get("dia_mes", 1))
        return CronTrigger(day=dia_mes, hour=hora, minute=minuto, timezone=FUSO)
    return CronTrigger(hour=hora, minute=minuto, timezone=FUSO)  # diaria


def _rodar(automacao_id_str: str) -> None:
    """Job do relógio: abre sessão própria, recarrega a automação e dispara.

    Recarrega do banco a cada disparo (em vez de fechar sobre o objeto antigo)
    porque a definição pode ter mudado desde o agendamento.
    """
    sessao = CriadorDeSessao()
    try:
        auto = sessao.get(Automacao, uuid.UUID(automacao_id_str))
        if auto is None or not auto.ativa or auto.tipo_gatilho != TIPO_AGENDAMENTO:
            return  # desativada/removida/trocou de gatilho — não dispara
        entrada = (auto.configuracao_gatilho or {}).get("entrada") or ""
        criar_execucao(sessao, auto, entrada, origem="agendamento")  # enfileira; a fila roda
        fila.enfileirar()
        logger.info("Automação agendada %s enfileirada.", automacao_id_str)
    except Exception:
        logger.exception("Falha ao rodar automação agendada %s", automacao_id_str)
    finally:
        sessao.close()


def sincronizar(automacao: Automacao) -> None:
    """Registra/atualiza/remove o job de uma automação conforme seu gatilho.

    Chamado após cada criar/editar. Só vira job se for 'agendamento' E `ativa`;
    caso contrário, garante que nenhum job remanescente fique no relógio.
    """
    job_id = str(automacao.id)
    eh_agendada = automacao.ativa and automacao.tipo_gatilho == TIPO_AGENDAMENTO
    if not eh_agendada:
        remover(automacao.id)
        return
    _scheduler.add_job(
        _rodar,
        trigger=_trigger_da_config(automacao.configuracao_gatilho or {}),
        args=[job_id],
        id=job_id,
        replace_existing=True,
    )
    logger.info("Automação %s agendada (%s).", job_id, automacao.configuracao_gatilho)


def remover(automacao_id: uuid.UUID) -> None:
    """Tira do relógio o job de uma automação, se existir."""
    job_id = str(automacao_id)
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)


# ─────────────── Renovação dos tokens do Instagram (Fase 1) ───────────────
# O token de longa duração do Instagram dura ~60 dias e precisa ser renovado
# antes de expirar (a Meta só renova token com ≥24h e <60 dias de vida). Janela
# de 10 dias: renova bem antes do fim, com folga para retentar nos dias seguintes
# se um refresh oscilar.
JANELA_REFRESH_IG_DIAS = 10


def renovar_tokens_instagram(sessao) -> int:
    """Renova as credenciais `instagram` cujo token está perto de expirar.

    Commit por credencial (uma falha não derruba as outras). Devolve quantas
    foram renovadas. É a única escrita pelo SISTEMA no cofre (via
    `credenciais_cofre.gravar_token_renovado`)."""
    import credenciais_cofre
    import instagram_tokens

    corte = datetime.now(timezone.utc) + timedelta(days=JANELA_REFRESH_IG_DIAS)
    alvos = sessao.scalars(
        select(Credencial).where(
            Credencial.tipo == "instagram",
            Credencial.expira_em.is_not(None),
            Credencial.expira_em <= corte,
        )
    ).all()
    renovadas = 0
    for cred in alvos:
        try:
            atual = credenciais_cofre.decifrar(cred).get("token", "")
            if not atual:
                continue
            res = instagram_tokens.renovar(atual)
            credenciais_cofre.gravar_token_renovado(
                cred, res["token"], res["expira_em"]
            )
            sessao.commit()
            renovadas += 1
        except Exception:
            sessao.rollback()
            logger.exception(
                "Falha ao renovar token Instagram da credencial %s", cred.id
            )
    return renovadas


def _refresh_instagram_job() -> None:
    """Entrada do agendador: abre a própria sessão e renova os tokens vencendo."""
    sessao = CriadorDeSessao()
    try:
        renovar_tokens_instagram(sessao)
    finally:
        sessao.close()


# ─────────────── Agendamentos únicos (disparo futuro por um agente) ───────────────
# Um agente cria uma linha `pendente` em `agendamentos` (instrumento agendar_automacao);
# este sweeper dispara os vencidos. Aditivo, na borda — o núcleo não conhece a tabela.
LIMITE_POR_VARREDURA = 100


def varrer_agendamentos(sessao) -> int:
    """Dispara os agendamentos VENCIDOS (`pendente` com `quando_executar` já passado):
    cria a execução da automação-alvo e marca `enfileirado`. Alvo ausente/inativo →
    `cancelado` (visível, nunca em silêncio). CLAIM-FIRST (marca antes de criar) para
    NUNCA disparar em dobro — no pior caso (falha após o claim) perde-se um disparo, que
    é preferível a duplicar. Devolve quantos disparou."""
    agora = datetime.now(timezone.utc)
    pendentes = sessao.scalars(
        select(Agendamento)
        .where(
            Agendamento.estado == "pendente",
            Agendamento.quando_executar <= agora,
        )
        .order_by(Agendamento.quando_executar)
        .limit(LIMITE_POR_VARREDURA)
    ).all()
    disparados = 0
    for ag in pendentes:
        auto = sessao.get(Automacao, ag.automacao_id)
        if auto is None or not auto.ativa:
            ag.estado = "cancelado"
            # Motivo HUMANO (nunca em silêncio, §12-A) — a aba "Agendadas" mostra.
            ag.motivo = (
                "A automação-alvo foi removida."
                if auto is None
                else "A automação-alvo estava desativada (em repouso) quando chegou a hora. "
                "Ative-a para os próximos agendamentos dispararem."
            )
            sessao.commit()
            logger.warning(
                "Agendamento %s cancelado: automação-alvo ausente/inativa.", ag.id
            )
            continue
        try:
            ag.estado = "enfileirado"  # claim: não re-processa nesta nem na próxima varredura
            sessao.commit()
            execucao = criar_execucao(sessao, auto, ag.entrada or "", origem="agendamento")
            ag.execucao_id = execucao.id
            sessao.commit()
            fila.enfileirar()
            disparados += 1
            logger.info(
                "Agendamento %s disparou a execução %s da automação %s.",
                ag.id, execucao.id, ag.automacao_id,
            )
        except Exception:
            sessao.rollback()
            logger.exception("Falha ao disparar o agendamento %s", ag.id)
    return disparados


def _varrer_agendamentos_job() -> None:
    """Entrada do agendador: abre a própria sessão e dispara os agendamentos vencidos."""
    sessao = CriadorDeSessao()
    try:
        varrer_agendamentos(sessao)
    finally:
        sessao.close()


# ─────────────── Poda do banco de logs (observabilidade) ───────────────
# Mantém a tabela `evento_log` enxuta no Postgres compartilhado: eventos rotineiros
# (info/warning) vivem pouco; erros ficam bem mais tempo para diagnóstico tardio.
RETENCAO_INFO_DIAS = 14
RETENCAO_ERRO_DIAS = 90
LIMITE_PODA_LOTE = 5000


def podar_evento_log(sessao) -> int:
    """Apaga eventos vencidos do banco de logs, em LOTES (não trava o Postgres). Devolve
    o total removido. info/warning além de RETENCAO_INFO_DIAS; error/critical além de
    RETENCAO_ERRO_DIAS."""
    agora = datetime.now(timezone.utc)
    corte_info = agora - timedelta(days=RETENCAO_INFO_DIAS)
    corte_erro = agora - timedelta(days=RETENCAO_ERRO_DIAS)
    graves = ["error", "critical"]
    total = 0
    while True:
        ids = sessao.scalars(
            select(EventoLog.id)
            .where(
                or_(
                    and_(EventoLog.nivel.notin_(graves), EventoLog.criado_em < corte_info),
                    and_(EventoLog.nivel.in_(graves), EventoLog.criado_em < corte_erro),
                )
            )
            .limit(LIMITE_PODA_LOTE)
        ).all()
        if not ids:
            break
        sessao.execute(delete(EventoLog).where(EventoLog.id.in_(ids)))
        sessao.commit()
        total += len(ids)
        if len(ids) < LIMITE_PODA_LOTE:
            break
    if total:
        logger.info("Poda do banco de logs: %d evento(s) removido(s).", total)
    return total


def _podar_evento_log_job() -> None:
    """Entrada do agendador: abre a própria sessão e poda o banco de logs."""
    sessao = CriadorDeSessao()
    try:
        podar_evento_log(sessao)
    finally:
        sessao.close()


def iniciar() -> None:
    """Sobe o relógio e reconstrói os jobs a partir do banco."""
    sessao = CriadorDeSessao()
    try:
        agendadas = sessao.scalars(
            select(Automacao).where(
                Automacao.tipo_gatilho == TIPO_AGENDAMENTO,
                Automacao.ativa.is_(True),
            )
        ).all()
        for auto in agendadas:
            sincronizar(auto)
    finally:
        sessao.close()
    # Vigia de inatividade das conversas (mensageria, Fase J): roda a cada minuto.
    from mensageria import sweeper

    _scheduler.add_job(
        sweeper.varrer_job,
        trigger=IntervalTrigger(seconds=60),
        id="mensageria_sweeper",
        replace_existing=True,
    )
    # Renovação diária dos tokens de longa duração do Instagram (Fase 1), de
    # madrugada (BRT) fora do horário comercial.
    _scheduler.add_job(
        _refresh_instagram_job,
        trigger=CronTrigger(hour=3, minute=30, timezone=FUSO),
        id="instagram_token_refresh",
        replace_existing=True,
    )
    # Recuperação periódica de execuções presas em `em_andamento` (worker travado
    # sem reinício do processo — que o boot já recuperaria). Complementa o
    # `fila._recuperar_orfas` do boot; usa heartbeat (não mata cadeia em progresso).
    _scheduler.add_job(
        fila.varrer_presas_job,
        trigger=IntervalTrigger(seconds=120),
        id="execucao_sweeper",
        replace_existing=True,
    )
    # Recuperação periódica de TURNOS da IA criadora presos em `em_andamento` (worker
    # travado sem reinício). Espelha o sweeper de execuções; usa heartbeat de atividade
    # (não mata turno em progresso). Complementa o `fila_turnos._recuperar_orfas` do boot.
    _scheduler.add_job(
        fila_turnos.varrer_presos_job,
        trigger=IntervalTrigger(seconds=120),
        id="turno_criacao_sweeper",
        replace_existing=True,
    )
    # Disparo dos agendamentos únicos vencidos (instrumento agendar_automacao), a
    # cada minuto. Borda: o núcleo não conhece a tabela `agendamentos`.
    _scheduler.add_job(
        _varrer_agendamentos_job,
        trigger=IntervalTrigger(seconds=60),
        id="agendamentos_sweeper",
        replace_existing=True,
    )
    # Poda diária do banco de logs (observabilidade), de madrugada (BRT), fora do pico.
    _scheduler.add_job(
        _podar_evento_log_job,
        trigger=CronTrigger(hour=4, minute=15, timezone=FUSO),
        id="poda_evento_log",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()
    logger.info("Agendador no ar com %d job(s).", len(_scheduler.get_jobs()))


def desligar() -> None:
    """Desliga o relógio (no encerramento do app)."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
