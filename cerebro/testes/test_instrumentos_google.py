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


# ── Gerar e montar imagem ────────────────────────────────────────────────────────


def _resposta_imagem(dados=b"\x89PNG-imagem", mime="image/png", motivo="STOP"):
    partes = [NS(inline_data=NS(data=dados, mime_type=mime))] if dados else []
    return NS(candidates=[NS(content=NS(parts=partes), finish_reason=motivo)])


def _guardar(monkeypatch, modulo):
    salvos: list = []
    monkeypatch.setattr(modulo.arquivos, "salvar",
                        lambda nome, conteudo, tipo: salvos.append((nome, conteudo, tipo)) or f"https://armazem/{nome}")
    return salvos


def test_gerar_imagem_pelo_google_com_proporcao_e_resolucao(monkeypatch):
    from instrumentos import gerar_imagem as gi

    pedidos = _google_falso(monkeypatch, [_resposta_imagem(b"jpeg-bytes", "image/jpeg")])
    salvos = _guardar(monkeypatch, gi)
    tipo = encaixe.obter_tipo("gerar_imagem")
    cfg = tipo.Config(modelo="gemini-3.1-flash-image", tamanho="4:5", qualidade="2K", formato="jpeg")
    with usar_chaves({"google": "g"}):
        r = tipo.executar(cfg, tipo.Args(prompt="um café na praia"))
    conf = pedidos[0]["config"]
    assert pedidos[0]["model"] == "gemini-3.1-flash-image"
    assert conf.response_modalities == ["IMAGE"]
    assert (conf.image_config.aspect_ratio, conf.image_config.image_size) == ("4:5", "2K")
    assert conf.image_config.output_mime_type == "image/jpeg"
    assert pedidos[0]["contents"] == ["um café na praia"]
    assert salvos[0][1] == b"jpeg-bytes" and salvos[0][0].endswith(".jpg")
    assert r["ok"] and r["url"].startswith("https://armazem/")


def test_gerar_imagem_proporcao_de_um_modelo_nao_vale_no_outro():
    tipo = encaixe.obter_tipo("gerar_imagem")
    with pytest.raises(ValueError):
        tipo.Config(modelo="gemini-3.1-flash-image", tamanho="1024x1024", qualidade="1K")
    with pytest.raises(ValueError):  # o Flash-Lite só faz 1K
        tipo.Config(modelo="gemini-3.1-flash-lite-image", tamanho="1:1", qualidade="4K")


def test_gerar_imagem_pelo_google_sem_imagem_vira_recusa(monkeypatch):
    _google_falso(monkeypatch, [_resposta_imagem(None, motivo="IMAGE_SAFETY")])
    tipo = encaixe.obter_tipo("gerar_imagem")
    cfg = tipo.Config(modelo="gemini-3.1-flash-image", tamanho="1:1", qualidade="1K")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(cfg, tipo.Args(prompt="algo proibido"))
    assert e.value.codigo == "ia.recusa" and not e.value.retentavel


