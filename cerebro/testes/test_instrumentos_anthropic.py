"""Instrumentos que usam as ferramentas que rodam na Anthropic (2026-10-02): Pesquisar
na web, Ler página da web e Ler documento (PDF). A Anthropic é simulada aqui (as
respostas imitam o formato real, conferido ao vivo); nada vai à rede."""

import json
import uuid

import httpx
import pytest

import anthropic
import instrumentos as encaixe
from instrumentos import anthropic_servidor as srv
from instrumentos.base import FalhaInstrumento
from orquestracao import gasto_instrumentos


class _Bloco:
    def __init__(self, dados: dict):
        self._dados = dados

    def model_dump(self):
        return dict(self._dados)


class _Resposta:
    def __init__(self, blocos, stop="end_turn", entrada=1000, saida=100, buscas=0):
        self.content = [_Bloco(b) for b in blocos]
        self.stop_reason = stop
        self.usage = {
            "input_tokens": entrada, "output_tokens": saida,
            "server_tool_use": {"web_search_requests": buscas},
        }


def _anthropic_falsa(monkeypatch, respostas):
    """Troca o cliente da Anthropic por um que devolve `respostas` em ordem e guarda
    cada pedido em `pedidos`."""
    pedidos: list[dict] = []
    fila = list(respostas)

    class Mensagens:
        def create(self, **kw):
            pedidos.append(kw)
            item = fila.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    class Cliente:
        messages = Mensagens()

    monkeypatch.setattr(srv, "_cliente", lambda: Cliente())
    return pedidos


def _erro_api(classe, status, mensagem):
    resp = httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    return classe(mensagem, response=resp, body=None)


# ── Pesquisar na web ─────────────────────────────────────────────────────────────


def test_pesquisa_devolve_resposta_fontes_e_custo_real(monkeypatch):
    pedidos = _anthropic_falsa(monkeypatch, [_Resposta([
        {"type": "server_tool_use", "name": "web_search", "input": {"query": "selic"}},
        {"type": "web_search_tool_result", "content": [
            {"type": "web_search_result", "title": "Copom", "url": "https://bcb.gov.br/a"},
        ]},
        {"type": "text", "text": "A Selic está em 13,75%.",
         "citations": [{"type": "web_search_result_location", "url": "https://bcb.gov.br/a",
                        "title": "Copom"}]},
    ], entrada=10000, saida=200, buscas=2)])
    tipo = encaixe.obter_tipo("pesquisar_web")
    r = tipo.executar(tipo.Config(), tipo.Args(pergunta="Qual a Selic?"))
    assert r["resposta"] == "A Selic está em 13,75%."
    assert r["fontes"] == [{"titulo": "Copom", "url": "https://bcb.gov.br/a"}]
    # Haiku: US$ 1/5 por 1M → 0,01 + 0,001 de tokens + 2 buscas × 0,01
    assert r["uso"]["buscas"] == 2 and r["uso"]["custo_usd"] == pytest.approx(0.031)
    ferramenta = pedidos[0]["tools"][0]
    assert ferramenta["type"] == srv.BUSCA_BASICA  # Haiku usa a versão básica
    assert ferramenta["max_uses"] == 5 and ferramenta["user_location"]["country"] == "BR"


def test_modelo_maior_usa_a_busca_que_filtra(monkeypatch):
    pedidos = _anthropic_falsa(monkeypatch, [_Resposta([{"type": "text", "text": "ok"}])])
    tipo = encaixe.obter_tipo("pesquisar_web")
    tipo.executar(tipo.Config(modelo="claude-sonnet-5", sites_preferidos=["gov.br"]),
                  tipo.Args(pergunta="x y z"))
    assert pedidos[0]["tools"][0]["type"] == srv.BUSCA_NOVA
    assert pedidos[0]["tools"][0]["allowed_domains"] == ["gov.br"]


def test_nao_aceita_os_dois_filtros_de_site():
    tipo = encaixe.obter_tipo("pesquisar_web")
    with pytest.raises(ValueError, match="não os dois"):
        tipo.Config(sites_preferidos=["a.com"], sites_bloqueados=["b.com"])


def test_turno_pausado_continua_de_onde_parou(monkeypatch):
    pedidos = _anthropic_falsa(monkeypatch, [
        _Resposta([{"type": "server_tool_use", "name": "web_search"}], stop="pause_turn", buscas=1),
        _Resposta([{"type": "text", "text": "pronto"}], buscas=1),
    ])
    tipo = encaixe.obter_tipo("pesquisar_web")
    r = tipo.executar(tipo.Config(), tipo.Args(pergunta="algo longo"))
    assert r["resposta"] == "pronto" and r["uso"]["buscas"] == 2
    # A continuação reenvia o pedido + o que já veio — sem acrescentar "continue".
    assert [m["role"] for m in pedidos[1]["messages"]] == ["user", "assistant"]


def test_erro_dentro_do_resultado_vira_falha_clara(monkeypatch):
    # HTTP 200 com bloco de erro: sem tratar, o agente narraria sucesso.
    _anthropic_falsa(monkeypatch, [_Resposta([
        {"type": "web_fetch_tool_result", "content": {"type": "web_fetch_tool_error",
                                                      "error_code": "url_not_accessible"}},
    ])])
    tipo = encaixe.obter_tipo("ler_pagina")
    with pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(url="https://exemplo.com/x"))
    assert "não pôde ser aberta" in str(e.value)
    assert e.value.codigo == "anthropic.url_not_accessible" and e.value.retentavel is False


