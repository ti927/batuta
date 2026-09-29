"""Um servidor MCP DE VERDADE, local, para os testes do instrumento MCP.

Antes de 2026-09-29 os testes do MCP mockavam a conexão inteira — nenhum provava que
o Batuta conversa com um servidor real. Este sobe dois servidores (FastMCP da própria
biblioteca MCP, via uvicorn numa thread): um no transporte atual (Streamable HTTP, em
`/mcp`) e um no legado (HTTP+SSE, em `/sse`).

A porta confere a identificação ANTES do MCP (middleware ASGI puro — o
`BaseHTTPMiddleware` do Starlette quebra o fluxo do SSE). Aceita qualquer um dos
modos, com os valores fixos abaixo:

- `Authorization: Bearer TOKEN_OK`
- `Authorization: Basic claude.ia:SENHA-APP` (o WordPress com senha de aplicativo)
- `X-API-Key: CHAVE_OK` (cabeçalho personalizado)
- `?api_key=CHAVE_OK` (chave na query)
- endereço com `/s/CHAVE_URL/` (a chave no endereço, como Make/Zapier)
- endereço com `/aberto/` (servidor que não pede identificação)

E o prefixo `/extra/` exige, ALÉM da identificação, o cabeçalho `X-Tenant: acme`
(para provar os cabeçalhos extras).
"""

from __future__ import annotations

import base64
import socket
import threading
import time
from urllib.parse import parse_qs

TOKEN_OK = "TOKEN_OK"
USUARIO_OK = "claude.ia"
SENHA_OK = "SENHA-APP"
CHAVE_OK = "CHAVE_OK"
CHAVE_URL = "CHAVE_URL"


def _porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def _identificado(headers: dict[str, str], query: dict) -> bool:
    auth = headers.get("authorization", "")
    if auth == f"Bearer {TOKEN_OK}":
        return True
    basic = base64.b64encode(f"{USUARIO_OK}:{SENHA_OK}".encode()).decode()
    if auth == f"Basic {basic}":
        return True
    if headers.get("x-api-key") == CHAVE_OK:
        return True
    return query.get("api_key", [None])[0] == CHAVE_OK


class _Porteiro:
    """Middleware ASGI: confere a identificação e tira o prefixo do caminho."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        caminho: str = scope["path"]
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        query = parse_qs(scope.get("query_string", b"").decode())
        liberado = False
        exige_extra = False
        for prefixo in ("/aberto", f"/s/{CHAVE_URL}", "/extra"):
            if caminho.startswith(prefixo + "/"):
                caminho = caminho[len(prefixo):]
                liberado = prefixo != "/extra"
                exige_extra = prefixo == "/extra"
                break
        if not liberado and not _identificado(headers, query):
            return await _responder(send, 401, b'{"erro":"nao identificado"}')
        if exige_extra and headers.get("x-tenant") != "acme":
            return await _responder(send, 403, b'{"erro":"sem tenant"}')
        scope = dict(scope, path=caminho, raw_path=caminho.encode())
        return await self.app(scope, receive, send)


async def _responder(send, status: int, corpo: bytes):
    await send({
        "type": "http.response.start", "status": status,
        "headers": [(b"content-type", b"application/json"),
                    (b"www-authenticate", b'Bearer realm="falso"')],
    })
    await send({"type": "http.response.body", "body": corpo})


def _mcp(nome: str):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    servidor = FastMCP(nome)

    @servidor.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def ler(texto: str) -> str:
        """Lê algo (o servidor diz: só lê)."""
        return f"lido {texto}"

    @servidor.tool(annotations=ToolAnnotations(destructiveHint=True))
    def apagar(texto: str) -> str:
        """Apaga algo (o servidor diz: altera)."""
        return f"apagado {texto}"

    @servidor.tool()
    def neutra(texto: str) -> str:
        """Sem anotação nenhuma."""
        return texto

    @servidor.resource("doc://manual")
    def manual() -> str:
        """O manual."""
        return "conteúdo"

    @servidor.prompt()
    def saudacao() -> str:
        """Um prompt."""
        return "oi"

    return servidor


def _subir(app) -> tuple[int, object]:
    import uvicorn

    porta = _porta_livre()
    servidor = uvicorn.Server(
        uvicorn.Config(_Porteiro(app), host="127.0.0.1", port=porta, log_level="error")
    )
    threading.Thread(target=servidor.run, daemon=True).start()
    limite = time.monotonic() + 15
    while not servidor.started:
        if time.monotonic() > limite:
            raise RuntimeError("o servidor MCP falso não subiu")
        time.sleep(0.05)
    return porta, servidor


class ServidoresFalsos:
    """Os dois servidores no ar. `url_http(prefixo)` e `url_sse(prefixo)` montam o
    endereço (ex.: prefixo "/aberto" ou f"/s/{CHAVE_URL}")."""

    def __init__(self):
        self.porta_http, self._http = _subir(_mcp("falso-http").streamable_http_app())
        self.porta_sse, self._sse = _subir(_mcp("falso-sse").sse_app())

    def url_http(self, prefixo: str = "") -> str:
        return f"http://127.0.0.1:{self.porta_http}{prefixo}/mcp"

    def url_sse(self, prefixo: str = "") -> str:
        return f"http://127.0.0.1:{self.porta_sse}{prefixo}/sse"

    def parar(self):
        for s in (self._http, self._sse):
            s.should_exit = True
