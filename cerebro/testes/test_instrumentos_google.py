"""Os instrumentos "por capacidade" quando o modelo escolhido é do Google (2026-10-02):
Pesquisar na web, Ler página e Ler documento. O Google é simulado (as respostas imitam
o formato do SDK `google-genai`); nada vai à rede."""

from types import SimpleNamespace as NS

import httpx
import pytest

import instrumentos as encaixe
from google.genai import errors
from instrumentos import escolha_ia
from instrumentos import google_servidor as goo
from instrumentos import ler_documento as ld
from instrumentos import pesquisar_web
from instrumentos.base import FalhaInstrumento
from orquestracao.llm import usar_chaves


def _resposta(texto, *, consultas=(), fontes=(), links=None, entrada=1000, saida=100,
              pensamento=0, ferramenta=0, motivo="STOP", bloqueio=None):
    meta = NS(
        web_search_queries=list(consultas),
        grounding_chunks=[NS(web=NS(uri=u, title=t)) for t, u in fontes],
    )
    url_meta = NS(url_metadata=[
        NS(retrieved_url=u, url_retrieval_status=NS(value=s)) for u, s in (links or {}).items()
    ])
    candidato = NS(finish_reason=motivo, grounding_metadata=meta, url_context_metadata=url_meta)
    return NS(
        text=texto, candidates=[candidato], prompt_feedback=NS(block_reason=bloqueio),
        usage_metadata=NS(
            prompt_token_count=entrada, candidates_token_count=saida,
            thoughts_token_count=pensamento, tool_use_prompt_token_count=ferramenta,
            cached_content_token_count=0,
        ),
    )


def _google_falso(monkeypatch, respostas) -> list[dict]:
    pedidos: list[dict] = []
    fila = list(respostas)

    class Modelos:
        def generate_content(self, **kw):
            pedidos.append(kw)
            item = fila.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    monkeypatch.setattr(goo, "cliente", lambda timeout=None: NS(models=Modelos()))
    return pedidos


def _erro(codigo, mensagem, status="ERRO"):
    classe = errors.ServerError if codigo >= 500 else errors.ClientError
    return classe(codigo, {"error": {"code": codigo, "message": mensagem, "status": status}})


# ── Qual IA faz o trabalho ───────────────────────────────────────────────────────


def test_em_branco_com_so_a_chave_do_google_usa_o_google():
    with usar_chaves({"google": "g"}):
        assert escolha_ia.resolver("", pesquisar_web.PADROES) == "gemini-3.5-flash-lite"
        assert escolha_ia.resolver("", ld.PADROES) == "gemini-3.8-flash"
    with usar_chaves({"openai": "o", "google": "g"}):  # a ordem de preferência vale
        assert escolha_ia.resolver("", pesquisar_web.PADROES) == "gpt-5.6-luna"


def test_google_libera_os_tres_de_leitura_mas_nao_o_gerar_arquivo():
    for t in ("pesquisar_web", "ler_pagina", "ler_documento"):
        assert "google" in encaixe.obter_tipo(t).provedores_ia
    assert "google" not in encaixe.obter_tipo("gerar_arquivo").provedores_ia
    campo = encaixe.obter_tipo("gerar_arquivo").Config.model_json_schema()["properties"]["modelo"]
    assert campo["provedores"] == ["anthropic", "openai"]
    assert not any(m.startswith("gemini") for m in campo["enum"])


def test_sem_chave_do_google_explica_o_caminho():
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"openai": "o"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(modelo="gemini-3.8-flash"), tipo.Args(pergunta="selic hoje"))
    assert e.value.codigo == "ia.sem_chave"


# ── Pesquisar na web ─────────────────────────────────────────────────────────────


def test_pesquisa_pelo_google_com_fontes_filtros_e_custo(monkeypatch):
    from datetime import date

    pedidos = _google_falso(monkeypatch, [_resposta(
        "A Selic está em 13,75%.", consultas=["selic hoje"],
        fontes=[("bcb.gov.br", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/a")],
        entrada=500, saida=80, pensamento=200, ferramenta=3000,
    )])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"google": "g"}):
        r = tipo.executar(
            tipo.Config(sites_bloqueados=["exemplo.com"]),
            tipo.Args(pergunta="qual a selic?", desde=date(2026, 9, 25)),
        )
    config = pedidos[0]["config"]
    busca = config.tools[0].google_search
    assert pedidos[0]["model"] == "gemini-3.5-flash-lite"
    assert busca.exclude_domains == ["exemplo.com"]
    assert busca.time_range_filter.start_time.date() == date(2026, 9, 25)
    assert "Hoje é" in config.system_instruction
    assert r["resposta"] == "A Selic está em 13,75%."
    assert r["fontes"][0]["titulo"] == "bcb.gov.br"
    assert r["uso"]["buscas"] == 1
    assert r["uso"]["tokens_entrada"] == 3500 and r["uso"]["tokens_saida"] == 280
    # 3.500 × US$ 0,30/M + 280 × US$ 2,50/M + 1 busca × US$ 0,014
    assert r["uso"]["custo_usd"] == pytest.approx(0.00105 + 0.0007 + 0.014)


