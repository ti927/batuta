"""Testes do instrumento Enviar mensagem no Telegram — foco na PRECEDÊNCIA do destino.

Decisão do maestro (2026-06-25, exec `d179dd90`): o destinatário CONFIGURADO no
instrumento é a verdade — o que o agente escreve no texto dele (args) NÃO o substitui.
Só cai no `args.destinatario` quando o campo do instrumento está vazio (é exatamente o
caso da entrega conversacional da borda, que monta a config sem destino e passa o contato
em args — ver `mensageria/telegram.py`). Sem rede real (o POST é interceptado)."""

import pytest

from instrumentos.base import FalhaInstrumento
from instrumentos.enviar_telegram import ArgsTelegram, ConfigTelegram, EnviarTelegram


def _captura(monkeypatch, config: ConfigTelegram, args: ArgsTelegram) -> dict:
    """Roda o instrumento interceptando o POST; devolve {json, resultado}."""
    cap: dict = {}

    class _Resp:
        status_code = 200
        is_success = True

        def json(self):
            return {"ok": True, "result": {"message_id": 7}}

    class _Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):
            cap["json"] = json
            return _Resp()

    monkeypatch.setattr("instrumentos.enviar_telegram.httpx.Client", _Cliente)
    cap["resultado"] = EnviarTelegram().executar(config, args)
    return cap


def test_config_vence_o_markdown(monkeypatch):
    """Com destinatário configurado, o do agente (args) é IGNORADO — o config manda."""
    cap = _captura(
        monkeypatch,
        ConfigTelegram(token_bot="x", destinatario_padrao="CONFIG"),
        ArgsTelegram(destinatario="ARGS", mensagem="oi"),
    )
    assert cap["json"]["chat_id"] == "CONFIG"
    assert cap["resultado"]["ok"] is True


def test_sem_config_usa_o_do_agente(monkeypatch):
    """Campo do instrumento vazio → cai no que o agente informar (fallback)."""
    cap = _captura(
        monkeypatch,
        ConfigTelegram(token_bot="x", destinatario_padrao=""),
        ArgsTelegram(destinatario="ARGS", mensagem="oi"),
    )
    assert cap["json"]["chat_id"] == "ARGS"


def test_entrega_conversacional_usa_o_contato(monkeypatch):
    """A borda monta `ConfigTelegram(token_bot=token)` (destino vazio) e passa o contato
    em args — a inversão não pode misroteá-la. Aqui o contato deve prevalecer."""
    cap = _captura(
        monkeypatch,
        ConfigTelegram(token_bot="tok"),  # sem destinatario_padrao (como a borda monta)
        ArgsTelegram(destinatario="555-contato", mensagem="resposta"),
    )
    assert cap["json"]["chat_id"] == "555-contato"


def test_sem_nenhum_destino_falha(monkeypatch):
    """Sem destino no config nem no args → falha não-retentável (nada para onde mandar)."""
    with pytest.raises(FalhaInstrumento):
        _captura(
            monkeypatch,
            ConfigTelegram(token_bot="x", destinatario_padrao=""),
            ArgsTelegram(destinatario="", mensagem="oi"),
        )
