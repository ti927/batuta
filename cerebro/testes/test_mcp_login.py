"""Testes da Fatia 0 do Batuta-MCP profissional: login OAuth real + tokens assinados.

Rodam OFFLINE (sem Postgres): a tabela de clientes usa SQLite em memória e o Supabase é
mockado. Cobrem a cripto dos tokens, o fluxo code→access→refresh carregando o `subject`,
a persistência do cliente (DCR) e a autenticação por senha.
"""

import asyncio
import os

import pytest
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# Segredo fixo para a assinatura ser determinística no teste.
os.environ["MCP_TOKEN_SECRET"] = "segredo-de-teste"

import mcp_login  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def engine_sqlite():
    """SQLite em memória compartilhado (StaticPool) com a tabela `mcp_cliente`."""
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    mcp_login.preparar(eng)
    return eng


@pytest.fixture
def cliente_oauth():
    return OAuthClientInformationFull(
        client_id="cliente-1",
        redirect_uris=[AnyUrl("https://claude.ai/api/mcp/auth_callback")],
    )


# ───────────────────────────── Cripto dos tokens ─────────────────────────────

def test_assinar_verificar_roundtrip():
    t = mcp_login._assinar("access", {"sub": "u1", "scopes": ["batuta"]}, 60)
    corpo = mcp_login._verificar("access", t)
    assert corpo is not None
    assert corpo["sub"] == "u1"
    assert corpo["scopes"] == ["batuta"]


def test_verificar_rejeita_violacao_especie_e_expiracao():
    t = mcp_login._assinar("access", {"sub": "u1"}, 60)
    # adulteração da assinatura
    assert mcp_login._verificar("access", t[:-2] + "xy") is None
    # espécie errada (um "access" não vale como "code")
    assert mcp_login._verificar("code", t) is None
    # expirado (ttl negativo → exp no passado)
    velho = mcp_login._assinar("access", {"sub": "u1"}, -1)
    assert mcp_login._verificar("access", velho) is None
    # lixo
    assert mcp_login._verificar("access", "sem-ponto") is None
    assert mcp_login._verificar("access", "") is None


def test_segredo_diferente_invalida():
    t = mcp_login._assinar("access", {"sub": "u1"}, 60)
    os.environ["MCP_TOKEN_SECRET"] = "outro-segredo"
    try:
        assert mcp_login._verificar("access", t) is None
    finally:
        os.environ["MCP_TOKEN_SECRET"] = "segredo-de-teste"


# ───────────────────────── Fluxo OAuth (code→access→refresh) ─────────────────────────

def test_authorize_manda_para_a_telinha(engine_sqlite, cliente_oauth):
    prov = mcp_login.ProvedorLoginBatuta(engine=engine_sqlite)
    params = AuthorizationParams(
        state="xyz",
        scopes=["batuta"],
        code_challenge="desafio123",
        redirect_uri=AnyUrl("https://claude.ai/api/mcp/auth_callback"),
        redirect_uri_provided_explicitly=True,
        resource="https://batuta/mcp",
    )
    url = _run(prov.authorize(cliente_oauth, params))
    assert "/login?req=" in url
    req = url.split("req=", 1)[1]
    pedido = mcp_login._verificar("req", req)
    assert pedido["client_id"] == "cliente-1"
    assert pedido["code_challenge"] == "desafio123"
    assert pedido["state"] == "xyz"
    assert pedido["redirect_uri"] == "https://claude.ai/api/mcp/auth_callback"


def test_code_para_access_carrega_subject(engine_sqlite, cliente_oauth):
    prov = mcp_login.ProvedorLoginBatuta(engine=engine_sqlite)
    # o /login emitiria este código depois de autenticar o consultor u-42
    codigo = mcp_login._assinar(
        "code",
        {
            "client_id": "cliente-1",
            "sub": "u-42",
            "scopes": ["batuta"],
            "code_challenge": "desafio123",
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "explicito": True,
            "resource": None,
        },
        120,
    )
    code_obj = _run(prov.load_authorization_code(cliente_oauth, codigo))
    assert code_obj is not None
    assert code_obj.subject == "u-42"
    assert code_obj.code_challenge == "desafio123"

    token = _run(prov.exchange_authorization_code(cliente_oauth, code_obj))
    acesso = _run(prov.load_access_token(token.access_token))
    assert acesso is not None
    assert acesso.subject == "u-42"

    # refresh rotaciona e mantém o subject
    refresh_obj = _run(prov.load_refresh_token(cliente_oauth, token.refresh_token))
    assert refresh_obj is not None and refresh_obj.subject == "u-42"
    novo = _run(prov.exchange_refresh_token(cliente_oauth, refresh_obj, ["batuta"]))
    acesso2 = _run(prov.load_access_token(novo.access_token))
    assert acesso2.subject == "u-42"


def test_code_de_outro_cliente_recusado(engine_sqlite, cliente_oauth):
    prov = mcp_login.ProvedorLoginBatuta(engine=engine_sqlite)
    codigo = mcp_login._assinar(
        "code",
        {
            "client_id": "OUTRO",
            "sub": "u-42",
            "scopes": ["batuta"],
            "code_challenge": "d",
            "redirect_uri": "https://claude.ai/cb",
            "explicito": True,
            "resource": None,
        },
        120,
    )
    assert _run(prov.load_authorization_code(cliente_oauth, codigo)) is None