def test_so_nestes_sites_vira_regra_nas_instrucoes(monkeypatch):
    pedidos = _google_falso(monkeypatch, [_resposta("ok")])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"google": "g"}):
        tipo.executar(tipo.Config(sites_preferidos=["gov.br"]), tipo.Args(pergunta="dados do ibge"))
    assert "gov.br" in pedidos[0]["config"].system_instruction


def test_conta_do_google_sem_credito_da_o_caminho(monkeypatch):
    _google_falso(monkeypatch, [_erro(402, "Your prepayment credits are depleted.", "RESOURCE_EXHAUSTED")])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(pergunta="selic hoje"))
    assert e.value.codigo == "ia.sem_credito" and "ai.studio" in str(e.value)
    assert not e.value.retentavel


def test_chave_recusada_pelo_google(monkeypatch):
    _google_falso(monkeypatch, [_erro(400, "API key not valid. Please pass a valid API key.", "INVALID_ARGUMENT")])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(pergunta="selic hoje"))
    assert e.value.codigo == "ia.chave_recusada"


def test_google_sobrecarregado_e_retentavel(monkeypatch):
    _google_falso(monkeypatch, [_erro(503, "The model is overloaded.", "UNAVAILABLE")])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(pergunta="selic hoje"))
    assert e.value.retentavel and e.value.codigo == "ia.indisponivel"


def test_resposta_bloqueada_pelo_google_vira_recusa(monkeypatch):
    _google_falso(monkeypatch, [_resposta("", motivo="SAFETY")])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(pergunta="algo proibido"))
    assert e.value.codigo == "ia.recusa"


# ── Ler página ───────────────────────────────────────────────────────────────────


def test_ler_pagina_pelo_google_usa_a_leitura_de_link(monkeypatch):
    url = "https://pt.wikipedia.org/wiki/Selic"
    pedidos = _google_falso(monkeypatch, [_resposta(
        "Trata da Selic.", links={url: "URL_RETRIEVAL_STATUS_SUCCESS"},
    )])
    tipo = encaixe.obter_tipo("ler_pagina")
    with usar_chaves({"google": "g"}):
        r = tipo.executar(tipo.Config(), tipo.Args(url=url))
    assert pedidos[0]["config"].tools[0].url_context is not None
    assert url in pedidos[0]["contents"][0]
    assert r["conteudo"] == "Trata da Selic." and "aviso" not in r


def test_ler_pagina_pelo_google_que_nao_abriu(monkeypatch):
    url = "https://exemplo.com.br/restrito"
    _google_falso(monkeypatch, [_resposta("", links={url: "URL_RETRIEVAL_STATUS_PAYWALL"})])
    tipo = encaixe.obter_tipo("ler_pagina")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(url=url))
    assert e.value.codigo == "google.link_inacessivel" and not e.value.retentavel


def test_ler_pagina_pelo_google_responde_sem_abrir_e_avisa(monkeypatch):
    _google_falso(monkeypatch, [_resposta("Acho que trata de juros.")])
    tipo = encaixe.obter_tipo("ler_pagina")
    with usar_chaves({"google": "g"}):
        r = tipo.executar(tipo.Config(), tipo.Args(url="https://exemplo.com.br"))
    assert "não abriu" in r["aviso"]


# ── Ler documento ────────────────────────────────────────────────────────────────


def test_ler_documento_pelo_google_baixa_e_manda_o_pdf(monkeypatch):
    monkeypatch.setattr(ld.httpx, "get", lambda url, **k: httpx.Response(
        200, content=b"%PDF-1.4 conteudo", request=httpx.Request("GET", url)))
    pedidos = _google_falso(monkeypatch, [_resposta("Total de R$ 1.200,00.")])
    tipo = encaixe.obter_tipo("ler_documento")
    with usar_chaves({"google": "g"}):
        r = tipo.executar(tipo.Config(), tipo.Args(url="https://x.com/nota.pdf", pergunta="total?"))
    parte, pergunta = pedidos[0]["contents"]
    assert pedidos[0]["model"] == "gemini-3.8-flash"
    assert parte.inline_data.mime_type == "application/pdf"
    assert parte.inline_data.data.startswith(b"%PDF") and pergunta == "total?"
    assert r["resposta"].startswith("Total") and r["citacoes"] == []


def test_ler_documento_pelo_google_recusa_o_que_nao_e_pdf(monkeypatch):
    monkeypatch.setattr(ld.httpx, "get", lambda url, **k: httpx.Response(
        200, content=b"<html>login</html>", request=httpx.Request("GET", url)))
    tipo = encaixe.obter_tipo("ler_documento")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(url="https://x.com/nota.pdf"))
    assert "não aponta para um PDF" in str(e.value)


def test_ler_documento_pelo_google_grande_demais_sugere_outra_ia(monkeypatch):
    monkeypatch.setattr(ld, "MAX_BYTES_GOOGLE", 10)
    monkeypatch.setattr(ld.httpx, "get", lambda url, **k: httpx.Response(
        200, content=b"%PDF-1.4 muito grande", request=httpx.Request("GET", url)))
    tipo = encaixe.obter_tipo("ler_documento")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(url="https://x.com/nota.pdf"))
    assert "Anthropic ou da OpenAI" in str(e.value)
