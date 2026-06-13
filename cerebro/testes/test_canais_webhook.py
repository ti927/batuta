"""Webhook de entrada do canal (Passo 5).

O endpoint é público (o Telegram chama sem login), idempotente e tolerante.
Provam: registra a mensagem recebida; deduplica updates repetidos; ignora canal
inativo / evento sem mensagem; e o endpoint admin que registra o webhook no
provedor (setWebhook mockado).
"""

from sqlalchemy import select

import canais.telegram as tg
from modelos import Canal, MensagemCanal
from segredos_canal import salvar_segredos


def _update(update_id, chat_id="5175352629", texto="alou"):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": texto}}


def _canal(sessao, org_id, ativo=True):
    canal = Canal(
        organizacao_id=org_id, tipo="telegram", nome="Tg", config={}, ativo=ativo
    )
    sessao.add(canal)
    sessao.flush()
    return canal


class _RespOK:
    status_code = 200

    def json(self):
        return {"ok": True, "result": {}}


class _ClienteCaptura:
    chamadas = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None, **k):
        _ClienteCaptura.chamadas.append((url, json))
        return _RespOK()


# ───────────────────────── webhook de entrada (público) ──────────────────────


def test_webhook_registra_mensagem_recebida(cliente, sessao, dados):
    canal = _canal(sessao, dados["orgA"].id)
    r = cliente.post(f"/canais/{canal.id}/webhook", json=_update(500, texto="oi"))
    assert r.status_code == 200 and r.json()["ok"] is True
    msg = sessao.scalars(
        select(MensagemCanal).where(MensagemCanal.canal_id == canal.id)
    ).first()
    assert msg is not None
    assert msg.direcao == "entrada"
    assert msg.identificador_externo == "5175352629"
    assert msg.texto == "oi"
    assert msg.id_externo == "500"


def test_webhook_e_idempotente(cliente, sessao, dados):
    canal = _canal(sessao, dados["orgA"].id)
    url = f"/canais/{canal.id}/webhook"
    primeira = cliente.post(url, json=_update(777))
    segunda = cliente.post(url, json=_update(777))  # mesmo update_id
    # A 1ª é aceita (aqui sem identidade/automação → ignorada, mas registrada);
    # a 2ª, com o mesmo update_id, é deduplicada — independe do roteamento.
    assert primeira.json()["ok"] is True
    assert segunda.json().get("duplicado") is True
    linhas = sessao.scalars(
        select(MensagemCanal).where(MensagemCanal.canal_id == canal.id)
    ).all()
    assert len(linhas) == 1  # não duplicou


def test_webhook_ignora_canal_inativo(cliente, sessao, dados):
    canal = _canal(sessao, dados["orgA"].id, ativo=False)
    r = cliente.post(f"/canais/{canal.id}/webhook", json=_update(1))
    assert r.status_code == 200 and "ignorado" in r.json()
    assert sessao.scalars(
        select(MensagemCanal).where(MensagemCanal.canal_id == canal.id)
    ).first() is None


def test_webhook_ignora_evento_sem_mensagem(cliente, sessao, dados):
    canal = _canal(sessao, dados["orgA"].id)
    r = cliente.post(f"/canais/{canal.id}/webhook", json={"update_id": 9, "edited_channel_post": {}})
    assert r.status_code == 200 and "ignorado" in r.json()


# ─────────────────────── registrar webhook (admin) ───────────────────────────


def test_registrar_webhook_chama_provedor(cliente, entrar, sessao, dados, monkeypatch):
    monkeypatch.setenv("CEREBRO_PUBLIC_URL", "https://api.batuta.team")
    monkeypatch.setattr(tg.httpx, "Client", _ClienteCaptura)
    _ClienteCaptura.chamadas = []
    canal = _canal(sessao, dados["orgA"].id)
    salvar_segredos(sessao, canal.id, {"token": "BOT:TK"})
    entrar(dados["admin"])
    r = cliente.post(f"/organizacoes/{dados['orgA'].id}/canais/{canal.id}/registrar-webhook")
    assert r.status_code == 200
    assert r.json()["url"] == f"https://api.batuta.team/canais/{canal.id}/webhook"
    url, corpo = _ClienteCaptura.chamadas[-1]
    assert url == "https://api.telegram.org/botBOT:TK/setWebhook"
    assert corpo == {"url": f"https://api.batuta.team/canais/{canal.id}/webhook"}


def test_registrar_webhook_sem_url_publica_falha(cliente, entrar, sessao, dados, monkeypatch):
    monkeypatch.delenv("CEREBRO_PUBLIC_URL", raising=False)
    canal = _canal(sessao, dados["orgA"].id)
    entrar(dados["admin"])
    r = cliente.post(f"/organizacoes/{dados['orgA'].id}/canais/{canal.id}/registrar-webhook")
    assert r.status_code == 400
