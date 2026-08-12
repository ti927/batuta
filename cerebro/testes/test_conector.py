"""Testes do instrumento CONECTOR (Framework de Instrumentos, Fase 1 — o motor).

Sem rede real: o `httpx.Client` é interceptado e captura a requisição montada.
Provam o ponto central — UM conector se expande em VÁRIAS ferramentas (uma por
operação declarada) —, a montagem correta da requisição (URL com [colchete],
autenticação, query/corpo por destino), o corte de custo herdado do REST, a
robustez a nomes de campo não-identificadores (ex.: 'cpo.NomeCliente'), o cofre
(o segredo de auth é separado) e a irreversibilidade conservadora por instrumento.
"""

import json
import uuid

import instrumentos as encaixe
from instrumentos.conector import ArgsConector, ConfigConector, Conector
from modelos import Instrumento
from orquestracao.agente import _ferramentas_de_instrumento


# ─────────────────────────── dublê de httpx ───────────────────────────


class _Resp:
    def __init__(self, status=200, dados=None, texto=""):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._dados = dados
        self.text = texto

    def json(self):
        if self._dados is None:
            raise ValueError("sem json")
        return self._dados


def _mock_http(monkeypatch, resp, capturas):
    class _Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def request(self, metodo, url, headers=None, params=None, json=None):
            capturas.append(
                {"metodo": metodo, "url": url, "headers": headers, "params": params, "json": json}
            )
            return resp

    monkeypatch.setattr("instrumentos.conector.httpx.Client", _Cliente)


def _instrumento(configuracao: dict) -> Instrumento:
    inst = Instrumento(
        id=uuid.uuid4(), time_id=uuid.uuid4(), nome="i", tipo="conector",
        configuracao=configuracao,
    )
    inst.segredos_decifrados = {}
    return inst


# ─────────────────────────── registro / esquema ───────────────────────────


def test_conector_registrado():
    t = encaixe.obter_tipo("conector")
    assert t is not None
    assert t.campos_secretos == ("auth_segredo",)
    assert "conector" in [x.tipo for x in encaixe.tipos_disponiveis()]


def test_expande_uma_ferramenta_por_operacao():
    config = ConfigConector(
        operacoes=[
            {"nome": "Listar posts", "url": "https://api.x.com/posts", "metodo": "GET"},
            {"nome": "Publicar", "url": "https://api.x.com/posts", "metodo": "POST"},
        ]
    )
    tools = Conector().expandir_ferramentas(config)
    assert [t.name for t in tools] == ["Listar_posts", "Publicar"]


def test_executar_isolado_descreve_operacoes():
    config = ConfigConector(
        operacoes=[{"nome": "Listar", "url": "https://api.x.com", "metodo": "GET"}]
    )
    r = Conector().executar(config, ArgsConector())
    assert r["ok"] is True
    assert [o["nome"] for o in r["operacoes"]] == ["Listar"]


# ─────────────────────────── seam no cinto ───────────────────────────


def test_seam_conector_expande_no_cinto():
    """O encaixe transforma 1 conector em N ferramentas (como o MCP)."""
    inst = _instrumento(
        {
            "operacoes": [
                {"nome": "a", "url": "https://x", "metodo": "GET"},
                {"nome": "b", "url": "https://x", "metodo": "GET"},
            ]
        }
    )
    tools = _ferramentas_de_instrumento(inst, [], {}, [])
    assert [t.name for t in tools] == ["a", "b"]


# ─────────────────────────── montagem da requisição ───────────────────────────


def test_montagem_url_auth_query_corpo_e_filtro(monkeypatch):
    capturas: list = []
    _mock_http(
        monkeypatch,
        _Resp(200, {"results": [{"id": 1, "status": "ok", "lixo": "descartar"}]}),
        capturas,
    )
    config = ConfigConector(
        auth_tipo="bearer",
        auth_segredo="tok123",
        operacoes=[
            {
                "nome": "criar",
                "url": "https://api.x.com/orgs/[org]/posts",
                "metodo": "POST",
                "campos_resposta": ["id", "status"],
                "campos": [
                    {"nome": "org", "papel": "ia", "destino": "url"},
                    {"nome": "texto", "papel": "ia", "destino": "corpo"},
                    {"nome": "fonte", "papel": "fixo", "valor": "batuta", "destino": "corpo"},
                    {"nome": "rascunho", "papel": "ia", "destino": "query", "obrigatorio": False},
                ],
            }
        ],
    )
    tool = Conector().expandir_ferramentas(config)[0]
    saida = json.loads(tool.invoke({"org": "acme", "texto": "olá mundo"}))

    req = capturas[0]
    assert req["metodo"] == "POST"
    assert req["url"] == "https://api.x.com/orgs/acme/posts"  # [org] substituído
    assert req["headers"]["Authorization"] == "Bearer tok123"  # auth bearer
    assert req["json"] == {"texto": "olá mundo", "fonte": "batuta"}  # ia + fixo no corpo
    assert req["params"] is None  # 'rascunho' opcional não informado → nada na query
    # corte de custo herdado do REST: só id/status por registro (lixo removido)
    assert saida["corpo"]["results"] == [{"id": 1, "status": "ok"}]


