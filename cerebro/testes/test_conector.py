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

import pytest

import instrumentos as encaixe
from instrumentos.base import FalhaInstrumento
from instrumentos.conector import (
    ArgsConector,
    CampoOperacao,
    ConfigConector,
    Conector,
    OperacaoConector,
    _executar_operacao,
)
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

    monkeypatch.setattr("instrumentos.conector.http_saida.cliente", _Cliente)


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
    # O segredo da autenticação declarada + o material de mTLS/OAuth (opcional,
    # vindo do cofre): vazio nele NÃO conta como segredo pendente.
    assert t.campos_secretos == (
        "auth_segredo", "certificado", "chave_privada", "client_secret",
        "access_token",
    )
    assert t.campos_secretos_opcionais == (
        "certificado", "chave_privada", "client_secret", "access_token",
    )
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


def test_auth_basic_monta_o_cabecalho(monkeypatch):
    """Usuário e senha (Basic) — um dos 'em breve' que o Construtor tinha. O par
    vira o cabeçalho padrão; a senha é a metade secreta (vem do cofre)."""
    import base64

    capturas: list = []
    _mock_http(monkeypatch, _Resp(200, {"ok": True}), capturas)
    config = ConfigConector(
        auth_tipo="basic",
        auth_usuario="maria",
        auth_segredo="s3nha",
        operacoes=[{"nome": "buscar", "url": "https://api.x.com/s", "metodo": "GET"}],
    )
    Conector().expandir_ferramentas(config)[0].invoke({})
    esperado = base64.b64encode(b"maria:s3nha").decode()
    assert capturas[0]["headers"]["Authorization"] == f"Basic {esperado}"


def test_auth_oauth2_usa_o_token_que_a_borda_obteve(monkeypatch):
    """No OAuth 2.0 quem vai no cabeçalho é o TOKEN (que a borda troca pelo
    segredo e renova sozinha), nunca o Client Secret."""
    capturas: list = []
    _mock_http(monkeypatch, _Resp(200, {"ok": True}), capturas)
    config = ConfigConector(
        auth_tipo="oauth2",
        auth_usuario="cliente-123",
        auth_segredo="NAO-DEVE-VAZAR",
        url_token="https://api.x.com/oauth/token",
        access_token="tok-da-borda",
        operacoes=[{"nome": "buscar", "url": "https://api.x.com/s", "metodo": "GET"}],
    )
    Conector().expandir_ferramentas(config)[0].invoke({})
    assert capturas[0]["headers"]["Authorization"] == "Bearer tok-da-borda"
    assert "NAO-DEVE-VAZAR" not in json.dumps(capturas[0], default=str)


def test_auth_oauth2_sem_token_nao_quebra(monkeypatch):
    """Token ainda não obtido (ex.: credenciais erradas): a chamada sai sem
    Authorization e o serviço responde 401 com recado claro — não explode aqui."""
    capturas: list = []
    _mock_http(monkeypatch, _Resp(200, {"ok": True}), capturas)
    config = ConfigConector(
        auth_tipo="oauth2",
        auth_usuario="cliente-123",
        auth_segredo="seg",
        url_token="https://api.x.com/oauth/token",
        operacoes=[{"nome": "buscar", "url": "https://api.x.com/s", "metodo": "GET"}],
    )
    Conector().expandir_ferramentas(config)[0].invoke({})
    assert "Authorization" not in (capturas[0]["headers"] or {})


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


def test_metadados_nao_afetam_execucao():
    config = {
        "descricao": "publica fotos",
        "categoria": "Redes sociais",
        "operacoes": [{"nome": "a", "url": "https://x", "metodo": "GET"}],
    }
    assert encaixe.acao_irreversivel("conector", config) is False  # só olha operações
    publica, _ = encaixe.preparar_config("conector", config)
    assert publica["descricao"] == "publica fotos"
    assert publica["categoria"] == "Redes sociais"


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


# ─────────────────────────── testar e detectar (Construtor) ───────────────────────────


def test_testar_operacao_detecta_todos_os_campos(monkeypatch):
    """O 'testar e detectar' roda SEM o filtro campos_resposta — mostra a resposta
    inteira para o usuário escolher o que trazer."""
    _mock_http(
        monkeypatch,
        _Resp(200, {"results": [{"id": 1, "status": "ok", "extra": "z"}]}),
        [],
    )
    config = ConfigConector(
        operacoes=[
            {"nome": "listar", "url": "https://x/i", "metodo": "GET",
             "campos_resposta": ["id"]}  # filtro configurado é IGNORADO no teste
        ]
    )
    r = Conector().testar_operacao(config, "listar", {})
    assert r["ok"] is True
    assert [c["nome"] for c in r["campos_detectados"]] == ["id", "status", "extra"]
    tipos = {c["nome"]: c["tipo"] for c in r["campos_detectados"]}
    assert tipos == {"id": "número", "status": "texto", "extra": "texto"}


