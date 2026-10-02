"""Os instrumentos "por capacidade" quando o modelo escolhido é da OpenAI (2026-10-02):
Pesquisar na web, Ler página, Ler documento e Gerar arquivo. A OpenAI é simulada (as
respostas imitam o formato real da Responses API, conferido ao vivo); nada vai à rede."""

import httpx
import pytest

import instrumentos as encaixe
import openai
from instrumentos import escolha_ia
from instrumentos import gerar_arquivo as ga
from instrumentos import openai_servidor as oai
from instrumentos.base import FalhaInstrumento
from orquestracao.llm import usar_chaves


class _Obj:
    def __init__(self, dados: dict):
        self._dados = dados
        for k, v in dados.items():
            setattr(self, k, v)

    def model_dump(self):
        return dict(self._dados)


class _Resposta:
    def __init__(self, itens, texto="", status="completed", entrada=1000, saida=100, cache=0):
        self.output = [_Obj(i) for i in itens]
        self.output_text = texto
        self.status = status
        self.error = None
        self.incomplete_details = None
        self.usage = _Obj({
            "input_tokens": entrada, "output_tokens": saida,
            "input_tokens_details": {"cached_tokens": cache},
        })


def _mensagem(texto, anotacoes=()):
    return {"type": "message", "content": [
        {"type": "output_text", "text": texto, "annotations": list(anotacoes)},
    ]}


def _busca(acao="search", fontes=()):
    return {"type": "web_search_call", "status": "completed",
            "action": {"type": acao, "sources": list(fontes)}}


class _Cliente:
    """Cliente falso da OpenAI: devolve `respostas` em ordem e guarda os pedidos."""

    def __init__(self, respostas, arquivos_do_espaco=(), conteudos=None):
        self.pedidos: list[dict] = []
        self.enviados: list[tuple] = []
        self.apagados: list[str] = []
        fila = list(respostas)
        cliente = self

        class Respostas:
            def create(self, **kw):
                cliente.pedidos.append(kw)
                item = fila.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item

        class Arquivos:
            def create(self, file, purpose):
                cliente.enviados.append((file, purpose))
                return _Obj({"id": f"file-{len(cliente.enviados)}"})

            def delete(self, file_id):
                cliente.apagados.append(file_id)

        class Conteudo:
            def retrieve(self, file_id, container_id):
                return _Obj({"read": lambda: (conteudos or {}).get(file_id, b"PK-dados")})

        class ArquivosDoEspaco:
            content = Conteudo()

            def list(self, container_id):
                return [_Obj(f) for f in arquivos_do_espaco]

        class Espacos:
            files = ArquivosDoEspaco()

        self.responses = Respostas()
        self.files = Arquivos()
        self.containers = Espacos()


def _openai_falsa(monkeypatch, respostas, **kw) -> _Cliente:
    cli = _Cliente(respostas, **kw)
    monkeypatch.setattr(oai, "cliente", lambda timeout=None: cli)
    return cli


