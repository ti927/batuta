"""Central de Conhecimento: o leitor (`conhecimento.py`), as rotas `/ajuda` e o wiring
da consulta/prompt da IA criadora. O acervo real (cerebro/central/*.md) é a fonte."""

import conhecimento
from criacao.prompt import (
    _blocos_criadora,
    montar_prompt_criadora,
    montar_system_criadora,
)

PILOTO = "instrumentos/publicar-instagram"


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
    assert "instagram" in cap.tags  # lista do frontmatter parseada
    assert "## Para a IA" in cap.corpo  # corpo sem frontmatter, com as seções


def test_obter_inexistente_devolve_none():
    assert conhecimento.obter("nao/existe") is None


def test_busca_encontra_e_vazio_nao_quebra():
    achados = conhecimento.buscar("publicar story no instagram")
    assert achados and achados[0].slug == PILOTO
    assert conhecimento.buscar("zzxqwnadaaqui") == []
    assert conhecimento.buscar("") == []


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
    assert "Publicar no Instagram" in prompt  # o índice de títulos foi injetado


def test_system_criadora_marca_o_cache():
    # Parte D: o prompt vira SystemMessage com o bloco estável marcado para cache.
    sm = montar_system_criadora()
    assert isinstance(sm.content, list) and sm.content
    assert sm.content[0]["cache_control"] == {"type": "ephemeral"}
    assert "consultar_conhecimento" in sm.content[0]["text"]  # é o bloco estável
    # Com fotografia + memória, ganha um 2º bloco (volátil) também marcado.
    sm2 = montar_system_criadora(
        {"time": {"nome": "X"}}, [{"categoria": "fato", "conteudo": "y"}]
    )
    assert len(sm2.content) == 2
    assert all(b["cache_control"] == {"type": "ephemeral"} for b in sm2.content)


def test_prompt_texto_igual_a_juncao_dos_blocos():
    # O conteúdo é o MESMO de antes: o texto puro é a junção estável + volátil.
    snap = {"time": {"nome": "X"}}
    mem = [{"categoria": "fato", "conteudo": "y"}]
    estavel, volatil = _blocos_criadora(snap, mem)
    assert montar_prompt_criadora(snap, mem) == estavel + "\n\n" + volatil
    assert montar_prompt_criadora() == _blocos_criadora(None, None)[0]  # sem volátil