def test_auth_em_cabecalho_e_query(monkeypatch):
    capturas: list = []
    _mock_http(monkeypatch, _Resp(200, {"ok": True}), capturas)
    config = ConfigConector(
        auth_tipo="query",
        auth_nome="api_key",
        auth_segredo="K9",
        operacoes=[{"nome": "buscar", "url": "https://api.x.com/s", "metodo": "GET"}],
    )
    Conector().expandir_ferramentas(config)[0].invoke({})
    assert capturas[0]["params"] == {"api_key": "K9"}


def test_campo_nome_nao_identificador(monkeypatch):
    """Campo 'cpo.NomeCliente' vira um arg de nome seguro, mas cai no corpo sob o
    nome REAL — o motor nunca quebra por um nome de campo com ponto/hífen."""
    capturas: list = []
    _mock_http(monkeypatch, _Resp(200, {"ok": True}), capturas)
    config = ConfigConector(
        operacoes=[
            {
                "nome": "gravar",
                "url": "https://api.x.com/obj",
                "metodo": "POST",
                "campos": [{"nome": "cpo.NomeCliente", "papel": "ia", "destino": "corpo"}],
            }
        ]
    )
    tool = Conector().expandir_ferramentas(config)[0]
    campos = tool.args_schema.model_json_schema()["properties"]
    assert "cpo_NomeCliente" in campos  # arg seguro para a IA
    tool.invoke({"cpo_NomeCliente": "Fulano"})
    assert capturas[0]["json"] == {"cpo.NomeCliente": "Fulano"}  # nome real na rede


# ─────────────────────────── cofre / parede ───────────────────────────


def test_cofre_separa_auth_segredo():
    publica, segredos = encaixe.preparar_config(
        "conector",
        {
            "auth_tipo": "bearer",
            "auth_segredo": "meu-token",
            "operacoes": [{"nome": "x", "url": "https://x", "metodo": "GET"}],
        },
    )
    assert "auth_segredo" not in publica  # segredo fora da config pública
    assert segredos == {"auth_segredo": "meu-token"}
    assert publica["operacoes"][0]["nome"] == "x"  # operações preservadas


def test_irreversivel_conservador_por_instrumento():
    so_leitura = {"operacoes": [{"nome": "l", "url": "https://x", "metodo": "GET"}]}
    com_escrita = {
        "operacoes": [
            {"nome": "l", "url": "https://x", "metodo": "GET"},
            {"nome": "p", "url": "https://x", "metodo": "POST"},
        ]
    }
    assert encaixe.acao_irreversivel("conector", so_leitura) is False
    assert encaixe.acao_irreversivel("conector", com_escrita) is True


def test_conector_oculto_no_catalogo_mas_executavel(cliente, entrar, dados):
    """O conector NÃO aparece no dropdown de criar instrumento da tela atual
    (espera o Construtor da Fase 2), mas o tipo é real e o motor o executa."""
    entrar(dados["admin"])
    r = cliente.get("/instrumentos/tipos")
    assert r.status_code == 200
    tipos = [t["tipo"] for t in r.json()]
    assert "conector" not in tipos  # invisível na tela atual
    assert "chamar_api_rest" in tipos  # os demais tipos seguem visíveis
    assert encaixe.obter_tipo("conector") is not None  # mas é real no motor


def test_falha_de_http_vira_erro_para_ia(monkeypatch):
    """5xx vira FalhaInstrumento, capturada e devolvida como erro honesto à IA
    (não finge sucesso)."""
    capturas: list = []
    _mock_http(monkeypatch, _Resp(500), capturas)
    config = ConfigConector(
        operacoes=[{"nome": "buscar", "url": "https://api.x.com/s", "metodo": "GET"}]
    )
    saida = json.loads(Conector().expandir_ferramentas(config)[0].invoke({}))
    assert saida["ok"] is False
    assert "falhou" in saida["erro"]
