"""Testes dos instrumentos de comentários do Instagram (Fase 3).

Cobrem: ler comentários (estrutura + política de falha) e responder/moderar
(responder, ocultar, reexibir, apagar; resposta vazia barrada; idempotência =
falha não-retentável). Sem rede.
"""

import pytest

from instrumentos.base import FalhaInstrumento
from instrumentos.instagram_ler_comentarios import (
    ArgsLerComentarios,
    ConfigLerComentarios,
    InstagramLerComentarios,
)
from instrumentos.instagram_responder_comentario import (
    ArgsResponderComentario,
    ConfigResponderComentario,
    InstagramResponderComentario,
)


class _Resp:
    def __init__(self, body, status=200):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._b = body

    def json(self):
        return self._b

    @property
    def text(self):
        return str(self._b)


class _Client:
    def __init__(self, roteador):
        self.roteador = roteador
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None):
        self.calls.append(("GET", url, params))
        return self.roteador("GET", url, params)

    def post(self, url, data=None):
        self.calls.append(("POST", url, data))
        return self.roteador("POST", url, data)

    def delete(self, url, params=None):
        self.calls.append(("DELETE", url, params))
        return self.roteador("DELETE", url, params)


# ───────────────────────── ler comentários ─────────────────────────

CFG_LER = ConfigLerComentarios(ig_user_id="178", token="TOK")


def _instalar_ler(monkeypatch, roteador):
    cli = _Client(roteador)
    monkeypatch.setattr(
        "instrumentos.instagram_ler_comentarios.httpx.Client", lambda *a, **k: cli
    )
    return cli


def test_ler_comentarios_estrutura(monkeypatch):
    def r(metodo, url, params):
        return _Resp({"data": [
            {"id": "c1", "text": "top!", "username": "fulano", "timestamp": "2026-01-01", "like_count": 3},
        ]})

    cli = _instalar_ler(monkeypatch, r)
    res = InstagramLerComentarios().executar(CFG_LER, ArgsLerComentarios(media_id="m1", limite=10))
    assert res["media_id"] == "m1"
    assert res["comentarios"][0] == {
        "id": "c1", "texto": "top!", "autor": "fulano", "data": "2026-01-01", "curtidas": 3,
    }
    assert cli.calls[0][1].endswith("/m1/comments")


def test_ler_nao_conectado_falha():
    with pytest.raises(FalhaInstrumento) as e:
        InstagramLerComentarios().executar(ConfigLerComentarios(), ArgsLerComentarios(media_id="m1"))
    assert "conectado" in str(e.value)


def test_ler_servidor_caido_retentavel(monkeypatch):
    _instalar_ler(monkeypatch, lambda *a: _Resp({}, 503))
    with pytest.raises(FalhaInstrumento) as e:
        InstagramLerComentarios().executar(CFG_LER, ArgsLerComentarios(media_id="m1"))
    assert e.value.retentavel is True


# ───────────────────────── responder / moderar ─────────────────────────

CFG_RESP = ConfigResponderComentario(ig_user_id="178", token="TOK")


def _instalar_resp(monkeypatch, roteador):
    cli = _Client(roteador)
    monkeypatch.setattr(
        "instrumentos.instagram_responder_comentario.httpx.Client", lambda *a, **k: cli
    )
    return cli


def test_responder_publica_resposta(monkeypatch):
    cli = _instalar_resp(monkeypatch, lambda m, u, d: _Resp({"id": "r1"}))
    res = InstagramResponderComentario().executar(
        CFG_RESP, ArgsResponderComentario(comment_id="c1", acao="responder", mensagem="obrigado!")
    )
    assert res == {"ok": True, "acao": "responder", "comentario_id": "c1", "resposta_id": "r1"}
    metodo, url, dados = cli.calls[0]
    assert metodo == "POST" and url.endswith("/c1/replies")
    assert dados["message"] == "obrigado!"


def test_responder_vazio_barrado():
    with pytest.raises(FalhaInstrumento) as e:
        InstagramResponderComentario().executar(
            CFG_RESP, ArgsResponderComentario(comment_id="c1", acao="responder", mensagem="   ")
        )
    assert "vazia" in str(e.value)


def test_ocultar_usa_hide_true(monkeypatch):
    cli = _instalar_resp(monkeypatch, lambda m, u, d: _Resp({"success": True}))
    res = InstagramResponderComentario().executar(
        CFG_RESP, ArgsResponderComentario(comment_id="c1", acao="ocultar")
    )
    assert res["acao"] == "ocultar"
    metodo, url, dados = cli.calls[0]
    assert metodo == "POST" and url.endswith("/c1")
    assert dados["hide"] == "true"


def test_reexibir_usa_hide_false(monkeypatch):
    cli = _instalar_resp(monkeypatch, lambda m, u, d: _Resp({"success": True}))
    InstagramResponderComentario().executar(
        CFG_RESP, ArgsResponderComentario(comment_id="c1", acao="reexibir")
    )
    assert cli.calls[0][2]["hide"] == "false"


def test_apagar_usa_delete(monkeypatch):
    cli = _instalar_resp(monkeypatch, lambda m, u, d: _Resp({"success": True}))
    res = InstagramResponderComentario().executar(
        CFG_RESP, ArgsResponderComentario(comment_id="c1", acao="apagar")
    )
    assert res["acao"] == "apagar"
    assert cli.calls[0][0] == "DELETE" and cli.calls[0][1].endswith("/c1")


def test_falha_de_resposta_nunca_retentavel(monkeypatch):
    _instalar_resp(monkeypatch, lambda m, u, d: _Resp({"error": {"message": "x"}}, 500))
    with pytest.raises(FalhaInstrumento) as e:
        InstagramResponderComentario().executar(
            CFG_RESP, ArgsResponderComentario(comment_id="c1", acao="responder", mensagem="oi")
        )
    assert e.value.retentavel is False
