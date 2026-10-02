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

    monkeypatch.setattr(srv, "_cliente", lambda timeout=None: Cliente())
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
        assert tipo.provedores_ia == ("anthropic", "openai", "google")
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


# ── Gerar arquivo e analisar dados ───────────────────────────────────────────────


def _anthropic_com_arquivos(monkeypatch, respostas, arquivos_gerados):
    """Cliente falso com a rota beta (execução de código) e a API de arquivos."""
    from instrumentos import gerar_arquivo as ga

    pedidos: list[dict] = []
    subidos: list[tuple] = []
    fila = list(respostas)

    class Meta:
        def __init__(self, nome, tipo):
            self.filename, self.mime_type = nome, tipo

    class Baixado:
        def __init__(self, dados):
            self._dados = dados

        def read(self):
            return self._dados

    class Arquivos:
        def upload(self, file):
            subidos.append(file)

            class Enviado:
                id = f"file_entrada_{len(subidos)}"
            return Enviado()

        def retrieve_metadata(self, file_id):
            nome, tipo, _ = arquivos_gerados[file_id]
            return Meta(nome, tipo)

        def download(self, file_id):
            return Baixado(arquivos_gerados[file_id][2])

    class Mensagens:
        def create(self, **kw):
            pedidos.append(kw)
            return fila.pop(0)

    class Beta:
        messages = Mensagens()
        files = Arquivos()

    class Cliente:
        beta = Beta()

    monkeypatch.setattr(srv, "_cliente", lambda timeout=None: Cliente())
    salvos: list[tuple] = []
    monkeypatch.setattr(ga.arquivos, "salvar",
                        lambda nome, dados, tipo: salvos.append((nome, dados, tipo)) or f"https://batuta/{nome}")
    return pedidos, subidos, salvos


def _resultado_com_arquivo(file_id):
    return {"type": "bash_code_execution_tool_result", "content": {
        "type": "bash_code_execution_result", "return_code": 0, "stdout": "", "stderr": "",
        "content": [{"type": "bash_code_execution_output", "file_id": file_id}]}}


def test_gerar_arquivo_sobe_entrada_gera_e_guarda_no_batuta(monkeypatch):
    from instrumentos import gerar_arquivo as ga

    pedidos, subidos, salvos = _anthropic_com_arquivos(monkeypatch, [_Resposta([
        {"type": "text", "text": "vou montar"},
        {"type": "server_tool_use", "name": "bash_code_execution"},
        _resultado_com_arquivo("file_saida_1"),
        {"type": "text", "text": "Planilha pronta: total 370."},
    ])], {"file_saida_1": ("resumo.xlsx", "application/vnd.ms-excel", b"PK..")})
    monkeypatch.setattr(ga.httpx, "get", lambda url, **k: httpx.Response(
        200, content=b"a,b\n1,2\n", headers={"content-type": "text/csv"}))
    tipo = encaixe.obter_tipo("gerar_arquivo")
    r = tipo.executar(tipo.Config(formatos=["xlsx"]), tipo.Args(
        instrucao="resuma em planilha", arquivos_url=["https://x.com/dados.csv"]))
    # a resposta é só o texto final, sem a narração do meio
    assert r["resumo"] == "Planilha pronta: total 370."
    assert r["arquivos"][0]["nome"] == "resumo.xlsx"
    assert r["arquivos"][0]["url"].startswith("https://batuta/") and salvos[0][1] == b"PK.."
    assert subidos[0][0] == "dados.csv"
    pedido = pedidos[0]
    assert pedido["betas"] == ga.BETAS
    assert pedido["container"] == {"skills": [{"type": "anthropic", "skill_id": "xlsx", "version": "latest"}]}
    assert {"type": "container_upload", "file_id": "file_entrada_1"} in pedido["messages"][0]["content"]


def test_gerar_arquivo_sem_arquivo_avisa_o_agente(monkeypatch):
    _anthropic_com_arquivos(monkeypatch, [_Resposta([{"type": "text", "text": "a média é 5"}])], {})
    tipo = encaixe.obter_tipo("gerar_arquivo")
    r = tipo.executar(tipo.Config(), tipo.Args(instrucao="calcule a média de 4 e 6"))
    assert r["arquivos"] == [] and "Nenhum arquivo" in r["aviso"]


