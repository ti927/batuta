"""Saída pelo Telegram (Passo 4).

A chamada real à Bot API exige um bot do BotFather; aqui ela é mockada. Provam o
formato da chamada (`/bot<token>/sendMessage` + chat_id/text), o erro claro sem
token e quando o Telegram recusa, e o serviço de borda que resolve o token do
cofre e registra a saída em `mensagens_canal`.
"""

import pytest
from sqlalchemy import select

import canais.telegram as tg
from canais import servico
from canais.base import FalhaCanal
from canais.telegram import CanalTelegram, ConfigTelegram
from modelos import Canal, MensagemCanal
from segredos_canal import salvar_segredos


class _RespOK:
    status_code = 200

    def json(self):
        return {"ok": True, "result": {"message_id": 42}}


class _ClienteCaptura:
    """Captura a última chamada e devolve sucesso (substitui httpx.Client)."""

    chamadas: list[tuple[str, dict]] = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None, **k):
        _ClienteCaptura.chamadas.append((url, json))
        return _RespOK()


class _RespErro:
    status_code = 400

    def json(self):
        return {"ok": False, "description": "chat not found"}


class _ClienteErro(_ClienteCaptura):
    def post(self, url, json=None, **k):
        return _RespErro()


@pytest.fixture(autouse=True)
def _limpar_capturas():
    _ClienteCaptura.chamadas = []
    yield


def test_enviar_monta_chamada_da_bot_api(monkeypatch):
    monkeypatch.setattr(tg.httpx, "Client", _ClienteCaptura)
    r = CanalTelegram().enviar(
        ConfigTelegram(token="123:ABCtoken"), "chat-9", "olá mundo"
    )
    assert r == {"ok": True, "id_mensagem": 42}
    url, corpo = _ClienteCaptura.chamadas[-1]
    assert url == "https://api.telegram.org/bot123:ABCtoken/sendMessage"
    assert corpo == {"chat_id": "chat-9", "text": "olá mundo"}


def test_enviar_sem_token_falha():
    with pytest.raises(FalhaCanal, match="token"):
        CanalTelegram().enviar(ConfigTelegram(), "chat-9", "oi")


def test_enviar_erro_do_telegram_vira_falha(monkeypatch):
    monkeypatch.setattr(tg.httpx, "Client", _ClienteErro)
    with pytest.raises(FalhaCanal, match="chat not found"):
        CanalTelegram().enviar(ConfigTelegram(token="123:ABC"), "x", "oi")


def test_servico_resolve_token_do_cofre_e_registra_saida(monkeypatch, sessao, dados):
    monkeypatch.setattr(tg.httpx, "Client", _ClienteCaptura)
    canal = Canal(
        organizacao_id=dados["orgA"].id, tipo="telegram", nome="Tg", config={}, ativo=True
    )
    sessao.add(canal)
    sessao.flush()
    salvar_segredos(sessao, canal.id, {"token": "BOT:DOCOFRE"})

    r = servico.enviar_pelo_canal(sessao, canal, "chat-123", "do cofre")
    assert r["ok"] is True
    # O token veio do cofre (apareceu na URL da Bot API).
    url, corpo = _ClienteCaptura.chamadas[-1]
    assert "botBOT:DOCOFRE/sendMessage" in url
    assert corpo == {"chat_id": "chat-123", "text": "do cofre"}
    # A saída foi registrada no log.
    msg = sessao.scalars(
        select(MensagemCanal).where(MensagemCanal.canal_id == canal.id)
    ).first()
    assert msg is not None
    assert msg.direcao == "saida"
    assert msg.identificador_externo == "chat-123"
    assert msg.texto == "do cofre"


# ───────────────────────── normalização da entrada ───────────────────────────


def test_normalizar_mensagem_de_texto():
    m = CanalTelegram().normalizar(
        {"update_id": 100, "message": {"chat": {"id": 5175352629}, "text": "alou"}}
    )
    assert m is not None
    assert m.identificador_externo == "5175352629"
    assert m.texto == "alou"
    assert m.id_externo == "100"
    assert m.anexos == []


def test_normalizar_foto_vira_anexo_imagem():
    m = CanalTelegram().normalizar(
        {
            "update_id": 101,
            "message": {
                "chat": {"id": 9},
                "caption": "meu recibo",
                "photo": [
                    {"file_id": "pequena", "width": 90},
                    {"file_id": "grande", "width": 1280},
                ],
            },
        }
    )
    assert m is not None
    assert m.texto == "meu recibo"
    assert len(m.anexos) == 1
    assert m.anexos[0].tipo == "imagem"
    assert m.anexos[0].ref == "grande"  # a maior resolução


def test_normalizar_ignora_evento_sem_mensagem():
    assert CanalTelegram().normalizar({"update_id": 1, "callback_query": {}}) is None
    assert CanalTelegram().normalizar({"foo": "bar"}) is None


def test_configurar_webhook_chama_setwebhook(monkeypatch):
    monkeypatch.setattr(tg.httpx, "Client", _ClienteCaptura)
    CanalTelegram().configurar_webhook(
        ConfigTelegram(token="123:ABC"), "https://api.batuta.team/canais/x/webhook"
    )
    url, corpo = _ClienteCaptura.chamadas[-1]
    assert url == "https://api.telegram.org/bot123:ABC/setWebhook"
    assert corpo == {"url": "https://api.batuta.team/canais/x/webhook"}
