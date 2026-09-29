"""OAuth do instrumento MCP (Fase 2, 2026-09-29) contra um servidor OAuth DE VERDADE e
local (`mcp_oauth_falso.py`): descoberta, registro do cliente (dinâmico e CIMD), login
com PKCE, troca do código, renovação (com o refresh token que gira), renovação
SIMULTÂNEA com trava por instrumento, falha que marca "precisa reconectar" e OAuth
entre sistemas (client credentials).
"""

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

import instrumentos as encaixe
import instrumentos.mcp as mcp_mod
import segredos_instrumento as segredos
from instrumentos import mcp_conexao, mcp_oauth
from instrumentos.base import FalhaInstrumento
from instrumentos.mcp import ArgsMCP, ConectarMCP, ConfigMCP
from mcp_oauth_falso import CLIENTE_MAQUINA, ServidorOAuthFalso
from modelos import Instrumento, Organizacao, Time, Usuario
from sessao import CriadorDeSessao


@pytest.fixture(scope="module")
def oauth():
    s = ServidorOAuthFalso()
    yield s
    s.parar()


@pytest.fixture(autouse=True)
def _cache_limpo():
    mcp_mod._CACHE.clear()
    yield
    mcp_mod._CACHE.clear()


# ───────────────────────────── descoberta e início ─────────────────────────────

def test_descobre_pelo_401_do_servidor_mcp(oauth):
    d = mcp_oauth.descobrir(oauth.url_mcp)
    assert d.url_token == f"{oauth.base}/token"
    assert d.url_autorizacao == f"{oauth.base}/authorize"
    assert d.recurso == oauth.url_mcp
    assert d.escopo == "mcp"  # o `scope` do WWW-Authenticate vence


def test_servidor_sem_oauth_diz_o_que_fazer(oauth):
    from mcp_servidor_falso import ServidoresFalsos

    s = ServidoresFalsos()
    try:
        with pytest.raises(FalhaInstrumento) as e:
            mcp_oauth.descobrir(s.url_http("/aberto"))
        assert e.value.codigo == "mcp.oauth_sem_descoberta"
    finally:
        s.parar()


def _inst_fake():
    return type("I", (), {"id": uuid.uuid4()})()


def test_inicio_com_registro_dinamico_e_pkce(oauth, monkeypatch):
    monkeypatch.setenv("CEREBRO_PUBLIC_URL", "http://localhost:8000")  # sem HTTPS: sem CIMD
    url, dados, novos = mcp_oauth.iniciar_login(
        _inst_fake(), ConfigMCP(url=oauth.url_mcp, auth_modo="oauth_login"), {}, uuid.uuid4()
    )
    p = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert p["client_id"] == "cli-dcr" and dados["registro"] == "dcr"
    assert p["code_challenge_method"] == "S256" and len(p["code_challenge"]) >= 43
    assert p["resource"] == oauth.url_mcp and p["scope"] == "mcp"
    assert p["redirect_uri"] == "http://localhost:8000/mcp/oauth/callback"
    assert "code_verifier" not in url  # o verificador fica cifrado no instrumento
    # CURTO: o WordPress recusou o state de ~340 caracteres ("Invalid or expired state").
    assert len(p["state"]) < 80
    assert dados["pendente"]["verificador"] and dados["pendente"]["codigo"]
    assert novos == {}


def test_inicio_com_cimd_quando_o_servidor_aceita(monkeypatch):
    s = ServidorOAuthFalso(aceita_cimd=True)
    try:
        monkeypatch.setenv("CEREBRO_PUBLIC_URL", "https://api.batuta.team")
        antes = s.contagem["registro"]
        url, dados, _ = mcp_oauth.iniciar_login(
            _inst_fake(), ConfigMCP(url=s.url_mcp, auth_modo="oauth_login"), {}, uuid.uuid4()
        )
        p = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        assert p["client_id"] == "https://api.batuta.team/mcp/oauth/cliente.json"
        assert dados["registro"] == "cimd" and s.contagem["registro"] == antes
    finally:
        s.parar()


def test_client_id_manual_vence(oauth):
    url, dados, _ = mcp_oauth.iniciar_login(
        _inst_fake(),
        ConfigMCP(url=oauth.url_mcp, auth_modo="oauth_login", oauth_client_id="meu-app"),
        {}, uuid.uuid4(),
    )
    assert "client_id=meu-app" in url and dados["registro"] == "manual"