def test_detecta_uniao_de_campos_esparsos(monkeypatch):
    """Bubble OMITE campos vazios de cada registro — a detecção une os campos de
    TODOS os registros retornados (não só do primeiro), senão perderia campos."""
    _mock_http(
        monkeypatch,
        _Resp(200, {"response": {"results": [
            {"a": 1, "b": "x"},           # 1º registro: a, b
            {"a": 2, "c": True},          # 2º: a, c (b omitido por estar vazio)
            {"a": 3, "d": "y"},           # 3º: a, d
        ]}}),
        [],
    )
    config = ConfigConector(operacoes=[{"nome": "l", "url": "https://x", "metodo": "GET"}])
    r = Conector().testar_operacao(config, "l", {})
    assert [c["nome"] for c in r["campos_detectados"]] == ["a", "b", "c", "d"]


def test_testar_operacao_inexistente_levanta():
    config = ConfigConector(operacoes=[{"nome": "a", "url": "https://x", "metodo": "GET"}])
    with pytest.raises(FalhaInstrumento):
        Conector().testar_operacao(config, "nao-existe", {})


def test_testar_operacao_falha_externa_vira_dado(monkeypatch):
    _mock_http(monkeypatch, _Resp(500), [])
    config = ConfigConector(operacoes=[{"nome": "a", "url": "https://x", "metodo": "GET"}])
    r = Conector().testar_operacao(config, "a", {})
    assert r["ok"] is False and r["campos_detectados"] == []


def test_endpoint_testar_operacao_detecta(cliente, entrar, dados, monkeypatch):
    """Ponta a ponta: cria um conector (segredo ao cofre), testa uma operação —
    o segredo é decifrado e injetado, e os campos da resposta são detectados."""
    entrar(dados["admin"])
    criado = cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={
            "nome": "Meu conector",
            "tipo": "conector",
            "configuracao": {
                "auth_tipo": "bearer",
                "auth_segredo": "tok-abc",
                "operacoes": [
                    {"nome": "listar", "url": "https://api.x.com/itens", "metodo": "GET"}
                ],
            },
        },
    )
    assert criado.status_code == 201
    assert "auth_segredo" not in (criado.json()["configuracao"] or {})  # segredo ao cofre
    inst_id = criado.json()["id"]

    capturas: list = []
    _mock_http(monkeypatch, _Resp(200, {"results": [{"id": 1, "nome": "A", "lixo": "x"}]}), capturas)
    r = cliente.post(
        f"/instrumentos/{inst_id}/testar-operacao",
        json={"operacao": "listar", "valores": {}},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["ok"] is True
    assert [c["nome"] for c in corpo["campos_detectados"]] == ["id", "nome", "lixo"]
    assert capturas[0]["headers"]["Authorization"] == "Bearer tok-abc"  # segredo do cofre injetado


def test_endpoint_testar_operacao_so_conector(cliente, entrar, dados):
    """Um instrumento que não é conector recusa o teste de operação (422)."""
    entrar(dados["admin"])
    criado = cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={"nome": "Busca", "tipo": "busca_web", "configuracao": {}},
    )
    inst_id = criado.json()["id"]
    r = cliente.post(
        f"/instrumentos/{inst_id}/testar-operacao",
        json={"operacao": "x", "valores": {}},
    )
    assert r.status_code == 422


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


# ───────────── endereço com buraco não preenchido (2026-08-26) ─────────────
# Caso real: a operação "Altera Reembolso" apontava para `/obj/Tbl/[id]` com o campo
# `id` marcado como destino "query". O `[id]` nunca era substituído, a chamada saía
# com o colchete literal no endereço e o serviço respondia 404 — o agente então
# inventava uma explicação. Falhar aqui, dizendo QUAL campo, é honesto.


def _op_com_buraco(destino: str) -> OperacaoConector:
    return OperacaoConector(
        nome="Altera Reembolso", metodo="PATCH",
        url="https://api.exemplo/obj/Tbl.Reembolsos/[id]",
        campos=[CampoOperacao(nome="id", papel="ia", destino=destino, obrigatorio=True)],
    )


def test_placeholder_sem_campo_de_url_falha_claro(monkeypatch):
    capturas: list = []
    _mock_http(monkeypatch, _Resp(200, {}), capturas)
    with pytest.raises(FalhaInstrumento) as e:
        _executar_operacao(ConfigConector(), _op_com_buraco("query"), {"id": "123"})
    assert "«id»" in str(e.value)
    assert "destino" in str(e.value).lower()
    assert not capturas, "não pode chamar o serviço com o endereço quebrado"


def test_placeholder_com_destino_url_funciona(monkeypatch):
    """O contraste: com o destino certo, o endereço é montado e a chamada sai."""
    capturas: list = []
    _mock_http(monkeypatch, _Resp(200, {"ok": True}), capturas)
    _executar_operacao(ConfigConector(), _op_com_buraco("url"), {"id": "123"})
    assert capturas[0]["url"] == "https://api.exemplo/obj/Tbl.Reembolsos/123"
