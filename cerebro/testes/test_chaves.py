"""Testes da resolução da chave de IA (Fase 7.3).

Provam a ordem de fallback (organização → chave-mãe da consultoria → None) e que
a chave resolvida realmente chega ao cliente da LLM via `usar_chave`, sem tocar
no motor de grafo. Não fazem chamada real à IA — só constroem o cliente e leem
de onde veio a chave.
"""

import uuid

from cofre import cifrar, ultimos4
from chaves import (
    ORIGEM_CONSULTORIA,
    ORIGEM_LEGADO,
    ORIGEM_ORGANIZACAO,
    resolver_chave,
    resolver_chave_e_origem_por_time,
    resolver_chave_por_time,
    resolver_chaves_por_organizacao,
)
from modelos import ChaveApi
from orquestracao.llm import construir_modelo, usar_chaves
from orquestracao.modelos_ia import provedor_do_modelo


def _add_chave(
    sessao, organizacao_id, segredo, *, provedor="anthropic", ativa=True
):
    chave = ChaveApi(
        organizacao_id=organizacao_id,
        provedor=provedor,
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


def test_uma_chave_por_provedor_serve_qualquer_uso(sessao, dados):
    """Unificação 2026-06-15: a chave é por provedor, sem dimensão de papel. Uma
    chave Anthropic cadastrada serve tanto à execução quanto à conversa — quem
    escolhe a IA é o modelo, não a chave."""
    _add_chave(sessao, dados["orgA"].id, "sk-anthropic")
    # A mesma chave resolve, sem distinção de papel (não há mais `tipo_ia`).
    assert resolver_chave(sessao, dados["orgA"].id) == "sk-anthropic"
    chaves, _ = resolver_chaves_por_organizacao(sessao, dados["orgA"].id)
    assert chaves["anthropic"] == "sk-anthropic"


def test_resolver_por_time_segue_a_organizacao(sessao, dados):
    """A fronteira do motor conhece o time; a chave segue a organização dele."""
    _add_chave(sessao, dados["orgA"].id, "sk-org-A")
    assert resolver_chave_por_time(sessao, dados["timeA"].id) == "sk-org-A"


def test_resolver_por_time_inexistente_resolve_none(sessao, dados):
    _add_chave(sessao, None, "sk-consultoria")
    # Time fora do banco: organização indefinida → ainda assim cai na chave-mãe.
    assert resolver_chave_por_time(sessao, uuid.uuid4()) == "sk-consultoria"


# ─────────────────── Origem da chave (medição, Fase 7.6) ────────────────────


def test_origem_organizacao(sessao, dados):
    _add_chave(sessao, dados["orgA"].id, "sk-org-A")
    chave, origem = resolver_chave_e_origem_por_time(sessao, dados["timeA"].id)
    assert chave == "sk-org-A" and origem == ORIGEM_ORGANIZACAO


def test_origem_consultoria(sessao, dados):
    _add_chave(sessao, None, "sk-mae")
    chave, origem = resolver_chave_e_origem_por_time(sessao, dados["timeA"].id)
    assert chave == "sk-mae" and origem == ORIGEM_CONSULTORIA


def test_origem_legado_sem_chave(sessao, dados):
    chave, origem = resolver_chave_e_origem_por_time(sessao, dados["timeA"].id)
    assert chave is None and origem == ORIGEM_LEGADO


def test_construir_modelo_usa_chave_do_contexto():
    """A chave do provedor fixada por `usar_chaves` chega ao cliente da LLM."""
    with usar_chaves({"anthropic": "sk-do-contexto"}):
        modelo = construir_modelo("claude-haiku-4-5")
    assert modelo.anthropic_api_key.get_secret_value() == "sk-do-contexto"


def test_fora_do_contexto_cai_no_ambiente():
    """Sem chave no contexto, o cliente Anthropic usa a ANTHROPIC_API_KEY do
    ambiente — o comportamento legado, preservado (retrocompatibilidade)."""
    import os

    esperado = os.environ.get("ANTHROPIC_API_KEY", "")
    modelo = construir_modelo("claude-haiku-4-5")
    assert modelo.anthropic_api_key.get_secret_value() == esperado


# ─────────────────── Multi-provedor (Fase 7-A) ────────────────────


def test_provedor_do_modelo_por_prefixo():
    assert provedor_do_modelo("claude-haiku-4-5") == "anthropic"
    assert provedor_do_modelo("gpt-4o") == "openai"
    assert provedor_do_modelo("gemini-2.0-flash") == "google"


def test_construir_modelo_openai_usa_chave_do_contexto():
    """Modelo OpenAI constrói um ChatOpenAI com a chave OpenAI do contexto."""
    with usar_chaves({"openai": "sk-openai-xyz"}):
        modelo = construir_modelo("gpt-4o")
    assert type(modelo).__name__ == "ChatOpenAI"
    assert modelo.openai_api_key.get_secret_value() == "sk-openai-xyz"


def test_construir_modelo_sem_chave_do_provedor_falha(dados):
    """Modelo OpenAI sem chave OpenAI no contexto falha de forma clara (não há
    fallback de ambiente para os provedores não-Anthropic)."""
    import pytest

    with usar_chaves({"anthropic": "sk-só-anthropic"}):
        with pytest.raises(RuntimeError, match="OpenAI"):
            construir_modelo("gpt-4o")


def test_construir_modelo_aplica_timeout_finito():
    """Toda chamada de IA tem timeout FINITO — uma conexão pendurada falha em vez de
    travar o trabalhador da fila para sempre (causa raiz de execução órfã)."""
    from orquestracao.llm import TIMEOUT_IA_S

    with usar_chaves({"anthropic": "sk-x"}):
        m = construir_modelo("claude-haiku-4-5")
    assert getattr(m, "default_request_timeout", None) == TIMEOUT_IA_S
    with usar_chaves({"openai": "sk-y"}):
        o = construir_modelo("gpt-4o")
    assert getattr(o, "request_timeout", None) == TIMEOUT_IA_S


def test_construir_modelo_aplica_retentativa():
    """Toda chamada de IA retenta com backoff numa sobrecarga transitória (529/5xx) —
    um pico de poucos segundos não derruba mais uma execução longa (exec 132bcaa6)."""
    from orquestracao.llm import MAX_RETENTATIVAS_IA

    with usar_chaves({"anthropic": "sk-x"}):
        m = construir_modelo("claude-haiku-4-5")
    assert getattr(m, "max_retries", None) == MAX_RETENTATIVAS_IA
    with usar_chaves({"openai": "sk-y"}):
        o = construir_modelo("gpt-4o")
    assert getattr(o, "max_retries", None) == MAX_RETENTATIVAS_IA


def test_resolver_chaves_por_time_mapa_por_provedor(sessao, dados):
    """A fronteira resolve um mapa {provedor: chave} para a org do time."""
    from chaves import resolver_chaves_por_time

    _add_chave(sessao, dados["orgA"].id, "sk-org-anthropic")
    _add_chave(sessao, dados["orgA"].id, "sk-org-openai", provedor="openai")
    chaves, origens = resolver_chaves_por_time(sessao, dados["timeA"].id)
    assert chaves["anthropic"] == "sk-org-anthropic"
    assert chaves["openai"] == "sk-org-openai"
    assert origens["anthropic"] == ORIGEM_ORGANIZACAO
    assert "google" not in chaves  # sem chave Google cadastrada


# ─────────────────── Resolução por organização (conversa/criadora) ──────────


def test_resolver_chaves_por_organizacao(sessao, dados):
    """A conversa (IA criadora) resolve a chave por ORGANIZAÇÃO, seguindo o mesmo
    fallback org → consultoria. É a MESMA chave por provedor da execução
    (unificação 2026-06-15)."""
    _add_chave(sessao, dados["orgA"].id, "sk-org-A")
    chaves, origens = resolver_chaves_por_organizacao(sessao, dados["orgA"].id)
    assert chaves["anthropic"] == "sk-org-A"
    assert origens["anthropic"] == ORIGEM_ORGANIZACAO
    # sem chave própria, cai no legado (.env) para a Anthropic
    vazio, origens_b = resolver_chaves_por_organizacao(sessao, dados["orgB"].id)
    assert "anthropic" not in vazio
    assert origens_b["anthropic"] == ORIGEM_LEGADO
