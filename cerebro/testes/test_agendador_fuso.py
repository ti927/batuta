"""Testes do fuso dos gatilhos agendados (CRON).

Regressão de um bug real (exec 3f23b861): uma automação "toda segunda às 8h"
disparou às 5h em produção. Causa: o `CronTrigger` era criado SEM `timezone=`,
então o APScheduler não usava o fuso do scheduler — caía no fuso do SISTEMA
OPERACIONAL. No container do Railway (UTC), "8h" virava 8h UTC = 5h BRT. Na
máquina de dev (BRT) o bug não aparecia, mascarando o problema.

Estes testes FORÇAM o cenário do servidor (SO em UTC) e provam que o horário é
sempre interpretado no fuso de Brasília, em qualquer host.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import apscheduler.triggers.cron as cronmod

import agendador

BRT = ZoneInfo("America/Sao_Paulo")


def _proximo(trigger, *, agora_brt: datetime) -> datetime:
    """Próximo disparo do trigger, sempre devolvido em BRT para conferência."""
    prox = trigger.get_next_fire_time(None, agora_brt)
    return prox.astimezone(BRT)


def _simula_so_utc(monkeypatch):
    """Faz `get_localzone()` (usado pelo CronTrigger sem fuso) devolver UTC —
    reproduz o container de produção, onde o bug se manifestava."""
    monkeypatch.setattr(cronmod, "get_localzone", lambda: timezone.utc)


def test_semanal_dispara_no_horario_de_brasilia_mesmo_com_so_em_utc(monkeypatch):
    _simula_so_utc(monkeypatch)
    cfg = {"frequencia": "semanal", "dia_semana": 0, "hora": 8, "minuto": 0}
    trigger = agendador._trigger_da_config(cfg)
    # Domingo à noite (BRT): o próximo é a segunda às 8h BRT.
    domingo = datetime(2026, 6, 21, 23, 0, tzinfo=BRT)
    prox = _proximo(trigger, agora_brt=domingo)
    assert (prox.weekday(), prox.hour, prox.minute) == (0, 8, 0)  # segunda 08:00 BRT
    # E em UTC isso é 11h — NÃO 8h (que seria o bug).
    assert prox.astimezone(timezone.utc).hour == 11


def test_diaria_dispara_no_horario_de_brasilia_mesmo_com_so_em_utc(monkeypatch):
    _simula_so_utc(monkeypatch)
    trigger = agendador._trigger_da_config({"frequencia": "diaria", "hora": 15, "minuto": 30})
    base = datetime(2026, 6, 22, 0, 0, tzinfo=BRT)
    prox = _proximo(trigger, agora_brt=base)
    assert (prox.hour, prox.minute) == (15, 30)
    assert prox.utcoffset().total_seconds() == -3 * 3600  # carimbado em BRT


def test_mensal_dispara_no_horario_de_brasilia_mesmo_com_so_em_utc(monkeypatch):
    _simula_so_utc(monkeypatch)
    trigger = agendador._trigger_da_config(
        {"frequencia": "mensal", "dia_mes": 10, "hora": 9, "minuto": 0}
    )
    base = datetime(2026, 6, 1, 0, 0, tzinfo=BRT)
    prox = _proximo(trigger, agora_brt=base)
    assert (prox.day, prox.hour, prox.minute) == (10, 9, 0)


def test_trigger_carrega_o_fuso_de_brasilia_explicito():
    """O trigger nasce com o fuso explícito — não depende do SO nem da ordem de
    construção do scheduler."""
    trigger = agendador._trigger_da_config({"frequencia": "diaria", "hora": 8})
    assert str(trigger.timezone) == "America/Sao_Paulo"
