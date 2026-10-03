"""O instrumento MCP contra um servidor MCP DE VERDADE (local): cada modo de
identificação, os dois transportes, os erros sem segredo e o estado da conexão.

Pedido do maestro (2026-09-29): o MCP só aceitava endereço + token Bearer, e servidores
reais — o WordPress da Lure com senha de aplicativo, APIs com `X-API-Key` — ficavam de
fora. Ver `instrumentos/mcp_conexao.py` e `testes/mcp_servidor_falso.py`.
"""

import json
import uuid

import pytest

import instrumentos.mcp as mcp_mod
from instrumentos import mcp_conexao
from instrumentos.base import FalhaInstrumento
from instrumentos.mcp import ArgsMCP, ConectarMCP, ConfigMCP
from mcp_servidor_falso import (
    CHAVE_OK,
    CHAVE_URL,
    SENHA_OK,
    TOKEN_OK,
    USUARIO_OK,
    ServidoresFalsos,
)
from segredos_instrumento import pendentes


@pytest.fixture(scope="module")
def srv():
    s = ServidoresFalsos()
    yield s
    s.parar()


@pytest.fixture(autouse=True)
def _cache_limpo():
    mcp_mod._CACHE.clear()
    yield
    mcp_mod._CACHE.clear()


def _modos_certos(s: ServidoresFalsos) -> dict[str, ConfigMCP]:
    return {
        "nenhuma": ConfigMCP(url=s.url_http("/aberto"), auth_modo="nenhuma"),
        "url_secreta": ConfigMCP(url=s.url_http(f"/s/{CHAVE_URL}"), auth_modo="url_secreta"),
        "bearer": ConfigMCP(url=s.url_http(), auth_modo="bearer", token_bearer=TOKEN_OK),
        "cabecalho": ConfigMCP(
            url=s.url_http(), auth_modo="cabecalho", auth_nome="X-API-Key",
            auth_segredo=CHAVE_OK,
        ),
        "query": ConfigMCP(
            url=s.url_http(), auth_modo="query", auth_nome="api_key", auth_segredo=CHAVE_OK,
        ),
        "basic": ConfigMCP(
            url=s.url_http(), auth_modo="basic", auth_usuario=USUARIO_OK,
            auth_segredo=SENHA_OK,
        ),
    }


def _so_ler(c: ConfigMCP, **mudar) -> ConfigMCP:
    """A mesma configuração com só a ferramenta `ler` no cinto (validada de novo)."""
    return ConfigMCP.model_validate({
        **c.model_dump(), **mudar,
        "ferramentas": [{"nome": "ler", "usar": True, "irreversivel": False}],
    })


# ───────────────────────────── cada modo, de verdade ─────────────────────────────

@pytest.mark.parametrize(
    "modo", ["nenhuma", "url_secreta", "bearer", "cabecalho", "query", "basic"]
)
def test_cada_modo_conecta_e_lista(srv, modo):
    r = ConectarMCP().executar(_modos_certos(srv)[modo], ArgsMCP())
    assert r["ok"] is True
    assert r["transporte"] == "streamable_http"
    assert r["protocolo"]  # a versão negociada no initialize
    assert r["servidor"]["nome"] == "falso-http"
    sugestoes = {f["nome"]: f["sugestao"] for f in r["ferramentas"]}
    assert sugestoes == {"ler": "so_le", "apagar": "altera", "neutra": None}
    # sugestão NÃO é escolha: sem nada marcado, tudo segue pedindo aprovação
    assert all(f["pede_aprovacao"] is True for f in r["ferramentas"])
    assert [x["uri"] for x in r["recursos"]] == ["doc://manual"]
    assert [x["nome"] for x in r["prompts"]] == ["saudacao"]
    assert r["conexao"]["estado"] == "conectado"