def _erro_api(classe, status, mensagem):
    resp = httpx.Response(status, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    return classe(mensagem, response=resp, body=None)


# ── Qual IA faz o trabalho ───────────────────────────────────────────────────────


def test_em_branco_usa_a_ia_que_tem_chave():
    padroes = {"anthropic": "claude-haiku-4-5", "openai": "gpt-5.6-luna"}
    with usar_chaves({"openai": "sk-x"}):
        assert escolha_ia.resolver("", padroes) == "gpt-5.6-luna"
    with usar_chaves({"anthropic": "a", "openai": "b"}):
        assert escolha_ia.resolver("", padroes) == "claude-haiku-4-5"
    with usar_chaves({"openai": "sk-x"}):
        assert escolha_ia.resolver("claude-sonnet-5", padroes) == "claude-sonnet-5"


def test_campo_antigo_provedor_vira_o_padrao_daquela_ia():
    tipo = encaixe.obter_tipo("pesquisar_web")
    assert tipo.Config(provedor="openai").modelo == "gpt-5.6-luna"
    assert tipo.Config(provedor="anthropic", modelo="claude-sonnet-5").modelo == "claude-sonnet-5"
    assert tipo.Config(provedor="anthropic").modelo == "claude-haiku-4-5"


def test_modelo_fora_da_lista_e_recusado():
    tipo = encaixe.obter_tipo("ler_documento")
    with pytest.raises(ValueError):
        tipo.Config(modelo="gpt-4o")  # não abre página nem lê como os da geração atual
    with pytest.raises(ValueError):
        tipo.Config(modelo="gemini-3.8-flash")


def test_seletor_mostra_so_as_ias_do_instrumento():
    esquema = encaixe.obter_tipo("gerar_arquivo").Config.model_json_schema()
    campo = esquema["properties"]["modelo"]
    assert campo["ui"] == "modelo_ia"
    assert campo["provedores"] == ["anthropic", "openai"]
    assert "gpt-5.6-luna" in campo["enum"] and "claude-sonnet-5" in campo["enum"]


def test_sem_chave_da_openai_explica_o_caminho():
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"anthropic": "a"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(modelo="gpt-5.6-luna"), tipo.Args(pergunta="selic hoje"))
    assert e.value.codigo == "ia.sem_chave"
    assert "Organização › Chaves" in str(e.value)


# ── Pesquisar na web ─────────────────────────────────────────────────────────────


def test_pesquisa_pela_openai_com_filtros_fontes_e_custo(monkeypatch):
    cli = _openai_falsa(monkeypatch, [_Resposta(
        [_busca(fontes=[{"type": "url", "url": "https://bcb.gov.br/b"}]),
         _mensagem("A Selic está em 13,75% ([bcb](https://bcb.gov.br/a?utm_source=openai)).", [
             {"type": "url_citation", "url": "https://bcb.gov.br/a?utm_source=openai",
              "title": "Copom"},
         ])],
        texto="A Selic está em 13,75% ([bcb](https://bcb.gov.br/a?utm_source=openai)).",
        entrada=8600, saida=100,
    )])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"openai": "sk-x"}):
        r = tipo.executar(
            tipo.Config(sites_preferidos=["bcb.gov.br"], max_buscas=3),
            tipo.Args(pergunta="qual a selic?"),
        )
    pedido = cli.pedidos[0]
    assert pedido["model"] == "gpt-5.6-luna"
    assert pedido["tools"][0]["filters"] == {"allowed_domains": ["bcb.gov.br"]}
    assert pedido["tools"][0]["user_location"]["country"] == "BR"
    assert pedido["max_tool_calls"] == 3
    assert "Hoje é" in pedido["instructions"]
    assert "utm_source" not in r["resposta"]
    assert r["fontes"] == [
        {"titulo": "Copom", "url": "https://bcb.gov.br/a"},
        {"titulo": "", "url": "https://bcb.gov.br/b"},
    ]
    assert r["uso"]["buscas"] == 1
    # 8.600 × US$ 0,20/M + 100 × US$ 1,20/M + 1 busca × US$ 0,01
    assert r["uso"]["custo_usd"] == pytest.approx(0.00172 + 0.00012 + 0.01)


def test_resposta_que_falhou_na_openai_vira_falha(monkeypatch):
    _openai_falsa(monkeypatch, [_Resposta([], status="failed")])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"openai": "sk-x"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(modelo="gpt-5.6-luna"), tipo.Args(pergunta="selic hoje"))
    assert e.value.codigo == "openai.falhou"


def test_chave_recusada_pela_openai(monkeypatch):
    _openai_falsa(monkeypatch, [_erro_api(openai.AuthenticationError, 401, "bad key")])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"openai": "sk-x"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(modelo="gpt-5.6-luna"), tipo.Args(pergunta="selic hoje"))
    assert e.value.codigo == "ia.chave_recusada"