def test_gerar_arquivo_continua_no_mesmo_espaco_de_execucao(monkeypatch):
    pausa = _Resposta([{"type": "server_tool_use", "name": "bash_code_execution"}], stop="pause_turn")

    class Container:
        id = "container_abc"
    pausa.container = Container()
    pedidos, _, _ = _anthropic_com_arquivos(monkeypatch, [pausa, _Resposta([{"type": "text", "text": "ok"}])], {})
    tipo = encaixe.obter_tipo("gerar_arquivo")
    tipo.executar(tipo.Config(), tipo.Args(instrucao="algo demorado"))
    assert pedidos[1]["container"] == "container_abc"


def test_gerar_arquivo_recusa_entrada_sem_https_e_em_excesso():
    tipo = encaixe.obter_tipo("gerar_arquivo")
    with pytest.raises(FalhaInstrumento, match="no máximo"):
        tipo.executar(tipo.Config(), tipo.Args(instrucao="xxxxx", arquivos_url=["https://a"] * 11))


def test_espera_longa_publica_sinal_de_vida(monkeypatch):
    import time as _time

    from orquestracao import atividade

    monkeypatch.setattr(srv, "INTERVALO_BATIMENTO_S", 0.01)
    frases: list[str] = []
    with atividade.usar_atividade(frases.append):
        valor = srv._com_batimento(lambda: _time.sleep(0.05) or 42, "Gerando o arquivo")
    assert valor == 42 and frases and frases[0].startswith("Gerando o arquivo (")


# ── Melhorias do uso real (02/10/2026) ───────────────────────────────────────────


def test_argumento_com_nome_errado_e_recusado_dizendo_os_certos():
    tipo = encaixe.obter_tipo("ler_pagina")
    with pytest.raises(ValueError, match="argumento desconhecido.*pedido.*o_que_extrair, url"):
        encaixe.validar_argumentos(tipo, {"url": "https://x.com", "pedido": "a tabela"})


def test_agente_que_erra_o_nome_do_argumento_recebe_o_erro(monkeypatch):
    import orquestracao.agente as agente_mod
    from modelos import Instrumento

    chamado = []
    monkeypatch.setattr(agente_mod, "acionar_com_retentativa", lambda *a: chamado.append(a))
    tipo = encaixe.obter_tipo("descrever_imagem")
    inst = Instrumento(time_id=uuid.uuid4(), nome="Visão", tipo="descrever_imagem", configuracao={})
    inst.id = uuid.uuid4()
    ferramenta = agente_mod._ferramenta_unica(inst, tipo, tipo.Config(), [], {}, [], {})
    saida = json.loads(ferramenta.func(imagens_url=["https://x/a.png"], pergunta="o que é?"))
    assert saida["ok"] is False and "instrucao" in saida["erro"] and not chamado


def test_catalogo_do_mcp_mostra_os_argumentos():
    from criacao.ferramentas import catalogo_de_instrumentos

    mcp = {t["tipo"]: t for t in catalogo_de_instrumentos(com_argumentos=True)}
    args = {a["nome"]: a for a in mcp["ler_pagina"]["argumentos"]}
    assert args["url"]["obrigatorio"] is True and args["o_que_extrair"]["obrigatorio"] is False
    # o roteiro da IA criadora segue enxuto
    assert "argumentos" not in catalogo_de_instrumentos()[0]


def test_pesquisa_sabe_a_data_de_hoje_e_respeita_o_desde(monkeypatch):
    from datetime import date

    pedidos = _anthropic_falsa(monkeypatch, [_Resposta([
        {"type": "web_search_tool_result", "content": [
            {"type": "web_search_result", "title": "T", "url": "https://a.com", "page_age": "2 days ago"},
        ]},
        {"type": "text", "text": "ok"},
    ])])
    tipo = encaixe.obter_tipo("pesquisar_web")
    r = tipo.executar(tipo.Config(), tipo.Args(pergunta="notícias de IA", desde=date(2026, 9, 25)))
    assert "Hoje é " in pedidos[0]["system"] and "a partir de 25/09/2026" in pedidos[0]["system"]
    assert r["fontes"] == [{"titulo": "T", "url": "https://a.com", "idade": "2 days ago"}]


def test_resumo_do_arquivo_sem_caminho_interno():
    from instrumentos.gerar_arquivo import _sem_caminho_interno

    assert _sem_caminho_interno("Arquivo salvo em `$OUTPUT_DIR/resumo.xlsx`. Total 370.") == "Total 370."
    assert _sem_caminho_interno("A planilha ($OUTPUT_DIR/a.xlsx) tem 2 abas.") == "A planilha tem 2 abas."
