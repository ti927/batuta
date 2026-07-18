"""Testes do instrumento Google Search Console (só leitura).

Sem rede: o httpx do módulo é interceptado por um dublê que devolve a resposta da
searchAnalytics.query. Cobre o caminho feliz, a validação (sem token/sem site) e a
política de falha (403 não-retentável, 5xx retentável)."""

import pytest

import instrumentos.search_console as sc
from instrumentos.base import FalhaInstrumento


def _mock_post(monkeypatch, *, status=200, corpo=None):
    cap: dict = {}

    class _Resp:
        def __init__(self, status, corpo):
            self.status_code = status
            self.is_success = 200 <= status < 300
            self._corpo = corpo

        def json(self):
            return self._corpo

        @property
        def text(self):
            return ""

    class _Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):
            cap["url"] = url
            cap["json"] = json
            cap["headers"] = headers or {}
            return _Resp(
                status,
                corpo
                if corpo is not None
                else {
                    "rows": [
                        {"keys": ["controladoria"], "clicks": 12, "impressions": 340,
                         "ctr": 0.035, "position": 8.4},
                        {"keys": ["fluxo de caixa"], "clicks": 5, "impressions": 120,
                         "ctr": 0.041, "position": 12.1},
                    ]
                },
            )

    monkeypatch.setattr("instrumentos.search_console.httpx.Client", _Cliente)
    return cap


def _inst():
    return sc.SearchConsoleConsultar()


def test_consulta_feliz_parseia_linhas(monkeypatch):
    cap = _mock_post(monkeypatch)
    config = sc.ConfigSearchConsole(site_url="sc-domain:blog.com", access_token="ACCESS")
    args = sc.ArgsSearchConsole(dias=28, dimensoes=["query"], limite=20)
    res = _inst().executar(config, args)
    assert res["ok"] is True
    assert res["site"] == "sc-domain:blog.com"
    assert res["dimensoes"] == ["query"]
    assert res["linhas"][0]["chaves"] == {"query": "controladoria"}
    assert res["linhas"][0]["cliques"] == 12
    # Bearer com o access_token e o site URL-encodado no caminho
    assert cap["headers"]["Authorization"] == "Bearer ACCESS"
    assert "sc-domain%3Ablog.com" in cap["url"]
    assert cap["json"]["dimensions"] == ["query"]


def test_dimensoes_invalidas_sao_filtradas(monkeypatch):
    cap = _mock_post(monkeypatch)
    config = sc.ConfigSearchConsole(site_url="sc-domain:blog.com", access_token="A")
    args = sc.ArgsSearchConsole(dimensoes=["query", "inexistente"])
    _inst().executar(config, args)
    assert cap["json"]["dimensions"] == ["query"]


def test_sem_token_falha_nao_retentavel():
    config = sc.ConfigSearchConsole(site_url="sc-domain:blog.com", access_token="")
    with pytest.raises(FalhaInstrumento) as exc:
        _inst().executar(config, sc.ArgsSearchConsole())
    assert exc.value.retentavel is False


def test_sem_site_falha_nao_retentavel():
    config = sc.ConfigSearchConsole(site_url="", access_token="ACCESS")
    with pytest.raises(FalhaInstrumento) as exc:
        _inst().executar(config, sc.ArgsSearchConsole())
    assert exc.value.retentavel is False


def test_403_nao_retentavel_com_dica(monkeypatch):
    _mock_post(monkeypatch, status=403, corpo={"error": {"message": "permission denied"}})
    config = sc.ConfigSearchConsole(site_url="sc-domain:blog.com", access_token="A")
    with pytest.raises(FalhaInstrumento) as exc:
        _inst().executar(config, sc.ArgsSearchConsole())
    assert exc.value.retentavel is False
    assert "Search Console" in str(exc.value)


def test_500_retentavel(monkeypatch):
    _mock_post(monkeypatch, status=503, corpo={})
    config = sc.ConfigSearchConsole(site_url="sc-domain:blog.com", access_token="A")
    with pytest.raises(FalhaInstrumento) as exc:
        _inst().executar(config, sc.ArgsSearchConsole())
    assert exc.value.retentavel is True
