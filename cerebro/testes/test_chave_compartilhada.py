"""Testes do reuso de chave de serviço compartilhada (unificação de chaves).

Um instrumento que declara `chave_compartilhada` (ex.: gerar_imagem→openai) reusa
a chave do pool da organização quando não tem chave própria. A injeção é na borda
(`anexar_aos_instrumentos`), lendo o contexto `usar_chaves`. Também cobre que o pool
(`chaves.py`) é só de provedores de IA desde 2026-10-01."""

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


def test_instrumento_sem_chave_compartilhada_nao_recebe_injecao(sessao, dados):
    # gerar_pdf não declara chave_compartilhada → nada é injetado.
    inst = _instrumento(sessao, dados, tipo="gerar_pdf")
    with usar_chaves({"openai": "POOL-KEY"}):
        si.anexar_aos_instrumentos(sessao, [inst])
    assert inst.segredos_decifrados == {}


# ───────────────── o pool é só de provedores de IA (chaves.py) ─────────────────


def test_pool_so_tem_provedores_de_ia():
    from orquestracao.modelos_ia import PROVEDORES

    assert tuple(ch.SERVICOS) == tuple(PROVEDORES)
    assert ch.SERVICOS_COM_LEGADO == frozenset({"anthropic"})


def test_chave_antiga_de_servico_nao_entra_no_pool(sessao, dados):
    # Uma chave Tavily que tenha sobrado no cofre não é mais resolvida.
    org = dados["orgA"].id
    sessao.add(
        ChaveApi(
            organizacao_id=org, provedor="tavily",
            valor_cifrado=cofre.cifrar("tvly-123"), ultimos4="-123", ativa=True,
        )
    )
    sessao.flush()
    chaves_map, origens = ch.resolver_chaves_por_organizacao(sessao, org)
    assert "tavily" not in chaves_map and "tavily" not in origens