# ───────────────────────── Registro dinâmico de cliente (DCR) ─────────────────────────

def test_cliente_persiste_e_recarrega(engine_sqlite, cliente_oauth):
    prov = mcp_login.ProvedorLoginBatuta(engine=engine_sqlite)
    assert _run(prov.get_client("cliente-1")) is None
    _run(prov.register_client(cliente_oauth))
    carregado = _run(prov.get_client("cliente-1"))
    assert carregado is not None
    assert carregado.client_id == "cliente-1"
    # re-registrar o mesmo id não quebra (upsert)
    _run(prov.register_client(cliente_oauth))
    assert _run(prov.get_client("cliente-1")).client_id == "cliente-1"


# ───────────────────────── Autenticação no Supabase (mock) ─────────────────────────

class _Resp:
    def __init__(self, status, corpo):
        self.status_code = status
        self._corpo = corpo

    def json(self):
        return self._corpo


def test_autenticar_supabase_ok(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-abc")
    monkeypatch.setattr(
        mcp_login.httpx, "post", lambda *a, **k: _Resp(200, {"access_token": "jwt"})
    )
    monkeypatch.setattr(mcp_login, "validar_token", lambda t: {"sub": "supa-sub-1"})
    assert mcp_login.autenticar_supabase("a@x.com", "senha") == "supa-sub-1"


def test_autenticar_supabase_senha_errada(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-abc")
    monkeypatch.setattr(
        mcp_login.httpx, "post", lambda *a, **k: _Resp(400, {"error": "invalid_grant"})
    )
    assert mcp_login.autenticar_supabase("a@x.com", "errada") is None


def test_autenticar_supabase_sem_anon_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    assert mcp_login.autenticar_supabase("a@x.com", "senha") is None


# ───────────────────────── Escopo (identidade + tradução de acesso) ─────────────────────────

def test_usuario_do_sub_sem_identidade():
    import mcp_escopo
    # sub ausente ou inválido levanta SemAcesso ANTES de tocar o banco (sessao=None)
    with pytest.raises(mcp_escopo.SemAcesso):
        mcp_escopo.usuario_do_sub(None, None)
    with pytest.raises(mcp_escopo.SemAcesso):
        mcp_escopo.usuario_do_sub(None, "nao-e-uuid")


def test_traduzir_acesso():
    from fastapi import HTTPException

    import mcp_ferramentas
    assert "encontr" in mcp_ferramentas._traduzir_acesso(HTTPException(404, "x")).lower()
    assert "permiss" in mcp_ferramentas._traduzir_acesso(
        HTTPException(403, "Esta ação exige o papel 'operador'.")
    ).lower()


def test_ferramenta_sem_identidade_nao_toca_o_banco():
    """O decorator `_ferramenta` barra quem não tem `sub` ANTES de qualquer query
    (a sessão abre mas nada é consultado) e devolve a mensagem de acesso, não exceção."""
    import mcp_ferramentas
    r = mcp_ferramentas.listar_agentes(None, "algum-time")
    assert isinstance(r, str) and "identifica" in r.lower()


def test_ferramenta_escrita_sem_identidade_barra_antes_do_banco():
    """O decorator de ESCRITA também barra sem `sub` antes de tocar o banco (rollback de
    sessão não usada, sem conexão) e devolve texto, não exceção."""
    import mcp_ferramentas_escrita as escrita
    r = escrita.criar_agente(None, "t", "Novo", "agente", None, None, None, None, None)
    assert isinstance(r, str) and "identifica" in r.lower()
    r2 = escrita.ativar_time(None, "alguma-automacao")
    assert isinstance(r2, str) and "identifica" in r2.lower()


def test_campos_parciais_ignora_none():
    import mcp_ferramentas_escrita as escrita
    assert escrita._campos(nome="x", papel=None, agent_md="y") == {"nome": "x", "agent_md": "y"}
    assert escrita._campos(nome=None) == {}


def test_credenciais_sem_identidade_barram_antes_do_banco():
    """As ferramentas de credencial (leitura e escrita) barram sem `sub` antes de tocar o
    banco e devolvem texto, não exceção."""
    import mcp_ferramentas
    import mcp_ferramentas_escrita as escrita
    assert "identifica" in mcp_ferramentas.listar_credenciais(None, "org").lower()
    assert "identifica" in mcp_ferramentas.ver_chaves_de_ia(None, "org").lower()
    assert "identifica" in escrita.criar_credencial(None, "org", "WP", "wordpress").lower()
    assert "identifica" in escrita.remover_credencial(None, "cred").lower()


def test_fatia3b_sem_identidade_barra_antes_do_banco():
    """As ferramentas da 3b (config, referência, exclusão, duplicação, org) barram sem
    `sub` antes de tocar o banco."""
    import mcp_ferramentas_escrita as escrita
    assert "identifica" in escrita.configurar_memoria_agente(None, "ag", True, "sempre").lower()
    assert "identifica" in escrita.apontar_credencial(None, "inst", "cred").lower()
    assert "identifica" in escrita.duplicar_time(None, "t", "Cópia").lower()
    assert "identifica" in escrita.excluir_time(None, "t").lower()
    assert "identifica" in escrita.excluir_automacao(None, "a").lower()
    assert "identifica" in escrita.excluir_instrumento(None, "i").lower()
    assert "identifica" in escrita.criar_organizacao(None, "Nova Org").lower()