@pytest.mark.parametrize(
    "modo", ["nenhuma", "url_secreta", "bearer", "cabecalho", "query", "basic"]
)
def test_cada_modo_chama_a_ferramenta_no_cinto(srv, modo):
    """A prova do lado do agente: a ferramenta escolhida roda com a identificação."""
    c = _so_ler(_modos_certos(srv)[modo])
    [ferramenta] = ConectarMCP().expandir_ferramentas(c)
    saida = ferramenta.invoke({"texto": "x"})
    assert "lido x" in str(saida)


@pytest.mark.parametrize(
    "modo,estrago",
    [
        ("bearer", {"token_bearer": "ERRADO"}),
        ("cabecalho", {"auth_segredo": "ERRADO"}),
        ("query", {"auth_segredo": "ERRADO"}),
        ("basic", {"auth_segredo": "ERRADO"}),
    ],
)
def test_identificacao_errada_da_401_claro_e_sem_segredo(srv, modo, estrago):
    c = _modos_certos(srv)[modo].model_copy(update=estrago)
    with pytest.raises(FalhaInstrumento) as e:
        ConectarMCP().executar(c, ArgsMCP())
    assert e.value.codigo == "mcp.auth_401"
    assert e.value.retentavel is False
    texto = str(e.value)
    assert "ERRADO" not in texto and "127.0.0.1" not in texto  # nem segredo nem URL


def test_chave_errada_no_endereco_nao_vaza_o_endereco(srv):
    """No Zapier/Make a URL É a chave. O erro da biblioteca trazia a URL inteira."""
    c = ConfigMCP(url=srv.url_http("/s/CHAVE-SECRETA-ERRADA"), auth_modo="url_secreta")
    with pytest.raises(FalhaInstrumento) as e:
        ConectarMCP().executar(c, ArgsMCP())
    assert "CHAVE-SECRETA-ERRADA" not in str(e.value)
    assert e.value.codigo == "mcp.auth_401"


def test_basic_manda_o_cabecalho_certo():
    d = mcp_conexao.montar_destino(
        ConfigMCP(url="https://x/mcp", auth_modo="basic", auth_usuario="u", auth_segredo="p")
    )
    assert d.cabecalhos["Authorization"] == "Basic dTpw"


def test_query_acrescenta_sem_perder_parametros():
    d = mcp_conexao.montar_destino(
        ConfigMCP(url="https://x/mcp?a=1", auth_modo="query", auth_nome="k", auth_segredo="v")
    )
    assert d.url == "https://x/mcp?a=1&k=v"


# ───────────────────────────── cabeçalhos extras ─────────────────────────────

def test_cabecalhos_extras_publicos_e_protegidos(srv):
    base = dict(url=srv.url_http("/extra"), auth_modo="bearer", token_bearer=TOKEN_OK)
    with pytest.raises(FalhaInstrumento) as e:
        ConectarMCP().executar(ConfigMCP(**base), ArgsMCP())
    assert e.value.codigo == "mcp.auth_403"
    # público
    ok = ConectarMCP().executar(ConfigMCP(**base, cabecalhos={"X-Tenant": "acme"}), ArgsMCP())
    assert ok["ok"]
    # protegido (vai no cofre como JSON)
    ok = ConectarMCP().executar(
        ConfigMCP(**base, cabecalhos_secretos=json.dumps({"X-Tenant": "acme"})), ArgsMCP()
    )
    assert ok["ok"]


def test_cabecalho_protegido_invalido_diz_o_que_fazer():
    with pytest.raises(FalhaInstrumento) as e:
        mcp_conexao.montar_destino(ConfigMCP(url="https://x", cabecalhos_secretos="lixo"))
    assert e.value.codigo == "mcp.config_invalida"


# ───────────────────────────── transporte ─────────────────────────────

def test_automatico_cai_para_sse_no_servidor_antigo(srv):
    c = ConfigMCP(url=srv.url_sse(), auth_modo="bearer", token_bearer=TOKEN_OK)
    assert c.transport == "automatico"
    r = ConectarMCP().executar(c, ArgsMCP())
    assert r["transporte"] == "sse"
    assert r["servidor"]["nome"] == "falso-sse"
    assert r["conexao"]["transporte"] == "sse"