def test_limite_de_buscas_com_resposta_vira_aviso(monkeypatch):
    _anthropic_falsa(monkeypatch, [_Resposta([
        {"type": "web_search_tool_result", "content": {"error_code": "max_uses_exceeded"}},
        {"type": "text", "text": "achei parcialmente"},
    ])])
    tipo = encaixe.obter_tipo("pesquisar_web")
    r = tipo.executar(tipo.Config(), tipo.Args(pergunta="abc"))
    assert r["avisos"] == ["max_uses_exceeded"]


def test_modelo_desligado_vira_recado_honesto(monkeypatch):
    _anthropic_falsa(monkeypatch, [_erro_api(
        anthropic.NotFoundError, 404,
        "Error code: 404 - {'error': {'type': 'not_found_error', 'message': 'model: claude-haiku-4-5'}}",
    )])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(pergunta="abc"))
    assert "A Anthropic não reconhece mais o modelo" in str(e.value)
    assert e.value.codigo == "ia.modelo_desligado"


def test_chave_recusada_diz_onde_trocar(monkeypatch):
    _anthropic_falsa(monkeypatch, [_erro_api(anthropic.AuthenticationError, 401, "invalid x-api-key")])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with pytest.raises(FalhaInstrumento, match="Organização › Chaves") as e:
        tipo.executar(tipo.Config(), tipo.Args(pergunta="abc"))
    assert e.value.retentavel is False


def test_sem_chave_nenhuma_falha_antes_de_chamar(monkeypatch):
    monkeypatch.setattr(srv, "chaves_atuais", lambda: {})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(FalhaInstrumento) as e:
        srv._chave()
    assert e.value.codigo == "ia.sem_chave"


# ── Ler página e Ler documento ───────────────────────────────────────────────────


def test_ler_pagina_poe_o_link_no_pedido(monkeypatch):
    pedidos = _anthropic_falsa(monkeypatch, [_Resposta([{"type": "text", "text": "conteúdo"}])])
    tipo = encaixe.obter_tipo("ler_pagina")
    r = tipo.executar(tipo.Config(), tipo.Args(url="https://exemplo.com/p", o_que_extrair="o preço"))
    assert r["conteudo"] == "conteúdo"
    # a leitura só abre endereço que já está na conversa
    assert "https://exemplo.com/p" in pedidos[0]["messages"][0]["content"][0]["text"]
    assert pedidos[0]["tools"][0]["max_content_tokens"] == 30000


def test_ler_pagina_recusa_endereco_sem_http():
    tipo = encaixe.obter_tipo("ler_pagina")
    with pytest.raises(FalhaInstrumento, match="http"):
        tipo.executar(tipo.Config(), tipo.Args(url="exemplo.com/abc"))


def test_ler_documento_cita_a_pagina(monkeypatch):
    pedidos = _anthropic_falsa(monkeypatch, [_Resposta([
        {"type": "text", "text": "O valor é R$ 1.200,00.",
         "citations": [{"type": "page_location", "cited_text": "Total: R$ 1.200,00",
                        "start_page_number": 2}]},
    ])])
    tipo = encaixe.obter_tipo("ler_documento")
    r = tipo.executar(tipo.Config(), tipo.Args(url="https://x.com/nota.pdf", pergunta="valor?"))
    assert r["citacoes"] == [{"trecho": "Total: R$ 1.200,00", "pagina": 2}]
    doc = pedidos[0]["messages"][0]["content"][0]
    assert doc["source"] == {"type": "url", "url": "https://x.com/nota.pdf"}
    assert doc["citations"] == {"enabled": True} and "tools" not in pedidos[0]


def test_ler_documento_exige_link_publico_https():
    tipo = encaixe.obter_tipo("ler_documento")
    with pytest.raises(FalhaInstrumento, match="https"):
        tipo.executar(tipo.Config(), tipo.Args(url="http://x.com/nota.pdf"))


# ── Regras gerais ────────────────────────────────────────────────────────────────


def test_sao_prontos_de_ia_da_anthropic_e_so_leem():
    for t in ("pesquisar_web", "ler_pagina", "ler_documento"):
        tipo = encaixe.obter_tipo(t)
        assert tipo.provedores_ia == ("anthropic",)
        assert tipo.acao_irreversivel is False
        assert not encaixe.eh_personalizado(t)


def test_gasto_real_vai_para_o_uso_do_turno_e_sai_do_que_o_agente_le(monkeypatch):
    import orquestracao.agente as agente_mod
    from modelos import Instrumento

    tipo = encaixe.obter_tipo("pesquisar_web")
    monkeypatch.setattr(agente_mod, "acionar_com_retentativa", lambda t, c, a: {
        "ok": True, "resposta": "r", "uso": {"modelo": "claude-haiku-4-5", "custo_usd": 0.02},
    })
    inst = Instrumento(time_id=uuid.uuid4(), nome="Busca", tipo="pesquisar_web", configuracao={})
    inst.id = uuid.uuid4()
    ferramenta = agente_mod._ferramenta_unica(inst, tipo, tipo.Config(), [], {}, [], {})
    with gasto_instrumentos.coletar() as gastos:
        saida = json.loads(ferramenta.func(pergunta="abc"))
    assert "uso" not in saida
    assert gastos == [{
        "modelo": "claude-haiku-4-5", "custo_usd": 0.02, "categoria": "instrumento",
        "instrumento_id": str(inst.id), "instrumento": "Busca", "tipo": "pesquisar_web",
    }]
