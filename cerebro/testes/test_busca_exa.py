"""Testes do instrumento Busca na web (Exa) — busca semântica.

Conferem o corpo enviado por config (tipo/categoria/recência/domínios), o header
de auth (x-api-key), o parse da resposta, a falha sem chave e o `Literal` barrando
valor inválido. Sem rede real (o POST é interceptado)."""

import pytest
from pydantic import ValidationError

from instrumentos.base import FalhaInstrumento
from instrumentos.busca_exa import ArgsBuscaExa, BuscaExa, ConfigBuscaExa


def _captura(monkeypatch, config: ConfigBuscaExa, consulta="pauta de teste") -> dict:
    """Roda o instrumento interceptando o POST; devolve {json, headers, status}."""
    cap: dict = {}

    class _Resp:
        status_code = 200
        is_success = True

        def json(self):
            return {
                "results": [
                    {
                        "title": "T",
                        "url": "https://x.com",
                        "text": "conteudo " * 200,
                        "publishedDate": "2026-06-10",
                    }
                ]
            }

    class _Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json, headers=None):
            cap["json"] = json
            cap["headers"] = headers or {}
            return _Resp()

    monkeypatch.setattr("instrumentos.busca_exa.httpx.Client", _Cliente)
    resultado = BuscaExa().executar(config, ArgsBuscaExa(consulta=consulta))
    cap["resultado"] = resultado
    return cap


def test_default_envia_o_basico_e_a_chave_no_header(monkeypatch):
    cap = _captura(monkeypatch, ConfigBuscaExa(chave_api="EXA-KEY", max_resultados=7))
    corpo = cap["json"]
    assert corpo["query"]
    assert corpo["type"] == "auto"  # equilibrada
    assert corpo["numResults"] == 7
    assert corpo["contents"] == {"text": True}
    assert "category" not in corpo
    assert "startPublishedDate" not in corpo
    assert "includeDomains" not in corpo
    assert cap["headers"].get("x-api-key") == "EXA-KEY"
    # parse: trecho cortado em 500
    assert len(cap["resultado"]["resultados"][0]["trecho"]) == 500


def test_categoria_e_tipo_profundo(monkeypatch):
    cap = _captura(
        monkeypatch,
        ConfigBuscaExa(chave_api="k", categoria="noticias", tipo_busca="profunda"),
    )
    assert cap["json"]["category"] == "news"
    assert cap["json"]["type"] == "deep"


def test_recencia_vira_startPublishedDate(monkeypatch):
    cap = _captura(monkeypatch, ConfigBuscaExa(chave_api="k", recencia="semana"))
    assert "startPublishedDate" in cap["json"]  # data calculada (semana atrás)


def test_dominios(monkeypatch):
    cap = _captura(
        monkeypatch,
        ConfigBuscaExa(
            chave_api="k", incluir_dominios=["g1.globo.com"], excluir_dominios=["spam.com"]
        ),
    )
    assert cap["json"]["includeDomains"] == ["g1.globo.com"]
    assert cap["json"]["excludeDomains"] == ["spam.com"]


def test_sem_chave_falha_com_recado_claro():
    with pytest.raises(FalhaInstrumento) as exc:
        BuscaExa().executar(ConfigBuscaExa(), ArgsBuscaExa(consulta="x"))
    assert "Chaves e credenciais" in str(exc.value)


def test_valor_invalido_barrado_pelo_literal():
    with pytest.raises(ValidationError):
        ConfigBuscaExa(chave_api="k", tipo_busca="turbo")
    with pytest.raises(ValidationError):
        ConfigBuscaExa(chave_api="k", categoria="esporte")