@pytest.mark.parametrize("modo", ["bearer", "basic", "cabecalho"])
def test_sse_explicito_em_cada_modo_que_viaja_no_cabecalho(srv, modo):
    c = _so_ler(_modos_certos(srv)[modo], url=srv.url_sse(), transport="sse")
    assert ConectarMCP().executar(c, ArgsMCP())["transporte"] == "sse"
    [ferramenta] = ConectarMCP().expandir_ferramentas(c)
    assert "lido y" in str(ferramenta.invoke({"texto": "y"}))


def test_sse_com_identificacao_errada_acusa_401_e_nao_transporte(srv):
    c = ConfigMCP(url=srv.url_sse(), auth_modo="bearer", token_bearer="ERRADO")
    with pytest.raises(FalhaInstrumento) as e:
        ConectarMCP().executar(c, ArgsMCP())
    assert e.value.codigo == "mcp.auth_401"


def test_cinto_usa_o_transporte_ja_descoberto(srv, monkeypatch):
    """No automático, o cinto não gasta uma tentativa perdida por passo: usa o que o
    último "Conectar" guardou no estado da conexão do instrumento."""
    tentados = []
    original = mcp_conexao.com_transporte

    async def espiao(transporte, tentar):
        tentados.append(transporte)
        return await original(transporte, tentar)

    monkeypatch.setattr(mcp_conexao, "com_transporte", espiao)
    c = ConfigMCP(url=srv.url_sse(), auth_modo="bearer", token_bearer=TOKEN_OK)
    inst = type("I", (), {"conexao": {"transporte": "sse"}})()
    ConectarMCP().expandir_ferramentas_da_instancia(inst, c)
    assert tentados == ["sse"]


def test_instrumento_antigo_mantem_o_transporte_gravado():
    """Os existentes guardaram "streamable_http" — continuam exatamente iguais."""
    assert ConfigMCP.model_validate({"transport": "streamable_http"}).transport == "streamable_http"
    assert ConfigMCP().transport == "automatico"


# ───────────────────────────── erros de rede ─────────────────────────────

def test_servidor_fora_do_ar(srv):
    c = ConfigMCP(url="http://127.0.0.1:1/mcp", auth_modo="nenhuma")
    with pytest.raises(FalhaInstrumento) as e:
        ConectarMCP().executar(c, ArgsMCP())
    assert e.value.codigo == "mcp.fora_do_ar" and e.value.retentavel is True


def test_endereco_inexistente(srv):
    c = ConfigMCP(
        url=f"http://127.0.0.1:{srv.porta_http}/aberto/nada", auth_modo="nenhuma",
        transport="streamable_http",
    )
    with pytest.raises(FalhaInstrumento) as e:
        ConectarMCP().executar(c, ArgsMCP())
    assert e.value.codigo == "mcp.endereco_404"


def test_faltou_pedaco_do_modo_nem_chama_o_servidor():
    for config, falta in [
        (ConfigMCP(url="https://x", auth_modo="basic", auth_segredo="p"), "usuário"),
        (ConfigMCP(url="https://x", auth_modo="basic", auth_usuario="u"), "senha"),
        (ConfigMCP(url="https://x", auth_modo="cabecalho", auth_segredo="v"), "nome do cabeçalho"),
        (ConfigMCP(url="https://x", auth_modo="bearer"), "token"),
    ]:
        with pytest.raises(FalhaInstrumento) as e:
            mcp_conexao.montar_destino(config)
        assert falta in str(e.value) and e.value.codigo == "mcp.segredo_faltando"


# ───────────────────────────── retrocompatibilidade e pendências ─────────────────

def test_instrumento_antigo_sem_modo():
    assert mcp_conexao.modo_efetivo(ConfigMCP(url="x", token_bearer="t")) == "bearer"
    assert mcp_conexao.modo_efetivo(ConfigMCP(url="x")) == "nenhuma"