def test_documento_do_cliente_cimd(cliente, monkeypatch):
    monkeypatch.setenv("CEREBRO_PUBLIC_URL", "https://api.batuta.team")
    doc = cliente.get("/mcp/oauth/cliente.json").json()
    assert doc["client_id"] == "https://api.batuta.team/mcp/oauth/cliente.json"
    assert doc["redirect_uris"] == ["https://api.batuta.team/mcp/oauth/callback"]
    assert doc["token_endpoint_auth_method"] == "none"


# ───────────────────────────── o login inteiro, pelas rotas ─────────────────────

def _criar_inst(sessao, time_id, config: dict, secretos: dict) -> Instrumento:
    publica, s = encaixe.preparar_config("conectar_mcp", {**config, **secretos})
    inst = Instrumento(time_id=time_id, nome="MCP OAuth", tipo="conectar_mcp", configuracao=publica)
    sessao.add(inst)
    sessao.flush()
    segredos.salvar_segredos(sessao, inst.id, s)
    sessao.flush()
    return inst


def test_login_completo_pela_tela(oauth, cliente, entrar, dados, sessao):
    inst = _criar_inst(sessao, dados["timeA"].id, {"auth_modo": "oauth_login"}, {"url": oauth.url_mcp})
    entrar(dados["operador"])
    r = cliente.post(f"/instrumentos/{inst.id}/mcp/oauth/iniciar")
    assert r.status_code == 200, r.text
    # O navegador vai ao servidor de login, que aprova e devolve o código.
    volta = httpx.get(r.json()["url"], follow_redirects=False).headers["location"]
    q = {k: v[0] for k, v in parse_qs(urlparse(volta).query).items()}
    pagina = cliente.get("/mcp/oauth/callback", params={"code": q["code"], "state": q["state"]})
    assert pagina.status_code == 200 and "Conta conectada" in pagina.text
    assert '"ok": true' in pagina.text and "postMessage" in pagina.text
    sessao.refresh(inst)
    assert inst.conexao["oauth"]["estado"] == "conectado"
    cofre_inst = segredos.decifrar(sessao, inst.id)
    assert cofre_inst[mcp_oauth.CAMPO_ACCESS].startswith("AT-")
    assert cofre_inst[mcp_oauth.CAMPO_REFRESH].startswith("RT-")
    # E o instrumento conversa com o servidor protegido, sem ninguém colar token.
    lista = cliente.post(f"/instrumentos/{inst.id}/acionar", json={"argumentos": {}})
    assert lista.status_code == 200, lista.text
    assert {f["nome"] for f in lista.json()["ferramentas"]} == {"ler", "apagar", "neutra"}
    sessao.refresh(inst)
    assert inst.conexao["oauth"]["estado"] == "conectado"  # o teste não apagou o OAuth
    assert inst.conexao["estado"] == "conectado"


def test_volta_com_state_invalido_ou_login_recusado(oauth, cliente, entrar, dados, sessao):
    r = cliente.get("/mcp/oauth/callback", params={"code": "x", "state": "lixo"})
    assert "expirou" in r.text and '"ok": false' in r.text
    inst = _criar_inst(sessao, dados["timeA"].id, {"auth_modo": "oauth_login"}, {"url": oauth.url_mcp})
    entrar(dados["operador"])
    url = cliente.post(f"/instrumentos/{inst.id}/mcp/oauth/iniciar").json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    r = cliente.get("/mcp/oauth/callback", params={"error": "access_denied", "state": state})
    assert "não foi concluído" in r.text and "access_denied" in r.text


def test_observador_nao_inicia_login(oauth, cliente, entrar, dados, sessao):
    inst = _criar_inst(sessao, dados["timeA"].id, {"auth_modo": "oauth_login"}, {"url": oauth.url_mcp})
    entrar(dados["observador"])
    assert cliente.post(f"/instrumentos/{inst.id}/mcp/oauth/iniciar").status_code == 403


def test_sem_conectar_o_instrumento_diz_o_que_fazer():
    with pytest.raises(FalhaInstrumento) as e:
        mcp_conexao.montar_destino(ConfigMCP(url="https://x", auth_modo="oauth_login"))
    assert e.value.codigo == "mcp.precisa_conectar" and "Conectar" in str(e.value)