def test_modelo_desligado_na_openai_da_o_recado_honesto(monkeypatch):
    _openai_falsa(monkeypatch, [_erro_api(
        openai.NotFoundError, 404, "The model `gpt-5.6-luna` does not exist (model_not_found)",
    )])
    tipo = encaixe.obter_tipo("pesquisar_web")
    with usar_chaves({"openai": "sk-x"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(modelo="gpt-5.6-luna"), tipo.Args(pergunta="selic hoje"))
    assert e.value.codigo == "ia.modelo_desligado"
    assert "A OpenAI" in str(e.value)


# ── Ler página ───────────────────────────────────────────────────────────────────


def test_ler_pagina_pela_openai_abre_o_endereco(monkeypatch):
    cli = _openai_falsa(monkeypatch, [_Resposta(
        [_busca("open_page"), _mensagem("A página trata da Selic.")],
        texto="A página trata da Selic.",
    )])
    tipo = encaixe.obter_tipo("ler_pagina")
    with usar_chaves({"openai": "sk-x"}):
        r = tipo.executar(tipo.Config(), tipo.Args(url="https://pt.wikipedia.org/wiki/Selic"))
    assert "https://pt.wikipedia.org/wiki/Selic" in cli.pedidos[0]["input"][0]["content"][0]["text"]
    assert r["conteudo"] == "A página trata da Selic."
    assert "aviso" not in r
    assert r["uso"]["leituras"] == 1 and r["uso"]["buscas"] == 0


def test_ler_pagina_avisa_quando_a_ia_nao_abriu_a_pagina(monkeypatch):
    _openai_falsa(monkeypatch, [_Resposta(
        [_busca("search"), _mensagem("Não consegui acessar a página.")],
        texto="Não consegui acessar a página.",
    )])
    tipo = encaixe.obter_tipo("ler_pagina")
    with usar_chaves({"openai": "sk-x"}):
        r = tipo.executar(tipo.Config(), tipo.Args(url="https://exemplo.com.br"))
    assert "não abriu" in r["aviso"]


# ── Ler documento ────────────────────────────────────────────────────────────────


def test_ler_documento_pela_openai_manda_o_link_do_pdf(monkeypatch):
    cli = _openai_falsa(monkeypatch, [_Resposta(
        [_mensagem("Total de R$ 1.200,00, vence em 10/10.")],
        texto="Total de R$ 1.200,00, vence em 10/10.",
    )])
    tipo = encaixe.obter_tipo("ler_documento")
    with usar_chaves({"openai": "sk-x"}):
        r = tipo.executar(tipo.Config(), tipo.Args(url="https://x.com/nota.pdf", pergunta="total?"))
    conteudo = cli.pedidos[0]["input"][0]["content"]
    assert cli.pedidos[0]["model"] == "gpt-5.6-terra"
    assert conteudo[0] == {"type": "input_file", "file_url": "https://x.com/nota.pdf"}
    assert r["resposta"].startswith("Total") and r["citacoes"] == []


# ── Gerar arquivo ────────────────────────────────────────────────────────────────


def _guardados(monkeypatch):
    salvos: list[tuple] = []

    def salvar(nome, conteudo, tipo):
        salvos.append((nome, conteudo, tipo))
        return f"https://armazem/{nome}"

    monkeypatch.setattr(ga.arquivos, "salvar", salvar)
    return salvos


def test_gerar_arquivo_pela_openai_sobe_entrada_gera_guarda_e_limpa(monkeypatch):
    texto = ("Planilha criada com o total e o gráfico: "
             "[Baixar vendas.xlsx](sandbox:/mnt/data/vendas.xlsx).")
    cli = _openai_falsa(monkeypatch, [_Resposta(
        [{"type": "code_interpreter_call", "container_id": "cntr_1", "status": "completed"},
         _mensagem(texto, [{"type": "container_file_citation", "container_id": "cntr_1",
                            "file_id": "cfile_9", "filename": "vendas.xlsx"}])],
        texto=texto, entrada=2000, saida=600,
    )])
    salvos = _guardados(monkeypatch)
    monkeypatch.setattr(ga.httpx, "get", lambda url, **k: httpx.Response(
        200, content=b"mes,valor\njul,100\n", headers={"content-type": "text/csv"},
        request=httpx.Request("GET", url)))
    tipo = encaixe.obter_tipo("gerar_arquivo")
    with usar_chaves({"openai": "sk-x"}):
        r = tipo.executar(
            tipo.Config(formatos=["xlsx"]),
            tipo.Args(instrucao="planilha com total", arquivos_url=["https://x.com/vendas.csv"]),
        )
    assert cli.enviados[0][0][0] == "vendas.csv" and cli.enviados[0][1] == "user_data"
    ferramenta = cli.pedidos[0]["tools"][0]
    assert ferramenta["type"] == "code_interpreter"
    assert ferramenta["container"]["file_ids"] == ["file-1"]
    assert "xlsx" in cli.pedidos[0]["instructions"] and "/mnt/data" in cli.pedidos[0]["instructions"]
    assert salvos[0][0].endswith("-vendas.xlsx")
    assert r["arquivos"][0]["nome"] == "vendas.xlsx"
    assert r["resumo"] == "Planilha criada com o total e o gráfico."
    assert cli.apagados == ["file-1"]  # a entrada não fica na OpenAI
    # 2.000 × US$ 0,20/M + 600 × US$ 1,20/M + 1 espaço de execução (US$ 0,03)
    assert r["uso"]["custo_usd"] == pytest.approx(0.0004 + 0.00072 + 0.03)


def test_gerar_arquivo_sem_citacao_pega_o_que_a_ia_criou_na_pasta(monkeypatch):
    _openai_falsa(monkeypatch, [_Resposta(
        [{"type": "code_interpreter_call", "container_id": "cntr_1", "status": "completed"},
         _mensagem("Relatório pronto.")],
        texto="Relatório pronto.",
    )], arquivos_do_espaco=[
        {"id": "cf_1", "path": "/mnt/data/relatorio.docx", "source": "assistant"},
        {"id": "cf_2", "path": "/mnt/data/render/page-1.png", "source": "assistant"},
        {"id": "cf_3", "path": "/mnt/data/cfile_abc.png", "source": "assistant"},
        {"id": "cf_4", "path": "/mnt/data/vendas.csv", "source": "user"},
    ])
    _guardados(monkeypatch)
    tipo = encaixe.obter_tipo("gerar_arquivo")
    with usar_chaves({"openai": "sk-x"}):
        r = tipo.executar(tipo.Config(), tipo.Args(instrucao="relatório em Word"))
    assert [a["nome"] for a in r["arquivos"]] == ["relatorio.docx"]


def test_gerar_arquivo_pela_openai_sem_arquivo_avisa(monkeypatch):
    _openai_falsa(monkeypatch, [_Resposta([_mensagem("A média é 110.")], texto="A média é 110.")])
    _guardados(monkeypatch)
    tipo = encaixe.obter_tipo("gerar_arquivo")
    with usar_chaves({"openai": "sk-x"}):
        r = tipo.executar(tipo.Config(), tipo.Args(instrucao="qual a média?"))
    assert r["arquivos"] == [] and "Nenhum arquivo" in r["aviso"]


def test_entrada_apagada_mesmo_quando_a_chamada_falha(monkeypatch):
    cli = _openai_falsa(monkeypatch, [_erro_api(openai.InternalServerError, 500, "boom")])
    monkeypatch.setattr(ga.httpx, "get", lambda url, **k: httpx.Response(
        200, content=b"a", request=httpx.Request("GET", url)))
    tipo = encaixe.obter_tipo("gerar_arquivo")
    with usar_chaves({"openai": "sk-x"}), pytest.raises(FalhaInstrumento) as e:
        tipo.executar(tipo.Config(), tipo.Args(instrucao="monte algo", arquivos_url=["https://x.com/a.csv"]))
    assert e.value.retentavel and cli.apagados == ["file-1"]
