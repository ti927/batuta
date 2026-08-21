"""Login OAuth 2.1 REAL do Batuta-MCP (Fatia 0 do "Batuta-MCP profissional").

Substitui o login auto-aprovado da prova descartável (já aposentada). O claude.ai exige
OAuth no connector; aqui o `authorize`
**NÃO auto-aprova** — ele manda o navegador do consultor para uma telinha de login do
Batuta (e-mail/senha), autentica no **Supabase** (o mesmo Auth do app), resolve o
`Usuario` do banco e só então emite o código de autorização **amarrado à identidade
dele** (`subject = Usuario.id`).

Duas decisões de desenho, para um serviço standalone que NÃO roda `alembic`:

1. **Tokens SEM estado no servidor.** Código de autorização, access token e refresh
   token são strings **ASSINADAS** (HMAC-SHA256 com `MCP_TOKEN_SECRET`) que carregam o
   próprio conteúdo. Sobrevivem a restart/réplica (basta o mesmo segredo) e dispensam
   tabela de tokens. A **revogação é ao vivo**, a cada chamada de ferramenta: o
   `subject` é re-resolvido no banco e o acesso é re-checado por `Membro` — mesma
   filosofia do `auth.py` (desativar o usuário ou tirá-lo da org corta o acesso na
   hora, mesmo com um token ainda dentro da validade).

2. **Clientes OAuth numa tabela PORTÁVEL** (`mcp_cliente`). O registro dinâmico (DCR)
   que o claude.ai faz PRECISA sobreviver a deploy (senão o consultor re-loga a cada
   subida). É uma tabela mínima (Core, tipos portáveis Postgres/SQLite) criada no boot
   com `create_all(checkfirst=True)` — mesma ideia das tabelas de checkpoint do
   LangGraph, que também vivem fora do alembic.

As engrenagens do OAuth (rotas `/authorize`, `/token`, `/register`, metadados
`.well-known`) vêm prontas do SDK `mcp`; este arquivo implementa a lógica do provedor
e a telinha de login.
"""

import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import time
import uuid

import anyio
import httpx
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from sqlalchemy import Column, Float, MetaData, String, Table, Text, select
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

import mcp_escopo
from auth_supabase import TokenInvalido, validar_token
from sessao import CriadorDeSessao

# ───────────────────────────── Configuração ─────────────────────────────

ESCOPO = "batuta"
TTL_REQ = 600          # validade do "pedido de login" carregado até a telinha (s)
TTL_CODIGO = 120       # validade do authorization code (s) — curto, uso quase imediato
TTL_ACCESS = 3600 * 12    # validade do access token (s)
TTL_REFRESH = 3600 * 24 * 30  # validade do refresh token (s)

# URL pública (raiz) DESTE serviço — precisa bater com o domínio real, senão a
# descoberta do OAuth e o redirecionamento da telinha não fecham. Ordem:
# MCP_PUBLIC_URL (override) → RAILWAY_PUBLIC_DOMAIN (injetado pelo Railway) → localhost.
_railway = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
BASE_URL = (
    os.environ.get("MCP_PUBLIC_URL")
    or (f"https://{_railway}" if _railway else "http://localhost:8000")
).rstrip("/")
CAMINHO_MCP = "/mcp"

# Segredo de assinatura dos tokens. Em produção DEVE vir de `MCP_TOKEN_SECRET`
# (senão os tokens não sobrevivem a restart e cada réplica assina diferente). Sem ele,
# usamos um fallback aleatório por processo — bom só para dev/teste.
_FALLBACK_SEGREDO = secrets.token_hex(32)
if not os.environ.get("MCP_TOKEN_SECRET"):
    # Aviso único no stdout (o serviço loga em JSON via logging, mas isto é boot).
    print(
        "[mcp_login] AVISO: MCP_TOKEN_SECRET não definido — usando segredo efêmero "
        "(tokens não sobrevivem a restart). Defina a variável em produção."
    )


def _chave() -> bytes:
    return (os.environ.get("MCP_TOKEN_SECRET") or _FALLBACK_SEGREDO).encode()


# ───────────────────────── Tabela portável de clientes ─────────────────────────

_META = MetaData()
mcp_cliente = Table(
    "mcp_cliente",
    _META,
    Column("client_id", String(255), primary_key=True),
    Column("dados", Text, nullable=False),   # JSON de OAuthClientInformationFull
    Column("criado_em", Float, nullable=False),
)


