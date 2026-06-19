"""Testes do instrumento Ler site (Firecrawl).

Conferem o corpo enviado (url/formats/onlyMainContent), o header Bearer, o parse
de data.markdown + título com corte por max_caracteres, o caso sem conteúdo e a
falha sem chave. Sem rede real."""

import pytest

from instrumentos.base import FalhaInstrumento
from instrumentos.ler_site_firecrawl import (
    ArgsLerSiteFirecrawl,
    ConfigLerSiteFirecrawl,
    LerSiteFirecrawl,
)


def _captura(monkeypatch, config: ConfigLerSiteFirecrawl, *, data, url="https://x.com/a") -> dict:
    cap: dict = {}

    class _Resp:
        status_code = 200
        is_success = True

        def json(self):
            return {"success": True, "data": data}

    class _Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, u, json, headers=None):
            cap["json"] = json
            cap["headers"] = headers or {}
            return _Resp()

    monkeypatch.setattr("instrumentos.ler_site_firecrawl.httpx.Client", _Cliente)
    cap["resultado"] = LerSiteFirecrawl().executar(
        config, ArgsLerSiteFirecrawl(url=url)
    )
    return cap


def test_default_corpo_e_bearer(monkeypatch):
    cap = _captura(
        monkeypatch,
        ConfigLerSiteFirecrawl(chave_api="FC"),
        data={"markdown": "# Olá", "metadata": {"title": "Página X"}},
    )
    corpo = cap["json"]
    assert corpo["url"] == "https://x.com/a"
    assert corpo["formats"] == ["markdown"]
    assert corpo["onlyMainContent"] is True
    assert cap["headers"].get("Authorization") == "Bearer FC"
    assert cap["resultado"]["titulo"] == "Página X"
    assert cap["resultado"]["conteudo"] == "# Olá"


def test_desligar_conteudo_principal(monkeypatch):
    cap = _captura(
        monkeypatch,
        ConfigLerSiteFirecrawl(chave_api="k", apenas_conteudo_principal=False),
        data={"markdown": "x", "metadata": {}},
    )
    assert cap["json"]["onlyMainContent"] is False


def test_corta_em_max_caracteres(monkeypatch):
    cap = _captura(
        monkeypatch,
        ConfigLerSiteFirecrawl(chave_api="k", max_caracteres=500),
        data={"markdown": "a" * 5000, "metadata": {}},
    )
    assert len(cap["resultado"]["conteudo"]) == 500


def test_pagina_sem_conteudo_devolve_ok_false(monkeypatch):
    cap = _captura(
        monkeypatch, ConfigLerSiteFirecrawl(chave_api="k"), data={"markdown": ""}
    )
    assert cap["resultado"]["ok"] is False


def test_sem_chave_falha_com_recado_claro():
    with pytest.raises(FalhaInstrumento) as exc:
        LerSiteFirecrawl().executar(
            ConfigLerSiteFirecrawl(), ArgsLerSiteFirecrawl(url="https://x.com")
        )
    assert "Chaves e credenciais" in str(exc.value)