# ───────────────────────── renovação (dados COMITADOS: a trava é no banco) ─────────

@pytest.fixture
def comitado():
    """Organização, time e instrumento GRAVADOS de verdade — a renovação roda numa
    sessão própria com advisory lock e precisa enxergá-los. Apaga tudo ao fim."""
    s = CriadorDeSessao()
    u = Usuario(nome="oauth", email=f"oauth-{uuid.uuid4().hex[:6]}@x.com", auth_id=uuid.uuid4(), ativo=True)
    s.add(u)
    s.flush()
    org = Organizacao(nome="Org OAuth", dono_id=u.id)
    s.add(org)
    s.flush()
    t = Time(organizacao_id=org.id, nome="Time OAuth")
    s.add(t)
    s.flush()
    criados: list = []

    def criar(config: dict, secretos: dict, conexao: dict | None = None) -> uuid.UUID:
        inst = _criar_inst(s, t.id, config, secretos)
        inst.conexao = conexao
        s.commit()
        criados.append(inst.id)
        return inst.id

    yield criar
    s.rollback()
    for iid in criados:
        obj = s.get(Instrumento, iid)
        if obj is not None:
            s.delete(obj)
    s.flush()
    s.delete(s.get(Time, t.id))
    s.delete(s.get(Organizacao, org.id))
    s.delete(s.get(Usuario, u.id))
    s.commit()
    s.close()


def _conectado(oauth_srv: ServidorOAuthFalso, *, vencido: bool) -> tuple[dict, dict]:
    """Um login já feito (tokens reais do servidor falso), vencido ou não."""
    dados = oauth_srv._emitir(com_refresh=True)
    expira = datetime.now(timezone.utc) + (timedelta(minutes=-1) if vencido else timedelta(hours=1))
    conexao = {"oauth": {
        "url_token": f"{oauth_srv.base}/token", "client_id": "cli-dcr", "recurso": oauth_srv.url_mcp,
        "escopo": "mcp", "metodo": "none", "registro": "dcr", "estado": "conectado",
        "expira_em": expira.isoformat(),
    }}
    return conexao, {mcp_oauth.CAMPO_ACCESS: dados["access_token"], mcp_oauth.CAMPO_REFRESH: dados["refresh_token"]}


def _config_do_banco(iid) -> tuple[ConfigMCP, dict]:
    s = CriadorDeSessao()
    try:
        inst = s.get(Instrumento, iid)
        return ConfigMCP.model_validate({**inst.configuracao, **segredos.decifrar(s, iid)}), dict(inst.conexao or {})
    finally:
        s.close()


def test_renova_o_token_vencido_e_guarda_o_novo(oauth, comitado):
    conexao, secretos = _conectado(oauth, vencido=True)
    iid = comitado({"auth_modo": "oauth_login"}, {"url": oauth.url_mcp, **secretos}, conexao)
    config, cx = _config_do_banco(iid)
    antes = oauth.contagem["refresh"]
    novo = mcp_oauth.garantir_token(iid, "oauth_login", config, conexao=cx)
    assert novo.startswith("AT-") and novo != secretos[mcp_oauth.CAMPO_ACCESS]
    assert oauth.contagem["refresh"] == antes + 1
    config2, cx2 = _config_do_banco(iid)
    assert config2.oauth_access_token == novo
    assert config2.oauth_refresh_token != secretos[mcp_oauth.CAMPO_REFRESH]  # girou
    assert mcp_oauth._valido(cx2["oauth"], novo)


def test_duas_execucoes_ao_mesmo_tempo_renovam_uma_vez_so(comitado):
    """A trava por instrumento: sem ela, cinco renovações simultâneas usariam o MESMO
    refresh token — e, num servidor que gira o refresh, só a primeira funcionaria; as
    outras derrubariam a conexão."""
    srv = ServidorOAuthFalso(atraso_token_s=0.4)
    try:
        conexao, secretos = _conectado(srv, vencido=True)
        iid = comitado({"auth_modo": "oauth_login"}, {"url": srv.url_mcp, **secretos}, conexao)
        config, cx = _config_do_banco(iid)
        resultados: list[str] = []

        def rodar():
            resultados.append(mcp_oauth.garantir_token(iid, "oauth_login", config, conexao=cx))

        fios = [threading.Thread(target=rodar) for _ in range(5)]
        for f in fios:
            f.start()
        for f in fios:
            f.join(30)
        assert srv.contagem["refresh"] == 1
        assert len(set(resultados)) == 1 and resultados[0].startswith("AT-")
        _, cx2 = _config_do_banco(iid)
        assert cx2["oauth"]["estado"] == "conectado"
    finally:
        srv.parar()


