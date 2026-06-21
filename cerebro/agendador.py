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
from sqlalchemy import select

import fila
from modelos import Automacao, Credencial
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
              dia_mes: 1-31 (só mensal)}. O fuso vem do scheduler.
    """
    frequencia = config.get("frequencia", "diaria")
    hora = int(config.get("hora", 0))
    minuto = int(config.get("minuto", 0))
    if frequencia == "semanal":
        dia = _DIAS[int(config.get("dia_semana", 0)) % 7]
        return CronTrigger(day_of_week=dia, hour=hora, minute=minuto)
    if frequencia == "mensal":
        dia_mes = int(config.get("dia_mes", 1))
        return CronTrigger(day=dia_mes, hour=hora, minute=minuto)
    return CronTrigger(hour=hora, minute=minuto)  # diaria


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
        criar_execucao(sessao, auto, entrada)  # enfileira; a fila roda
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
        trigger=CronTrigger(hour=3, minute=30),
        id="instagram_token_refresh",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()
    logger.info("Agendador no ar com %d job(s).", len(_scheduler.get_jobs()))


def desligar() -> None:
    """Desliga o relógio (no encerramento do app)."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
