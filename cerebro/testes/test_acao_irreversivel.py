"""Irreversibilidade dos instrumentos — agora resolvida por (tipo + config + interruptor).

Irreversível = age no mundo externo sem desfazer (publicar/enviar/gravar/apagar). É o
que a parede de ativação usa para exigir portão humano. Mas uma CONSULTA (REST GET, SQL
somente-leitura, busca) não muda nada e não exige portão. O interruptor por instância
(`exige_aprovacao`) sobrepõe a derivação."""

import instrumentos as encaixe
from criacao.ferramentas import catalogo_de_instrumentos

# Baseline por tipo (o que o catálogo expõe à IA): o tipo PODE escrever?
# `disparar_webhook` é gatilho de automação em massa → NÃO exige portão (decisão
# do maestro); por isso está no baseline FALSE, não no TRUE.
_BASELINE_TRUE = {
    "publicar_wordpress", "chamar_api_rest", "banco_sql",
    "conectar_mcp",
}
_BASELINE_FALSE = {"busca_web", "gerar_pdf", "gerar_imagem", "disparar_webhook"}


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
    for tipo in ("publicar_wordpress", "conectar_mcp"):
        assert encaixe.acao_irreversivel(tipo, {}) is True, tipo


def test_webhook_nao_exige_portao():
    """Webhook de saída é gatilho de automação em massa: por padrão (automático)
    NÃO gateia. O interruptor por nó ainda pode forçar ou dispensar."""
    assert encaixe.acao_irreversivel("disparar_webhook", {}) is False
    assert encaixe.exige_portao("disparar_webhook", {}, None) is False
    # quem quiser barrar um webhook específico ainda força pelo interruptor:
    assert encaixe.exige_portao("disparar_webhook", {}, True) is True


def test_tipos_de_leitura():
    for tipo in _BASELINE_FALSE:
        assert encaixe.acao_irreversivel(tipo, {}) is False, tipo


def test_tipo_desconhecido_e_reversivel():
    assert encaixe.acao_irreversivel("nao_existe") is False
    assert encaixe.exige_portao("nao_existe", {}, None) is False


def test_interruptor_sobrepoe_a_derivacao():
    # None = automático (deriva)
    assert encaixe.exige_portao("chamar_api_rest", {"metodo": "GET"}, None) is False
    assert encaixe.exige_portao("chamar_api_rest", {"metodo": "POST"}, None) is True
    # True força portão até num GET; False dispensa até numa escrita (guard-rail = UI)
    assert encaixe.exige_portao("chamar_api_rest", {"metodo": "GET"}, True) is True
    assert encaixe.exige_portao("disparar_webhook", {}, False) is False
