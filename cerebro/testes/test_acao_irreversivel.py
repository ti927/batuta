"""Metadado `acao_irreversivel` dos tipos de instrumento (base da parede de ativação).

Irreversível = age no mundo externo sem desfazer (publicar/enviar/gravar). É o que
a parede de ativação usa para exigir portão humano antes do agente que o usa."""

import instrumentos as encaixe
from criacao.ferramentas import catalogo_de_instrumentos

_IRREVERSIVEIS = {
    "publicar_wordpress",
    "disparar_webhook",
    "chamar_api_rest",
    "banco_sql",
    "conectar_mcp",
}
_REVERSIVEIS = {"busca_web", "gerar_pdf", "gerar_imagem"}


def test_helper_marca_irreversiveis():
    for tipo in _IRREVERSIVEIS:
        assert encaixe.acao_irreversivel(tipo) is True, tipo
    for tipo in _REVERSIVEIS:
        assert encaixe.acao_irreversivel(tipo) is False, tipo


def test_tipo_desconhecido_e_reversivel_por_seguranca_de_leitura():
    # tipo inexistente: o helper não explode e devolve False (não há o que ativar)
    assert encaixe.acao_irreversivel("nao_existe") is False


def test_catalogo_expoe_acao_irreversivel():
    por_tipo = {c["tipo"]: c for c in catalogo_de_instrumentos()}
    # todo tipo do catálogo traz o campo
    assert all("acao_irreversivel" in c for c in por_tipo.values())
    for tipo in _IRREVERSIVEIS:
        assert por_tipo[tipo]["acao_irreversivel"] is True
    for tipo in _REVERSIVEIS:
        assert por_tipo[tipo]["acao_irreversivel"] is False