def preparar(engine=None) -> None:
    """Cria a tabela `mcp_cliente` se ainda não existir (idempotente). Chamado no boot
    do serviço MCP. À prova de falha: se o banco não responder, deixa estourar no boot
    (o serviço não tem o que fazer sem banco)."""
    from db import engine as engine_padrao

    _META.create_all(bind=engine or engine_padrao, checkfirst=True)


# ───────────────────────── Assinatura de tokens (stateless) ─────────────────────────

def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


def _unb64(txt: str) -> bytes:
    return base64.urlsafe_b64decode(txt + "=" * (-len(txt) % 4))


def _assinar(especie: str, dados: dict, ttl: int) -> str:
    """Empacota `dados` + espécie + expiração e assina com HMAC-SHA256."""
    corpo = {**dados, "k": especie, "exp": time.time() + ttl}
    parte = _b64(json.dumps(corpo, separators=(",", ":")).encode())
    assinatura = _b64(hmac.new(_chave(), parte.encode(), hashlib.sha256).digest())
    return f"{parte}.{assinatura}"


def _verificar(especie: str, token: str) -> dict | None:
    """Confere assinatura, espécie e validade. Devolve o corpo ou None."""
    if not token or "." not in token:
        return None
    parte, assinatura = token.split(".", 1)
    esperada = _b64(hmac.new(_chave(), parte.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(assinatura, esperada):
        return None
    try:
        corpo = json.loads(_unb64(parte))
    except (ValueError, json.JSONDecodeError):
        return None
    if corpo.get("k") != especie:
        return None
    if float(corpo.get("exp", 0)) < time.time():
        return None
    return corpo


# ───────────────────────── Autenticação no Supabase ─────────────────────────

def _anon_key() -> str | None:
    for chave in (
        "SUPABASE_ANON_KEY",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
    ):
        valor = os.environ.get(chave)
        if valor:
            return valor
    return None


def autenticar_supabase(email: str, senha: str) -> str | None:
    """Valida e-mail+senha no Supabase (grant_type=password). Devolve o `sub` (id do
    usuário no Supabase) se conferem; None se não. Bloqueante — chame numa thread."""
    if not email or not senha:
        return None
    url = os.environ["SUPABASE_URL"].rstrip("/")
    anon = _anon_key()
    if not anon:
        print("[mcp_login] AVISO: sem anon key (SUPABASE_ANON_KEY) — login por senha indisponível.")
        return None
    try:
        r = httpx.post(
            f"{url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": anon, "Content-Type": "application/json"},
            json={"email": email, "password": senha},
            timeout=20,
        )
    except httpx.HTTPError:
        return None
    if r.status_code >= 300:
        return None
    token = r.json().get("access_token")
    try:
        return validar_token(token).get("sub")
    except TokenInvalido:
        return None


def _resolver_usuario_ativo(sub: str) -> str | None:
    """sub do Supabase → id do `Usuario` Batuta ATIVO (str), ou None se não há cadastro
    (ninguém se autoinscreve) ou está desativado. Bloqueante — chame numa thread."""
    try:
        auth_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        return None
    sessao = CriadorDeSessao()
    try:
        usuario = mcp_escopo.usuario_por_auth_id(sessao, auth_id)
        if usuario is None or not usuario.ativo:
            return None
        return str(usuario.id)
    finally:
        sessao.close()


# ───────────────────────── Telinha de login (HTML) ─────────────────────────

def _pagina_login(req: str, email: str = "", erro: str = "") -> str:
    """HTML mínimo e com a marca do Batuta. `req` é o pedido de login assinado (carrega
    o contexto OAuth através do formulário). Sem dependências externas."""
    erro_html = (
        f'<p class="erro" role="alert">{html.escape(erro)}</p>' if erro else ""
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entrar no Batuta</title>
<style>
  :root {{ --roxo:#6D4AFF; --roxo-hover:#5A3FE0; --escuro:#1A1730; --fundo:#FAFAF7;
           --secundario:#6B6880; --erro:#E5484D; --erro-bg:#FDECEC; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
          background:var(--fundo); color:var(--escuro);
          font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; padding:24px; }}
  .cartao {{ background:#fff; width:100%; max-width:380px; border-radius:16px; padding:32px;
             box-shadow:0 8px 30px rgba(26,23,48,.08); }}
  .marca {{ font-weight:800; font-size:24px; letter-spacing:-.02em; }}
  .marca span {{ color:var(--roxo); }}
  .sub {{ color:var(--secundario); font-size:14px; margin:6px 0 22px; }}
  label {{ display:block; font-size:13px; font-weight:600; margin:14px 0 6px; }}
  input {{ width:100%; padding:11px 12px; border:1px solid #E4E2EC; border-radius:10px;
           font-size:15px; color:var(--escuro); }}
  input:focus {{ outline:2px solid var(--roxo); border-color:var(--roxo); }}
  button {{ width:100%; margin-top:22px; padding:12px; border:0; border-radius:10px;
            background:var(--roxo); color:#fff; font-size:15px; font-weight:700; cursor:pointer; }}
  button:hover {{ background:var(--roxo-hover); }}
  .erro {{ background:var(--erro-bg); color:var(--erro); font-size:13px; padding:10px 12px;
           border-radius:10px; margin:0 0 4px; }}
  .rodape {{ color:var(--secundario); font-size:12px; margin-top:18px; text-align:center; }}
</style>
</head>
<body>
  <form class="cartao" method="post" action="/login">
    <div class="marca">Bat<span>u</span>ta</div>
    <p class="sub">Entre com sua conta para conectar o Claude ao Batuta.</p>
    {erro_html}
    <input type="hidden" name="req" value="{html.escape(req)}">
    <label for="email">E-mail</label>
    <input id="email" name="email" type="email" autocomplete="username"
           value="{html.escape(email)}" required autofocus>
    <label for="senha">Senha</label>
    <input id="senha" name="senha" type="password" autocomplete="current-password" required>
    <button type="submit">Entrar</button>
    <p class="rodape">Suas credenciais vão só para o Batuta. O Claude nunca as vê.</p>
  </form>
</body>
</html>"""


# ───────────────────────────── O provedor OAuth ─────────────────────────────

class ProvedorLoginBatuta(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """Servidor de autorização OAuth com **login real** (Supabase) + escopo por
    consultor. Clientes na tabela `mcp_cliente`; tokens assinados (sem estado)."""

    def __init__(self, engine=None) -> None:
        self._engine = engine  # None → usa o engine padrão (db.engine)

    def _conexao(self):
        from db import engine as engine_padrao

        return (self._engine or engine_padrao).begin()

    # ── cliente (registro dinâmico, persistido) ──
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with self._conexao() as conn:
            linha = conn.execute(
                select(mcp_cliente.c.dados).where(mcp_cliente.c.client_id == client_id)
            ).first()
        if not linha:
            return None
        return OAuthClientInformationFull.model_validate_json(linha[0])

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        with self._conexao() as conn:
            valores = {
                "client_id": client_info.client_id,
                "dados": client_info.model_dump_json(),
                "criado_em": time.time(),
            }
            dialeto = conn.dialect.name
            if dialeto == "postgresql":
                stmt = pg_insert(mcp_cliente).values(**valores)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[mcp_cliente.c.client_id],
                    set_={"dados": stmt.excluded.dados},
                )
                conn.execute(stmt)
            else:  # sqlite (testes) e afins: apaga-e-insere
                conn.execute(
                    mcp_cliente.delete().where(
                        mcp_cliente.c.client_id == client_info.client_id
                    )
                )
                conn.execute(mcp_cliente.insert().values(**valores))

    # ── authorize: NÃO auto-aprova; manda para a telinha de login ──
    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        req = _assinar(
            "req",
            {
                "client_id": client.client_id,
                "redirect_uri": str(params.redirect_uri),
                "explicito": params.redirect_uri_provided_explicitly,
                "code_challenge": params.code_challenge,
                "scopes": params.scopes or [ESCOPO],
                "resource": params.resource,
                "state": params.state,
            },
            TTL_REQ,
        )
        return f"{BASE_URL}/login?req={req}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        d = _verificar("code", authorization_code)
        if not d or d.get("client_id") != client.client_id:
            return None
        return AuthorizationCode(
            code=authorization_code,
            scopes=d["scopes"],
            expires_at=d["exp"],
            client_id=d["client_id"],
            code_challenge=d["code_challenge"],
            redirect_uri=AnyUrl(d["redirect_uri"]),
            redirect_uri_provided_explicitly=d["explicito"],
            resource=d.get("resource"),
            subject=d.get("sub"),
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        escopos = authorization_code.scopes
        base = {
            "client_id": client.client_id,
            "sub": authorization_code.subject,
            "scopes": escopos,
        }
        acesso = _assinar("access", {**base, "resource": authorization_code.resource}, TTL_ACCESS)
        renov = _assinar("refresh", base, TTL_REFRESH)
        return OAuthToken(
            access_token=acesso,
            token_type="Bearer",
            expires_in=TTL_ACCESS,
            scope=" ".join(escopos) or None,
            refresh_token=renov,
        )

    # ── verificação do access token (usada pelo middleware que protege o MCP) ──
    async def load_access_token(self, token: str) -> AccessToken | None:
        d = _verificar("access", token)
        if not d:
            return None
        return AccessToken(
            token=token,
            client_id=d["client_id"],
            scopes=d["scopes"],
            expires_at=int(d["exp"]),
            resource=d.get("resource"),
            subject=d.get("sub"),
        )

    # ── refresh (rotaciona ambos os tokens) ──
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        d = _verificar("refresh", refresh_token)
        if not d or d.get("client_id") != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=d["client_id"],
            scopes=d["scopes"],
            subject=d.get("sub"),
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        escopos = scopes or refresh_token.scopes
        base = {"client_id": client.client_id, "sub": refresh_token.subject, "scopes": escopos}
        acesso = _assinar("access", base, TTL_ACCESS)
        novo_refresh = _assinar("refresh", base, TTL_REFRESH)
        return OAuthToken(
            access_token=acesso,
            token_type="Bearer",
            expires_in=TTL_ACCESS,
            scope=" ".join(escopos) or None,
            refresh_token=novo_refresh,
        )

    async def revoke_token(self, token) -> None:
        # Tokens são sem estado (assinados) — não há o que apagar. A revogação efetiva é
        # ao vivo, por chamada: o `subject` é re-resolvido e o acesso re-checado no banco.
        return None


# ───────────────────────── Rotas da telinha de login ─────────────────────────

def registrar_rotas_login(mcp) -> None:
    """Registra GET/POST `/login` no app do FastMCP (rotas públicas, parte do fluxo de
    auth). Chamado por `mcp_servidor` depois de construir o `FastMCP`."""

    @mcp.custom_route("/login", methods=["GET"])
    async def login_form(request: Request) -> HTMLResponse:  # pragma: no cover
        req = request.query_params.get("req", "")
        if not _verificar("req", req):
            return HTMLResponse(
                _pagina_login("", erro="Sessão de login expirada. Feche e conecte de novo."),
                status_code=400,
            )
        return HTMLResponse(_pagina_login(req))

    @mcp.custom_route("/login", methods=["POST"])
    async def login_submit(request: Request):  # pragma: no cover
        form = await request.form()
        req = (form.get("req") or "").strip()
        email = (form.get("email") or "").strip()
        senha = form.get("senha") or ""

        pedido = _verificar("req", req)
        if not pedido:
            return HTMLResponse(
                _pagina_login("", erro="Sessão de login expirada. Feche e conecte de novo."),
                status_code=400,
            )

        sub = await anyio.to_thread.run_sync(autenticar_supabase, email, senha)
        if not sub:
            return HTMLResponse(
                _pagina_login(req, email, erro="E-mail ou senha incorretos."), status_code=401
            )
        usuario_id = await anyio.to_thread.run_sync(_resolver_usuario_ativo, sub)
        if not usuario_id:
            return HTMLResponse(
                _pagina_login(
                    req, email,
                    erro="Este login não tem acesso ao Batuta. Peça um convite a um administrador.",
                ),
                status_code=403,
            )

        codigo = _assinar(
            "code",
            {
                "client_id": pedido["client_id"],
                "sub": usuario_id,
                "scopes": pedido["scopes"],
                "code_challenge": pedido["code_challenge"],
                "redirect_uri": pedido["redirect_uri"],
                "explicito": pedido["explicito"],
                "resource": pedido.get("resource"),
            },
            TTL_CODIGO,
        )
        destino = construct_redirect_uri(
            pedido["redirect_uri"], code=codigo, state=pedido.get("state")
        )
        return RedirectResponse(destino, status_code=302)
