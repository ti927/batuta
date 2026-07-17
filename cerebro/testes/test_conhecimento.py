"""Central de Conhecimento: o leitor (`conhecimento.py`), as rotas `/ajuda` e o wiring
da consulta/prompt da IA criadora. O acervo real (cerebro/central/*.md) é a fonte."""

import conhecimento
from criacao.prompt import montar_prompt_criadora

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
