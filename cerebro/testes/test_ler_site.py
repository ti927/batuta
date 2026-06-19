"""Testes do instrumento Ler site (Tavily /extract).

Conferem o corpo enviado por config (extract_depth/format), o header de auth
(Bearer), o parse de raw_content com corte por max_caracteres, o caso de página
sem conteúdo, a falha sem chave e o `Literal`. Sem rede real."""

import pytest
from pydantic import ValidationError

from instrumentos.base import FalhaInstrumento
from instrumentos.ler_site import ArgsLerSite, ConfigLerSite, LerSite


def _captura(monkeypatch, config: ConfigLerSite, *, results, url="https://x.com/a") -> dict:
    cap: dict = {}

    class _Resp:
        status_code = 200
        is_success = True

        def json(self):
            return {"results": results, "failed_results": []}

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

    monkeypatch.setattr("instrumentos.ler_site.httpx.Client", _Cliente)
    cap["resultado"] = LerSite().executar(config, ArgsLerSite(url=url))
    return cap


def test_default_corpo_e_bearer(monkeypatch):
    cap = _captura(
        monkeypatch,
        ConfigLerSite(chave_api="TVLY"),
        results=[{"url": "https://x.com/a", "raw_content": "olá mundo"}],
    )
    corpo = cap["json"]
    assert corpo["urls"] == ["https://x.com/a"]
    assert corpo["extract_depth"] == "basic"
    assert corpo["format"] == "markdown"
    assert cap["headers"].get("Authorization") == "Bearer TVLY"
    assert cap["resultado"] == {"ok": True, "url": "https://x.com/a", "conteudo": "olá mundo"}


def test_profundidade_e_formato(monkeypatch):
    cap = _captura(
        monkeypatch,
        ConfigLerSite(chave_api="k", profundidade="aprofundada", formato="texto"),
        results=[{"url": "https://x.com/a", "raw_content": "x"}],
    )
    assert cap["json"]["extract_depth"] == "advanced"
    assert cap["json"]["format"] == "text"


def test_corta_em_max_caracteres(monkeypatch):
    cap = _captura(
        monkeypatch,
        ConfigLerSite(chave_api="k", max_caracteres=500),
        results=[{"url": "https://x.com/a", "raw_content": "a" * 5000}],
    )
    assert len(cap["resultado"]["conteudo"]) == 500


def test_pagina_sem_conteudo_devolve_ok_false(monkeypatch):
    cap = _captura(monkeypatch, ConfigLerSite(chave_api="k"), results=[])
    assert cap["resultado"]["ok"] is False
    assert "Firecrawl" in cap["resultado"]["erro"]  # sugere a alternativa robusta


def test_sem_chave_falha_com_recado_claro():
    with pytest.raises(FalhaInstrumento) as exc:
        LerSite().executar(ConfigLerSite(), ArgsLerSite(url="https://x.com"))
    assert "Chaves e credenciais" in str(exc.value)


def test_valor_invalido_barrado_pelo_literal():
    with pytest.raises(ValidationError):
        ConfigLerSite(chave_api="k", formato="pdf")
