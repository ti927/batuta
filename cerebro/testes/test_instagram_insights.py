"""Testes do instrumento Instagram — conteúdo e métricas (Fase 2, leitura).

Cobrem a leitura de conta + posts (com curtidas/comentários), o erro de "não
conectado" e a política de falha (401 não-retentável; 5xx retentável). Sem rede.
"""

import pytest

from instrumentos.base import FalhaInstrumento
from instrumentos.instagram_insights import (
    ArgsInstagramInsights,
    ConfigInstagramInsights,
    InstagramInsights,
)

CFG = ConfigInstagramInsights(ig_user_id="178", token="TOK")


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

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None):
        return self.roteador(url, params)


def _instalar(monkeypatch, roteador):
    monkeypatch.setattr(
        "instrumentos.instagram_insights.httpx.Client", lambda *a, **k: _Client(roteador)
    )


def test_le_conta_e_posts(monkeypatch):
    def r(url, params):
        if url.endswith("/media"):
            return _Resp({"data": [
                {"id": "m1", "media_type": "IMAGE", "caption": "olá", "permalink": "p1",
                 "timestamp": "2026-01-01", "like_count": 5, "comments_count": 2},
            ]})
        return _Resp({"username": "batuta", "account_type": "BUSINESS", "media_count": 10})

    _instalar(monkeypatch, r)
    res = InstagramInsights().executar(CFG, ArgsInstagramInsights(limite=5))
    assert res["conta"] == {"usuario": "batuta", "tipo_conta": "BUSINESS", "total_posts": 10}
    assert res["posts"][0]["curtidas"] == 5
    assert res["posts"][0]["comentarios"] == 2
    assert res["posts"][0]["link"] == "p1"


def test_nao_conectado_falha():
    with pytest.raises(FalhaInstrumento) as e:
        InstagramInsights().executar(ConfigInstagramInsights(), ArgsInstagramInsights())
    assert "conectado" in str(e.value)


def test_token_recusado_nao_retentavel(monkeypatch):
    _instalar(monkeypatch, lambda url, params: _Resp({"error": {"message": "bad token"}}, 401))
    with pytest.raises(FalhaInstrumento) as e:
        InstagramInsights().executar(CFG, ArgsInstagramInsights())
    assert e.value.retentavel is False


def test_servidor_caido_retentavel(monkeypatch):
    _instalar(monkeypatch, lambda url, params: _Resp({}, 503))
    with pytest.raises(FalhaInstrumento) as e:
        InstagramInsights().executar(CFG, ArgsInstagramInsights())
    assert e.value.retentavel is True
