"""Testes da resolução da chave de IA (Fase 7.3).

Provam a ordem de fallback (organização → chave-mãe da consultoria → None) e que
a chave resolvida realmente chega ao cliente da LLM via `usar_chave`, sem tocar
no motor de grafo. Não fazem chamada real à IA — só constroem o cliente e leem
de onde veio a chave.
"""

import uuid

from cofre import cifrar, ultimos4
from chaves import resolver_chave, resolver_chave_por_time
from modelos import ChaveApi
from orquestracao.llm import construir_modelo, usar_chave


def _add_chave(sessao, organizacao_id, segredo, *, tipo_ia="executora", ativa=True):
    chave = ChaveApi(
        organizacao_id=organizacao_id,
        tipo_ia=tipo_ia,
        provedor="anthropic",
        valor_cifrado=cifrar(segredo),
        ultimos4=ultimos4(segredo),
        ativa=ativa,
    )
    sessao.add(chave)
    sessao.flush()
    return chave


def test_sem_chave_cadastrada_resolve_none(sessao, dados):
    """Cofre vazio: nada quebra — resolve None e o motor cai no .env legado."""
    assert resolver_chave(sessao, dados["orgA"].id) is None


def test_usa_a_chave_da_organizacao(sessao, dados):
    _add_chave(sessao, dados["orgA"].id, "sk-org-A")
    assert resolver_chave(sessao, dados["orgA"].id) == "sk-org-A"


def test_fallback_para_chave_mae_da_consultoria(sessao, dados):
    """Sem chave própria, usa a chave-mãe (organizacao_id nulo)."""
    _add_chave(sessao, None, "sk-consultoria")
    assert resolver_chave(sessao, dados["orgA"].id) == "sk-consultoria"


def test_chave_da_organizacao_vence_a_chave_mae(sessao, dados):
    _add_chave(sessao, None, "sk-consultoria")
    _add_chave(sessao, dados["orgA"].id, "sk-org-A")
    assert resolver_chave(sessao, dados["orgA"].id) == "sk-org-A"
    # Outra organização, sem chave própria, ainda cai na chave-mãe.
    assert resolver_chave(sessao, dados["orgB"].id) == "sk-consultoria"


def test_chave_inativa_e_ignorada(sessao, dados):
    """Uma chave da organização desativada não é usada — cai no fallback."""
    _add_chave(sessao, dados["orgA"].id, "sk-org-A", ativa=False)
    _add_chave(sessao, None, "sk-consultoria")
    assert resolver_chave(sessao, dados["orgA"].id) == "sk-consultoria"


def test_tipo_ia_isolado(sessao, dados):
    """Só a IA executora é consumida pelo motor nesta fase: uma chave de outro
    tipo (criadora) não responde pela executora."""
    _add_chave(sessao, dados["orgA"].id, "sk-criadora", tipo_ia="criadora")
    assert resolver_chave(sessao, dados["orgA"].id, tipo_ia="executora") is None
    assert resolver_chave(sessao, dados["orgA"].id, tipo_ia="criadora") == "sk-criadora"


def test_resolver_por_time_segue_a_organizacao(sessao, dados):
    """A fronteira do motor conhece o time; a chave segue a organização dele."""
    _add_chave(sessao, dados["orgA"].id, "sk-org-A")
    assert resolver_chave_por_time(sessao, dados["timeA"].id) == "sk-org-A"


def test_resolver_por_time_inexistente_resolve_none(sessao, dados):
    _add_chave(sessao, None, "sk-consultoria")
    # Time fora do banco: organização indefinida → ainda assim cai na chave-mãe.
    assert resolver_chave_por_time(sessao, uuid.uuid4()) == "sk-consultoria"


def test_construir_modelo_usa_chave_do_contexto():
    """A chave fixada por `usar_chave` chega ao cliente da LLM."""
    with usar_chave("sk-do-contexto"):
        modelo = construir_modelo("claude-haiku-4-5")
    assert modelo.anthropic_api_key.get_secret_value() == "sk-do-contexto"


def test_fora_do_contexto_cai_no_ambiente():
    """Sem chave no contexto, o cliente usa a ANTHROPIC_API_KEY do ambiente —
    o comportamento legado, preservado (retrocompatibilidade da 7.3)."""
    import os

    esperado = os.environ.get("ANTHROPIC_API_KEY", "")
    modelo = construir_modelo("claude-haiku-4-5")
    assert modelo.anthropic_api_key.get_secret_value() == esperado
