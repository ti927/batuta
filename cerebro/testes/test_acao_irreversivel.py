"""Irreversibilidade dos instrumentos — resolvida por (tipo + config).

Irreversível = age no mundo externo sem desfazer (publicar/enviar/gravar/apagar). É o
que a parede de ativação usa para exigir portão humano. Mas uma CONSULTA (REST GET, SQL
somente-leitura, busca) não muda nada e não exige portão. Não há mais interruptor por
instrumento: a parede liga/desliga por ORGANIZAÇÃO (ver test_portao_ativacao)."""

import instrumentos as encaixe
from criacao.ferramentas import catalogo_de_instrumentos

# Baseline por tipo (o que o catálogo expõe à IA): o tipo PODE escrever?
# As integrações de mercado (WordPress, busca, webhook de saída…) saíram do catálogo em
# 2026-10-01 — viraram personalizado.
# `chamar_api_rest` saiu do catálogo das IAs em 2026-09-29 (substituído na criação pelo
# conector) — o baseline dele segue provado em `test_rest_deriva_do_metodo`.
_BASELINE_TRUE = {"enviar_telegram", "banco_sql", "conectar_mcp", "pedir_aprovacao"}
_BASELINE_FALSE = {"gerar_pdf", "gerar_imagem", "agendar_automacao", "quadro"}


def test_catalogo_expoe_baseline_do_tipo():
    por_tipo = {c["tipo"]: c for c in catalogo_de_instrumentos()}
    assert all("acao_irreversivel" in c for c in por_tipo.values())
    for tipo in _BASELINE_TRUE:
        assert por_tipo[tipo]["acao_irreversivel"] is True, tipo
    for tipo in _BASELINE_FALSE:
        assert por_tipo[tipo]["acao_irreversivel"] is False, tipo


def test_rest_deriva_do_metodo():
    assert encaixe.acao_irreversivel("chamar_api_rest", {"metodo": "GET"}) is False
    assert encaixe.acao_irreversivel("chamar_api_rest", {"metodo": "HEAD"}) is False
    assert encaixe.acao_irreversivel("chamar_api_rest", {"metodo": "POST"}) is True
    assert encaixe.acao_irreversivel("chamar_api_rest", {"metodo": "DELETE"}) is True
    # sem config: cai no default do método (GET) → leitura
    assert encaixe.acao_irreversivel("chamar_api_rest") is False


def test_sql_deriva_do_somente_leitura():
    assert encaixe.acao_irreversivel("banco_sql", {}) is True
    assert encaixe.acao_irreversivel("banco_sql", {"somente_leitura": True}) is False
    assert encaixe.acao_irreversivel("banco_sql", {"somente_leitura": False}) is True


def test_tipos_que_sempre_escrevem():
    for tipo in ("enviar_telegram", "conectar_mcp"):
        assert encaixe.acao_irreversivel(tipo, {}) is True, tipo


def test_webhook_nao_exige_portao():
    """Webhook de saída é gatilho de automação em massa: NÃO é irreversível para a
    parede (não gateia)."""
    assert encaixe.acao_irreversivel("disparar_webhook", {}) is False


def test_tipos_de_leitura():
    for tipo in _BASELINE_FALSE:
        assert encaixe.acao_irreversivel(tipo, {}) is False, tipo


def test_tipo_desconhecido_e_reversivel():
    assert encaixe.acao_irreversivel("nao_existe") is False