def test_refresh_recusado_marca_precisa_reconectar(comitado, monkeypatch):
    srv = ServidorOAuthFalso()
    eventos = []
    monkeypatch.setattr(mcp_oauth, "_avisar", lambda iid, nome, e, nivel: eventos.append((e.codigo, nivel)))
    try:
        conexao, secretos = _conectado(srv, vencido=True)
        iid = comitado({"auth_modo": "oauth_login"}, {"url": srv.url_mcp, **secretos}, conexao)
        srv.revogar_tudo()  # a conta foi desconectada lá no servidor
        config, cx = _config_do_banco(iid)
        assert mcp_oauth.garantir_token(iid, "oauth_login", config, conexao=cx) == ""
        _, cx2 = _config_do_banco(iid)
        assert cx2["oauth"]["estado"] == "precisa_reconectar"
        assert eventos == [("mcp.oauth_recusado", "error")]
    finally:
        srv.parar()


def test_token_valido_nem_abre_sessao(oauth):
    """Caminho curto: token que ainda vale volta direto — sem banco, sem trava."""
    conexao, secretos = _conectado(oauth, vencido=False)
    config = ConfigMCP(url=oauth.url_mcp, auth_modo="oauth_login", **secretos)

    def proibido():
        raise AssertionError("não devia abrir sessão")

    assert mcp_oauth.garantir_token(uuid.uuid4(), "oauth_login", config, conexao=conexao,
                                    criar_sessao=proibido) == secretos[mcp_oauth.CAMPO_ACCESS]


# ───────────────────────────── OAuth entre sistemas ─────────────────────────────

def test_client_credentials_busca_o_token_e_conecta(oauth, comitado):
    iid = comitado(
        {"auth_modo": "oauth_cliente", "oauth_client_id": CLIENTE_MAQUINA[0]},
        {"url": oauth.url_mcp, "auth_segredo": CLIENTE_MAQUINA[1]},
    )
    config, cx = _config_do_banco(iid)
    token = mcp_oauth.garantir_token(iid, "oauth_cliente", config, conexao=cx)
    assert token.startswith("AT-")
    config2, cx2 = _config_do_banco(iid)
    assert cx2["oauth"]["url_token"] == f"{oauth.base}/token"  # descoberto sozinho
    r = ConectarMCP().executar(config2, ArgsMCP())
    assert r["ok"] and r["servidor"]["nome"] == "falso-oauth"


def test_client_credentials_errado_diz_o_que_conferir(oauth, comitado):
    iid = comitado(
        {"auth_modo": "oauth_cliente", "oauth_client_id": "maquina"},
        {"url": oauth.url_mcp, "auth_segredo": "errado"},
    )
    config, cx = _config_do_banco(iid)
    assert mcp_oauth.garantir_token(iid, "oauth_cliente", config, conexao=cx) == ""
    with pytest.raises(FalhaInstrumento) as e:
        mcp_conexao.montar_destino(config)
    assert e.value.codigo == "mcp.oauth_recusado"


def test_segredos_pendentes_nos_modos_oauth():
    from segredos_instrumento import pendentes

    assert pendentes("conectar_mcp", guardados=set(), configuracao={"auth_modo": "oauth_login"}) == ["url"]
    assert pendentes("conectar_mcp", guardados=set(), configuracao={"auth_modo": "oauth_cliente"}) == ["url", "auth_segredo"]


def test_diagnostico_manda_conectar_de_novo():
    from types import SimpleNamespace

    import diagnostico_execucao as diag

    passo = SimpleNamespace(ordem=1, saida={"erros_instrumentos": [{
        "tipo": "conectar_mcp", "instrumento_id": str(uuid.uuid4()), "instrumento": "WP",
        "erro": "não conectado", "origem": "cinto", "codigo": "mcp.precisa_conectar",
    }]})
    avisos: list = []
    diag._verificar_erros_instrumentos(None, [passo], avisos)
    assert "Conectar" in avisos[0]["detalhe"]