def test_gerar_imagem_pelo_google_sem_chave_do_google():
    tipo = encaixe.obter_tipo("gerar_imagem")
    cfg = tipo.Config(modelo="gemini-3.1-flash-image", tamanho="1:1", qualidade="1K", chave_api="sk-openai")
    with usar_chaves({"openai": "o"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(cfg, tipo.Args(prompt="um gato"))
    assert e.value.codigo == "ia.sem_chave"


def test_imagem_do_google_libera_com_a_chave_do_google_e_tem_preco():
    import precos

    assert encaixe.obter_tipo("gerar_imagem").provedores_ia == ("openai", "google")
    assert encaixe.obter_tipo("montar_imagem").provedores_ia == ("openai", "google")
    assert precos.custo_por_imagem("gemini-3.1-flash-image", "1:1", "4K") == 0.151


def test_campo_antigo_provedor_da_imagem_e_ignorado():
    tipo = encaixe.obter_tipo("gerar_imagem")
    assert tipo.Config(provedor="openai").modelo == "gpt-image-2"


def test_montar_imagem_pelo_google_manda_as_fotos_junto(monkeypatch):
    from instrumentos import montar_imagem as mi

    pedidos = _google_falso(monkeypatch, [_resposta_imagem()])
    _guardar(monkeypatch, mi)
    monkeypatch.setattr(mi.httpx, "get", lambda url, **k: httpx.Response(
        200, content=b"foto-" + url[-1:].encode(), headers={"content-type": "image/jpeg"},
        request=httpx.Request("GET", url)))
    tipo = encaixe.obter_tipo("montar_imagem")
    cfg = tipo.Config(modelo="gemini-3.1-flash-image", tamanho="4:5", qualidade="1K")
    with usar_chaves({"google": "g"}):
        r = tipo.executar(cfg, tipo.Args(prompt="a 1ª é a pessoa; coloque num escritório",
                                         imagens_url=["https://x.com/a", "https://x.com/b"]))
    foto1, foto2, texto = pedidos[0]["contents"]
    assert foto1.inline_data.data == b"foto-a" and foto2.inline_data.data == b"foto-b"
    assert foto1.inline_data.mime_type == "image/jpeg" and texto.startswith("a 1ª")
    assert r["ok"]


def test_montar_imagem_pelo_google_respeita_o_limite_de_fotos(monkeypatch):
    tipo = encaixe.obter_tipo("montar_imagem")
    cfg = tipo.Config(modelo="gemini-3.1-flash-image", tamanho="1:1", qualidade="1K")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(cfg, tipo.Args(prompt="x", imagens_url=[f"https://x.com/{i}" for i in range(15)]))
    assert "no máximo 14" in str(e.value)


# ── Narrar texto ─────────────────────────────────────────────────────────────────


def _resposta_audio(dados, entrada=50, saida=250):
    partes = [NS(inline_data=NS(data=dados, mime_type="audio/wav"))] if dados else []
    return NS(candidates=[NS(content=NS(parts=partes), finish_reason="STOP")],
              usage_metadata=NS(prompt_token_count=entrada, candidates_token_count=saida))


def test_narrar_texto_poe_cabecalho_wav_no_audio_cru_e_mede_o_custo(monkeypatch):
    import wave
    import io
    from instrumentos import narrar_texto as nt

    pcm = b"\x00\x01" * 24_000  # 1 s de áudio cru (16 bits, 24 kHz, mono)
    pedidos = _google_falso(monkeypatch, [_resposta_audio(pcm)])
    salvos = _guardar(monkeypatch, nt)
    tipo = encaixe.obter_tipo("narrar_texto")
    with usar_chaves({"google": "g"}):
        r = tipo.executar(tipo.Config(voz="Achird", tom="animado"), tipo.Args(texto="Olá, tudo bem?"))
    conf = pedidos[0]["config"]
    assert conf.response_modalities == ["AUDIO"]
    assert conf.speech_config.voice_config.prebuilt_voice_config.voice_name == "Achird"
    assert conf.speech_config.language_code == "pt-BR"
    assert "animado" in conf.system_instruction
    nome, wav, mime = salvos[0]
    assert mime == "audio/wav" and wav[:4] == b"RIFF" and nome.endswith(".wav")
    with wave.open(io.BytesIO(wav)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24_000, 1, 2)
    assert r["segundos"] == 1.0
    # 50 × US$ 0,50/M + 250 × US$ 6/M (Flash-Lite)
    assert r["uso"]["custo_usd"] == pytest.approx(0.000025 + 0.0015)


def test_narrar_texto_sem_tom_nao_manda_instrucao(monkeypatch):
    pedidos = _google_falso(monkeypatch, [_resposta_audio(b"RIFF....WAVEfmt ")])
    from instrumentos import narrar_texto as nt
    _guardar(monkeypatch, nt)
    tipo = encaixe.obter_tipo("narrar_texto")
    with usar_chaves({"google": "g"}):
        tipo.executar(tipo.Config(), tipo.Args(texto="Oi"))
    assert pedidos[0]["config"].system_instruction is None


def test_narrar_texto_sem_audio_vira_falha(monkeypatch):
    _google_falso(monkeypatch, [_resposta_audio(None)])
    tipo = encaixe.obter_tipo("narrar_texto")
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(texto="Oi"))
    assert e.value.codigo == "google.sem_audio"


def test_narrar_texto_e_do_google_e_registrado():
    from orquestracao import ciclo_modelos as cm
    from instrumentos import narrar_texto as nt

    tipo = encaixe.obter_tipo("narrar_texto")
    assert tipo.provedores_ia == ("google",) and tipo.acao_irreversivel is False
    for m in nt.PRECOS_VOZ:
        assert cm.obter(m) and cm.obter(m).uso == cm.VOZ


def test_imagem_do_google_paga_pela_chave_do_google():
    import medicao_instrumentos as med

    inst = NS(tipo="gerar_imagem", configuracao={"modelo": "gemini-3.1-flash-image", "qualidade": "2K"})
    entrada, servico = med._entrada_e_servico(inst)
    assert servico == "google" and entrada["custo_usd"] == 0.101
