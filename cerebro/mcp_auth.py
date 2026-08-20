"""Login OAuth mínimo (auto-aprovado) para a prova do MCP.

O claude.ai só conecta um custom connector via OAuth 2.1 (registro dinâmico do
cliente + authorize + token). Para a PROVA, este provedor cumpre o ritual do OAuth
mas **AUTO-APROVA**: não há tela de senha nem usuário real — qualquer cliente que
rode o fluxo recebe um token que dá acesso às ferramentas (que já são escopadas ao
time de teste). A postura de segurança é a mesma do "sem senha", só que embrulhada
no OAuth que o claude.ai exige.

A versão REAL (próxima fatia) amarra o `authorize` ao login do Batuta (Supabase) e
ao escopo por consultor/organização — aqui NÃO.

Guarda tudo em memória (some quando o processo reinicia) — aceitável para a prova.
As engrenagens do OAuth (rotas /authorize, /token, /register, metadados) vêm
prontas do SDK do MCP; este arquivo só implementa a lógica do provedor.
"""

import secrets
import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

TTL_CODIGO = 300  # validade do authorization code (s)
TTL_TOKEN = 3600 * 12  # validade do access token (s)
ESCOPO = "batuta"


def _novo(prefixo: str) -> str:
    return f"{prefixo}_{secrets.token_hex(24)}"


class ProvedorAutoAprovado(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """Servidor de autorização OAuth que aceita qualquer cliente e auto-aprova o
    login. É o mínimo para o claude.ai conectar o connector na PROVA."""

    def __init__(self) -> None:
        self._clientes: dict[str, OAuthClientInformationFull] = {}
        self._codigos: dict[str, AuthorizationCode] = {}
        self._tokens: dict[str, AccessToken] = {}
        self._refresh: dict[str, RefreshToken] = {}

    # ── cliente (registro dinâmico) ──
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clientes.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._clientes[client_info.client_id] = client_info

    # ── authorize (AUTO-APROVA: emite o código e redireciona de volta) ──
    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        codigo = _novo("code")
        self._codigos[codigo] = AuthorizationCode(
            code=codigo,
            scopes=params.scopes or [ESCOPO],
            expires_at=time.time() + TTL_CODIGO,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
            subject="prova",
        )
        return construct_redirect_uri(
            str(params.redirect_uri), code=codigo, state=params.state
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        c = self._codigos.get(authorization_code)
        if not c or c.client_id != client.client_id or c.expires_at < time.time():
            return None
        return c

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self._codigos.pop(authorization_code.code, None)  # código é de uso único
        acesso = _novo("at")
        renov = _novo("rt")
        escopos = authorization_code.scopes
        self._tokens[acesso] = AccessToken(
            token=acesso,
            client_id=client.client_id,
            scopes=escopos,
            expires_at=int(time.time() + TTL_TOKEN),
            resource=authorization_code.resource,
            subject="prova",
        )
        self._refresh[renov] = RefreshToken(
            token=renov, client_id=client.client_id, scopes=escopos, subject="prova"
        )
        return OAuthToken(
            access_token=acesso,
            token_type="Bearer",
            expires_in=TTL_TOKEN,
            scope=" ".join(escopos) or None,
            refresh_token=renov,
        )

    # ── verificação do token (usada pelo middleware que protege o MCP) ──
    async def load_access_token(self, token: str) -> AccessToken | None:
        t = self._tokens.get(token)
        if not t or (t.expires_at and t.expires_at < time.time()):
            return None
        return t

    # ── refresh ──
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        r = self._refresh.get(refresh_token)
        if not r or r.client_id != client.client_id:
            return None
        return r

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        escopos = scopes or refresh_token.scopes
        acesso = _novo("at")
        self._tokens[acesso] = AccessToken(
            token=acesso,
            client_id=client.client_id,
            scopes=escopos,
            expires_at=int(time.time() + TTL_TOKEN),
            subject="prova",
        )
        return OAuthToken(
            access_token=acesso,
            token_type="Bearer",
            expires_in=TTL_TOKEN,
            scope=" ".join(escopos) or None,
            refresh_token=refresh_token.token,
        )

    async def revoke_token(self, token) -> None:
        tok = getattr(token, "token", None)
        self._tokens.pop(tok, None)
        self._refresh.pop(tok, None)