def test_state_de_uso_unico_e_com_prazo(oauth, cliente, entrar, dados, sessao):
    inst = _criar_inst(sessao, dados["timeA"].id, {"auth_modo": "oauth_login"}, {"url": oauth.url_mcp})
    entrar(dados["operador"])
    url = cliente.post(f"/instrumentos/{inst.id}/mcp/oauth/iniciar").json()["url"]
    volta = httpx.get(url, follow_redirects=False).headers["location"]
    q = {k: v[0] for k, v in parse_qs(urlparse(volta).query).items()}
    primeira = cliente.get("/mcp/oauth/callback", params={"code": q["code"], "state": q["state"]})
    assert "Conta conectada" in primeira.text
    # A mesma volta de novo (ex.: alguém reenviando o endereço) é recusada.
    repetida = cliente.get("/mcp/oauth/callback", params={"code": q["code"], "state": q["state"]})
    assert "expirou" in repetida.text and '"ok": false' in repetida.text
    # Um login pedido há mais de 10 minutos também.
    url = cliente.post(f"/instrumentos/{inst.id}/mcp/oauth/iniciar").json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    sessao.refresh(inst)
    conexao = dict(inst.conexao)
    conexao["oauth"] = {**conexao["oauth"], "pendente": {
        **conexao["oauth"]["pendente"],
        "criado_em": (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat(),
    }}
    inst.conexao = conexao
    sessao.flush()
    velha = cliente.get("/mcp/oauth/callback", params={"code": "x", "state": state})
    assert "expirou" in velha.text


def test_volta_do_login_grava_o_estado_com_commit_de_verdade(oauth):
    """REGRESSÃO do teste ao vivo (29/09): com a sessão de verdade (o commit EXPIRA o
    objeto), a volta do login reatribuía o mesmo dict e o SQLAlchemy não gravava o
    estado "conectado" — só os tokens. A sessão dos outros testes não expira no commit,
    por isso eles não pegaram."""
    from modelos import Membro
    from rotas import mcp_oauth as rota

    s = CriadorDeSessao()
    u = Usuario(nome="oauth", email=f"oauth-{uuid.uuid4().hex[:6]}@x.com", auth_id=uuid.uuid4(), ativo=True)
    s.add(u)
    s.flush()
    org = Organizacao(nome="Org OAuth", dono_id=u.id)
    s.add(org)
    s.flush()
    s.add(Membro(usuario_id=u.id, organizacao_id=org.id, papel="admin"))
    t = Time(organizacao_id=org.id, nome="Time OAuth")
    s.add(t)
    s.flush()
    inst = _criar_inst(s, t.id, {"auth_modo": "oauth_login"}, {"url": oauth.url_mcp})
    config = ConfigMCP.model_validate({**inst.configuracao, "url": oauth.url_mcp})
    url, dados_oauth, _ = mcp_oauth.iniciar_login(inst, config, {}, u.id)
    inst.conexao = {"oauth": dados_oauth}
    s.commit()
    iid = inst.id
    try:
        volta = httpx.get(url, follow_redirects=False).headers["location"]
        q = {k: v[0] for k, v in parse_qs(urlparse(volta).query).items()}
        s2 = CriadorDeSessao()
        try:
            pagina = rota.callback(state=q["state"], code=q["code"], sessao=s2)
            assert "Conta conectada" in pagina.body.decode()
        finally:
            s2.close()
        s3 = CriadorDeSessao()
        try:
            gravado = s3.get(Instrumento, iid).conexao["oauth"]
        finally:
            s3.close()
        assert gravado["estado"] == "conectado"
        assert gravado.get("conectado_em") and gravado.get("expira_em")
        assert "pendente" not in gravado
    finally:
        s.rollback()
        s.delete(s.get(Instrumento, iid))
        s.flush()
        s.execute(Membro.__table__.delete().where(Membro.organizacao_id == org.id))
        s.delete(s.get(Time, t.id))
        s.delete(s.get(Organizacao, org.id))
        s.delete(s.get(Usuario, u.id))
        s.commit()
        s.close()
