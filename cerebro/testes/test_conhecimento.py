"""Central de Conhecimento: o leitor (`conhecimento.py`), as rotas `/ajuda` e o wiring
da consulta/prompt da IA criadora. O acervo real (cerebro/central/*.md) é a fonte."""

import conhecimento
from langchain_core.messages import SystemMessage

from criacao.prompt import (
    _blocos_criadora,
    montar_prompt_criadora,
    montar_system_criadora,
    prompt_criadora,
)

PILOTO = "instrumentos/gerar-video"


def test_indice_lista_capitulos_e_exclui_meta():
    conhecimento.recarregar()
    slugs = {c["slug"] for c in conhecimento.indice()}
    assert PILOTO in slugs
    # Arquivos-meta não entram no índice navegável.
    assert not ({"indice", "_gabarito", "gabarito"} & slugs)


def test_obter_capitulo_parseia_frontmatter():
    cap = conhecimento.obter(PILOTO)
    assert cap is not None
    assert cap.titulo and cap.area == "instrumentos"
    assert "sora" in cap.tags  # lista do frontmatter parseada
    assert "## Para a IA" in cap.corpo  # corpo sem frontmatter, com as seções


def test_obter_inexistente_devolve_none():
    assert conhecimento.obter("nao/existe") is None


def test_busca_encontra_e_vazio_nao_quebra():
    achados = conhecimento.buscar("gerar vídeo com a sora")
    assert achados and achados[0].slug == PILOTO
    assert conhecimento.buscar("zzxqwnadaaqui") == []
    assert conhecimento.buscar("") == []


def test_busca_conta_palavra_inteira_e_ignora_ligacao():
    # Antes, a pontuação contava SUBSTRING: "no" somava ponto dentro de "diagnostico" e
    # "conector", então o capítulo mais LONGO ganhava — e o vencedor mudava toda vez que
    # alguém acrescentava um parágrafo em qualquer capítulo (foi o que quebrou a suíte
    # em 2026-09-02). Palavra de ligação não pontua, e pedaço de palavra não conta.
    assert conhecimento.buscar("no") == []
    assert conhecimento.buscar("de para com") == []
    assert conhecimento.buscar("instrum") == []  # pedaço de "instrumento", não é palavra
    achados = conhecimento.buscar("pedir aprovacao aguardar")
    assert achados and achados[0].slug == "automacoes/pedir-aprovacao"


def test_rota_indice_e_capitulo(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.get("/ajuda/indice")
    assert r.status_code == 200
    assert any(c["slug"] == PILOTO for c in r.json()["capitulos"])

    r2 = cliente.get(f"/ajuda/{PILOTO}")
    assert r2.status_code == 200
    corpo = r2.json()
    assert corpo["titulo"] and corpo["corpo"]

    assert cliente.get("/ajuda/nao/existe").status_code == 404


def test_prompt_da_criadora_referencia_a_central():
    prompt = montar_prompt_criadora()
    assert "consultar_conhecimento" in prompt
    assert "Narrar texto (voz)" in prompt  # o índice de títulos foi injetado


def test_system_criadora_marca_o_cache():
    # Parte D: o prompt vira SystemMessage SÓ com o bloco estável, marcado para cache.
    sm = montar_system_criadora()
    assert isinstance(sm.content, list) and len(sm.content) == 1
    assert sm.content[0]["cache_control"] == {"type": "ephemeral"}
    assert "consultar_conhecimento" in sm.content[0]["text"]  # é o bloco estável


def test_volatil_sai_do_sistema_na_anthropic():
    # A foto/memória mudam a cada edição; no sistema, à frente do histórico, derrubavam o
    # cache da conversa inteira. Na Anthropic vêm À PARTE (o laço as põe depois da fala).
    snap = {"time": {"nome": "X"}}
    mem = [{"categoria": "fato", "conteudo": "y"}]
    estavel, volatil = _blocos_criadora(snap, mem)
    sm, vol = prompt_criadora("claude-sonnet-5", snap, mem)
    assert sm.content[0]["text"] == estavel and len(sm.content) == 1
    assert vol == volatil
    # Sem nada volátil, não há o que mandar à parte.
    assert prompt_criadora("claude-sonnet-5")[1] is None


def test_prompt_texto_igual_a_juncao_dos_blocos():
    # O conteúdo é o MESMO de antes: o texto puro é a junção estável + volátil.
    snap = {"time": {"nome": "X"}}
    mem = [{"categoria": "fato", "conteudo": "y"}]
    estavel, volatil = _blocos_criadora(snap, mem)
    assert montar_prompt_criadora(snap, mem) == estavel + "\n\n" + volatil
    assert montar_prompt_criadora() == _blocos_criadora(None, None)[0]  # sem volátil


def test_prompt_criadora_escolhe_formato_por_provedor():
    # Cache é só da Anthropic: SystemMessage lá; texto puro em OpenAI/Google/desconhecido
    # (a criadora aceita outros provedores — cache_control quebraria/seria ignorado lá).
    assert isinstance(prompt_criadora("claude-sonnet-5")[0], SystemMessage)
    assert isinstance(prompt_criadora("claude-opus-4-8")[0], SystemMessage)
    # Fora da Anthropic, tudo como antes: texto puro COMPLETO, nada à parte.
    snap = {"time": {"nome": "X"}}
    assert prompt_criadora("gpt-4o", snap) == (montar_prompt_criadora(snap), None)
    assert isinstance(prompt_criadora("gemini-2.5-pro")[0], str)
    assert isinstance(prompt_criadora("modelo-desconhecido-xyz")[0], str)  # seguro
