"""Testes do instrumento Busca na web (Tavily).

Cobrem: (1) robustez — consulta vazia barrada com mensagem clara (antes virava um
"HTTP 400" opaco) e o detalhe do erro do Tavily extraído; (2) a CONFIGURAÇÃO da
busca (tipo, recência, profundidade, país, domínios) montando o corpo certo da
API — incluindo o default = comportamento de antes (zero regressão). Não fazem
chamada de rede real (o POST é interceptado para capturar o corpo enviado).
"""

import httpx
import pytest
from pydantic import ValidationError

from instrumentos.base import FalhaInstrumento
from instrumentos.busca_web import (
    ArgsBuscaWeb,
    BuscaWeb,
    ConfigBuscaWeb,
    _detalhe_erro,
)


def _corpo_enviado(monkeypatch, config: ConfigBuscaWeb, consulta="pauta de teste") -> dict:
    """Roda o instrumento interceptando o POST e devolve o corpo (json) enviado à
    Tavily, com uma resposta de sucesso fixa."""
    capturado: dict = {}

    class _Resp:
        status_code = 200
        is_success = True

        def json(self):
            return {"results": [{"title": "T", "url": "u", "content": "c"}]}

    class _Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):
            capturado.update(json)
            return _Resp()

    monkeypatch.setattr("instrumentos.busca_web.httpx.Client", _Cliente)
    BuscaWeb().executar(config, ArgsBuscaWeb(consulta=consulta))
    return capturado


# ─────────────────────────── Robustez (já existente) ───────────────────────────

def test_consulta_vazia_barrada_sem_chamar_rede():
    inst = BuscaWeb()
    config = ConfigBuscaWeb(chave_api="qualquer")  # passa pela checagem de chave
    args = ArgsBuscaWeb(consulta="   ")  # 3 espaços: válido p/ pydantic, vazio após strip
    with pytest.raises(FalhaInstrumento) as exc:
        inst.executar(config, args)
    assert "vazia" in str(exc.value)


def test_detalhe_erro_extrai_motivo_do_json():
    resp = httpx.Response(400, json={"detail": "query too short"})
    assert _detalhe_erro(resp) == "query too short"


def test_detalhe_erro_cai_no_texto_cru():
    resp = httpx.Response(400, text="Bad Request")
    assert "Bad Request" in _detalhe_erro(resp)


# ─────────────────────────── Config → corpo da API ───────────────────────────

def test_default_reproduz_comportamento_antigo(monkeypatch):
    """Config padrão = busca geral, rápida, sem recência/país/domínios. Garante
    que instrumento existente (que só tinha max_resultados) não muda de cara."""
    corpo = _corpo_enviado(monkeypatch, ConfigBuscaWeb(chave_api="k", max_resultados=10))
    assert corpo["query"]
    assert corpo["max_results"] == 10
    assert corpo["search_depth"] == "basic"
    assert corpo["topic"] == "general"
    # Opcionais NÃO entram no default (senão a Tavily poderia recusar):
    assert "time_range" not in corpo
    assert "country" not in corpo
    assert "include_domains" not in corpo
    assert "exclude_domains" not in corpo


def test_noticias_com_recencia_semana(monkeypatch):
    corpo = _corpo_enviado(
        monkeypatch, ConfigBuscaWeb(chave_api="k", topico="noticias", recencia="semana")
    )
    assert corpo["topic"] == "news"
    assert corpo["time_range"] == "week"


def test_profundidade_aprofundada_vira_advanced(monkeypatch):
    corpo = _corpo_enviado(
        monkeypatch, ConfigBuscaWeb(chave_api="k", profundidade="aprofundada")
    )
    assert corpo["search_depth"] == "advanced"


def test_pais_so_vai_no_topico_geral(monkeypatch):
    # geral + brasil → country: brazil
    corpo = _corpo_enviado(
        monkeypatch, ConfigBuscaWeb(chave_api="k", topico="geral", pais="brasil")
    )
    assert corpo["country"] == "brazil"
    # notícias + brasil → country é OMITIDO (Tavily só aceita country no geral)
    corpo2 = _corpo_enviado(
        monkeypatch, ConfigBuscaWeb(chave_api="k", topico="noticias", pais="brasil")
    )
    assert "country" not in corpo2


def test_dominios_incluir_e_excluir(monkeypatch):
    corpo = _corpo_enviado(
        monkeypatch,
        ConfigBuscaWeb(
            chave_api="k",
            incluir_dominios=["g1.globo.com"],
            excluir_dominios=["spam.com"],
        ),
    )
    assert corpo["include_domains"] == ["g1.globo.com"]
    assert corpo["exclude_domains"] == ["spam.com"]


def test_valor_invalido_e_barrado_pelo_literal():
    with pytest.raises(ValidationError):
        ConfigBuscaWeb(chave_api="k", topico="x")
    with pytest.raises(ValidationError):
        ConfigBuscaWeb(chave_api="k", recencia="ontem")