@pytest.mark.parametrize(
    "config,faltam",
    [
        ({}, ["url"]),  # antigo, sem modo: só o endereço, como sempre
        ({"token_bearer": ""}, ["url"]),
        ({"auth_modo": "nenhuma"}, ["url"]),
        ({"auth_modo": "url_secreta"}, ["url"]),
        ({"auth_modo": "bearer"}, ["url", "token_bearer"]),
        ({"auth_modo": "basic", "auth_usuario": "u"}, ["url", "auth_segredo"]),
        ({"auth_modo": "cabecalho"}, ["url", "auth_segredo"]),
        ({"auth_modo": "query"}, ["url", "auth_segredo"]),
    ],
)
def test_segredos_pendentes_dependem_do_modo(config, faltam):
    assert pendentes("conectar_mcp", guardados=set(), configuracao=config) == faltam


# ───────────────────────────── estado da conexão guardado ─────────────────────────

def _instrumento_mcp(sessao, dados, config: dict, segredos_: dict):
    import instrumentos as encaixe
    import segredos_instrumento as segredos
    from modelos import Instrumento

    publica, secretos = encaixe.preparar_config("conectar_mcp", {**config, **segredos_})
    inst = Instrumento(time_id=dados["timeA"].id, nome="MCP teste", tipo="conectar_mcp",
                       configuracao=publica)
    sessao.add(inst)
    sessao.flush()
    segredos.salvar_segredos(sessao, inst.id, secretos)
    sessao.flush()
    return inst


def test_acionar_guarda_o_estado_da_conexao(srv, cliente, entrar, dados, sessao):
    inst = _instrumento_mcp(
        sessao, dados, {"auth_modo": "basic", "auth_usuario": USUARIO_OK},
        {"url": srv.url_sse(), "auth_segredo": SENHA_OK},
    )
    entrar(dados["operador"])
    r = cliente.post(f"/instrumentos/{inst.id}/acionar", json={"argumentos": {}})
    assert r.status_code == 200, r.text
    assert SENHA_OK not in r.text and str(srv.porta_sse) not in r.text
    sessao.refresh(inst)
    assert inst.conexao["estado"] == "conectado"
    assert inst.conexao["transporte"] == "sse"
    assert inst.conexao["protocolo"]
    lido = cliente.get(f"/instrumentos/{inst.id}").json()
    assert lido["conexao"]["transporte"] == "sse"
    assert "auth_segredo" in lido["segredos"]  # guardado, só os 4 últimos


def test_acionar_guarda_a_falha_com_codigo(srv, cliente, entrar, dados, sessao):
    inst = _instrumento_mcp(
        sessao, dados, {"auth_modo": "bearer"},
        {"url": srv.url_http(), "token_bearer": "ERRADO"},
    )
    entrar(dados["operador"])
    r = cliente.post(f"/instrumentos/{inst.id}/acionar", json={"argumentos": {}})
    assert r.status_code == 502
    assert "401" in r.json()["detail"] and "ERRADO" not in r.text
    sessao.refresh(inst)
    assert inst.conexao["estado"] == "falhou"
    assert inst.conexao["codigo"] == "mcp.auth_401"


# ───────────────────────────── diagnóstico ─────────────────────────────

def test_diagnostico_acusa_o_agente_que_rodou_sem_o_instrumento():
    from types import SimpleNamespace

    import diagnostico_execucao as diag

    iid = str(uuid.uuid4())
    passo = SimpleNamespace(ordem=2, saida={"erros_instrumentos": [{
        "ferramenta": None, "tipo": "conectar_mcp", "instrumento_id": iid,
        "instrumento": "WordPress da Lure", "erro": "o servidor MCP recusou (401).",
        "retentavel": None, "irreversivel": None, "origem": "cinto",
        "codigo": "mcp.auth_401",
    }]})
    avisos: list[dict] = []
    diag._verificar_erros_instrumentos(None, [passo], avisos)
    [a] = avisos
    assert a["codigo"] == "instrumento_fora_do_cinto"
    assert "WordPress da Lure" in a["titulo"]
    assert "Como o Batuta se conecta" in a["detalhe"] and "mcp.auth_401" in a["detalhe"]
    assert a["referencias"]["instrumento_id"] == iid
