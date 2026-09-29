"""Um servidor MCP protegido por OAuth, DE VERDADE e local, para os testes da Fase 2.

Faz o papel dos dois lados do WordPress (`/wp-json/mcp/mcp-oauth-server`):
- o RECURSO: `/mcp` (FastMCP) só responde com `Authorization: Bearer <token válido>`;
  sem isso devolve 401 com `WWW-Authenticate: ... resource_metadata="..."` (RFC 9728);
- o SERVIDOR DE AUTORIZAÇÃO: metadados (RFC 8414), registro dinâmico (RFC 7591),
  `/authorize` (aprova sozinho e devolve o código ao redirect_uri) e `/token`
  (authorization_code com PKCE S256 conferido, refresh_token que GIRA, e
  client_credentials).

`atraso_token_s` alarga a janela de corrida no teste de renovação simultânea.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode

from mcp_servidor_falso import _mcp, _porta_livre

CLIENTE_MAQUINA = ("maquina", "segredo-maquina")


class ServidorOAuthFalso:
    def __init__(self, *, aceita_cimd: bool = False, validade_s: int = 3600, atraso_token_s: float = 0.0):
        import uvicorn

        self.aceita_cimd = aceita_cimd
        self.validade_s = validade_s
        self.atraso_token_s = atraso_token_s
        self.codigos: dict[str, dict] = {}
        self.acessos: set[str] = set()
        self.refreshes: set[str] = set()
        self.contagem = {"registro": 0, "codigo": 0, "refresh": 0, "cliente": 0}
        self.ultimo_pedido_autorizacao: dict = {}
        self._trava = threading.Lock()
        self.porta = _porta_livre()
        self.base = f"http://127.0.0.1:{self.porta}"
        self._mcp_app = _mcp("falso-oauth").streamable_http_app()
        self._servidor = uvicorn.Server(uvicorn.Config(self, host="127.0.0.1", port=self.porta, log_level="error"))
        threading.Thread(target=self._servidor.run, daemon=True).start()
        limite = time.monotonic() + 15
        while not self._servidor.started:
            if time.monotonic() > limite:
                raise RuntimeError("o servidor OAuth falso não subiu")
            time.sleep(0.05)

    @property
    def url_mcp(self) -> str:
        return f"{self.base}/mcp"

    def parar(self):
        self._servidor.should_exit = True

    def revogar_tudo(self):
        with self._trava:
            self.acessos.clear()
            self.refreshes.clear()

    # ───────────────────────── ASGI ─────────────────────────
    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self._mcp_app(scope, receive, send)
        if scope["type"] != "http":
            return
        caminho = scope["path"]
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        if caminho.startswith("/mcp"):
            auth = headers.get("authorization", "")
            token = auth[7:] if auth.startswith("Bearer ") else ""
            if token not in self.acessos:
                return await self._json(send, 401, {"error": "unauthorized"}, extra=[(
                    b"www-authenticate",
                    f'Bearer resource_metadata="{self.base}/.well-known/oauth-protected-resource/mcp", scope="mcp"'.encode(),
                )])
            return await self._mcp_app(scope, receive, send)
        corpo = b""
        while True:
            m = await receive()
            corpo += m.get("body", b"")
            if not m.get("more_body"):
                break
        query = parse_qs(scope.get("query_string", b"").decode())
        if caminho == "/.well-known/oauth-protected-resource/mcp":
            return await self._json(send, 200, {
                "resource": self.url_mcp, "authorization_servers": [self.base],
                "scopes_supported": ["mcp"],
            })
        if caminho == "/.well-known/oauth-authorization-server":
            return await self._json(send, 200, {
                "issuer": self.base,
                "authorization_endpoint": f"{self.base}/authorize",
                "token_endpoint": f"{self.base}/token",
                "registration_endpoint": f"{self.base}/register",
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
                "client_id_metadata_document_supported": self.aceita_cimd,
            })
        if caminho == "/register":
            self.contagem["registro"] += 1
            return await self._json(send, 201, {"client_id": "cli-dcr", "token_endpoint_auth_method": "none"})
        if caminho == "/authorize":
            p = {k: v[0] for k, v in query.items()}
            self.ultimo_pedido_autorizacao = p
            codigo = secrets.token_urlsafe(12)
            self.codigos[codigo] = p
            destino = p["redirect_uri"] + "?" + urlencode({"code": codigo, "state": p["state"]})
            await send({"type": "http.response.start", "status": 302,
                        "headers": [(b"location", destino.encode())]})
            return await send({"type": "http.response.body", "body": b""})
        if caminho == "/token":
            return await self._token(send, {k: v[0] for k, v in parse_qs(corpo.decode()).items()}, headers)
        return await self._json(send, 404, {"error": "not_found"})

    async def _token(self, send, f: dict, headers: dict):
        import asyncio

        if self.atraso_token_s:
            await asyncio.sleep(self.atraso_token_s)
        g = f.get("grant_type")
        if g == "authorization_code":
            p = self.codigos.pop(f.get("code", ""), None)
            desafio = base64.urlsafe_b64encode(
                hashlib.sha256(f.get("code_verifier", "").encode()).digest()
            ).decode().rstrip("=")
            if not p or p["code_challenge"] != desafio or p["client_id"] != f.get("client_id") \
                    or p.get("resource") != f.get("resource") or p["redirect_uri"] != f.get("redirect_uri"):
                return await self._json(send, 400, {"error": "invalid_grant"})
            self.contagem["codigo"] += 1
            return await self._json(send, 200, self._emitir(com_refresh=True))
        if g == "refresh_token":
            with self._trava:
                valido = f.get("refresh_token") in self.refreshes
                if valido:
                    self.refreshes.discard(f["refresh_token"])  # GIRA: o antigo morre
            if not valido:
                return await self._json(send, 400, {"error": "invalid_grant"})
            self.contagem["refresh"] += 1
            return await self._json(send, 200, self._emitir(com_refresh=True))
        if g == "client_credentials":
            auth = headers.get("authorization", "")
            par = (f.get("client_id"), f.get("client_secret"))
            if auth.startswith("Basic "):
                u, _, s = base64.b64decode(auth[6:]).decode().partition(":")
                par = (u, s)
            if par != CLIENTE_MAQUINA:
                return await self._json(send, 401, {"error": "invalid_client"})
            self.contagem["cliente"] += 1
            return await self._json(send, 200, self._emitir(com_refresh=False))
        return await self._json(send, 400, {"error": "unsupported_grant_type"})

    def _emitir(self, *, com_refresh: bool) -> dict:
        acesso = "AT-" + secrets.token_urlsafe(8)
        with self._trava:
            self.acessos.add(acesso)
            dados = {"access_token": acesso, "token_type": "Bearer", "expires_in": self.validade_s}
            if com_refresh:
                r = "RT-" + secrets.token_urlsafe(8)
                self.refreshes.add(r)
                dados["refresh_token"] = r
        return dados

    async def _json(self, send, status: int, corpo: dict, extra=None):
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), *(extra or [])]})
        await send({"type": "http.response.body", "body": json.dumps(corpo).encode()})
