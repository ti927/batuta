"""Testes do instrumento 'Ler post do Instagram' (contexto do post por media_id).

Cobrem a estrutura da resposta e a política de falha (leitura idempotente:
400 não-retentável; 5xx retentável; sem token barra). Sem rede.
"""

import pytest

from instrumentos.base import FalhaInstrumento
from instrumentos.instagram_ler_post import ArgsLerPost, ConfigLerPost, InstagramLerPost


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


CFG = ConfigLerPost(ig_user_id="178", token="TOK")


def _instalar(monkeypatch, roteador):
    cli = _Client(roteador)
    monkeypatch.setattr(
        "instrumentos.instagram_ler_post.httpx.Client", lambda *a, **k: cli
    )
    return cli


def test_ler_post_estrutura(monkeypatch):
    def r(metodo, url, params):
        return _Resp(
            {
                "id": "m1",
                "caption": "Promo de verão!",
                "media_type": "IMAGE",
                "media_url": "https://cdn.instagr.am/m1.jpg",
                "permalink": "https://instagr.am/p/x",
                "timestamp": "2026-01-01",
                "like_count": 42,
                "comments_count": 7,
            }
        )

    cli = _instalar(monkeypatch, r)
    res = InstagramLerPost().executar(CFG, ArgsLerPost(media_id="m1"))
    assert res["ok"] is True
    assert res["post"]["legenda"] == "Promo de verão!"
    assert res["post"]["tipo"] == "IMAGE"
    assert res["post"]["imagem"] == "https://cdn.instagr.am/m1.jpg"  # URL da imagem
    assert res["post"]["curtidas"] == 42 and res["post"]["comentarios"] == 7
    metodo, url, params = cli.calls[0]
    assert metodo == "GET" and url.endswith("/m1")
    assert "caption" in params["fields"] and "media_url" in params["fields"]


def test_ler_post_nao_conectado_falha():
    with pytest.raises(FalhaInstrumento) as e:
        InstagramLerPost().executar(ConfigLerPost(), ArgsLerPost(media_id="m1"))
    assert "conectado" in str(e.value)


def test_ler_post_servidor_caido_retentavel(monkeypatch):
    _instalar(monkeypatch, lambda *a: _Resp({}, 503))
    with pytest.raises(FalhaInstrumento) as e:
        InstagramLerPost().executar(CFG, ArgsLerPost(media_id="m1"))
    assert e.value.retentavel is True


def test_ler_post_recusado_nao_retentavel(monkeypatch):
    _instalar(monkeypatch, lambda *a: _Resp({"error": {"message": "no"}}, 400))
    with pytest.raises(FalhaInstrumento) as e:
        InstagramLerPost().executar(CFG, ArgsLerPost(media_id="m1"))
    assert e.value.retentavel is False
