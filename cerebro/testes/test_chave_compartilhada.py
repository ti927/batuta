"""Testes do reuso de chave de serviço compartilhada (unificação de chaves).

Um instrumento que declara `chave_compartilhada` (ex.: gerar_imagem→openai,
busca_web→tavily) reusa a chave do pool da organização quando não tem chave
própria. A injeção é na borda (`anexar_aos_instrumentos`), lendo o contexto
`usar_chaves`. Também cobre a resolução do Tavily no pool (`chaves.py`)."""

import chaves as ch
import cofre
import segredos_instrumento as si
from modelos import ChaveApi, Instrumento
from orquestracao.llm import usar_chaves


def _instrumento(sessao, dados, tipo="gerar_imagem", configuracao=None):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="x", tipo=tipo, configuracao=configuracao or {}
    )
    sessao.add(inst)
    sessao.flush()
    return inst


# ───────────────── injeção da chave do pool na borda ─────────────────


def test_injeta_chave_do_pool_quando_sem_propria(sessao, dados):
    inst = _instrumento(sessao, dados, configuracao={"modelo": "dall-e-3"})
    with usar_chaves({"openai": "POOL-KEY"}):
        si.anexar_aos_instrumentos(sessao, [inst])
    assert inst.segredos_decifrados.get("chave_api") == "POOL-KEY"


def test_chave_propria_tem_prioridade_sobre_o_pool(sessao, dados):
    inst = _instrumento(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"chave_api": "PROPRIA"})
    with usar_chaves({"openai": "POOL-KEY"}):
        si.anexar_aos_instrumentos(sessao, [inst])
    assert inst.segredos_decifrados.get("chave_api") == "PROPRIA"


def test_sem_pool_e_sem_propria_fica_sem_chave(sessao, dados):
    inst = _instrumento(sessao, dados)
    with usar_chaves({}):
        si.anexar_aos_instrumentos(sessao, [inst])
    assert not inst.segredos_decifrados.get("chave_api")


def test_busca_web_reusa_tavily_do_pool(sessao, dados):
    inst = _instrumento(sessao, dados, tipo="busca_web")
    with usar_chaves({"tavily": "TVLY-POOL"}):
        si.anexar_aos_instrumentos(sessao, [inst])
    assert inst.segredos_decifrados.get("chave_api") == "TVLY-POOL"


def test_instrumento_sem_chave_compartilhada_nao_recebe_injecao(sessao, dados):
    # gerar_pdf não declara chave_compartilhada → nada é injetado.
    inst = _instrumento(sessao, dados, tipo="gerar_pdf")
    with usar_chaves({"openai": "POOL-KEY"}):
        si.anexar_aos_instrumentos(sessao, [inst])
    assert inst.segredos_decifrados == {}


# ───────────────── resolução do Tavily no pool (chaves.py) ─────────────────


def test_resolve_tavily_do_cofre_da_org(sessao, dados):
    org = dados["orgA"].id
    sessao.add(
        ChaveApi(
            organizacao_id=org,
            tipo_ia="executora",
            provedor="tavily",
            valor_cifrado=cofre.cifrar("tvly-123"),
            ultimos4="-123",
            ativa=True,
        )
    )
    sessao.flush()
    chaves_map, origens = ch.resolver_chaves_por_organizacao(sessao, org)
    assert chaves_map.get("tavily") == "tvly-123"
    assert origens.get("tavily") == ch.ORIGEM_ORGANIZACAO


def test_tavily_sem_chave_marca_legado(sessao, dados):
    chaves_map, origens = ch.resolver_chaves_por_organizacao(sessao, dados["orgB"].id)
    assert "tavily" not in chaves_map
    assert origens.get("tavily") == ch.ORIGEM_LEGADO
