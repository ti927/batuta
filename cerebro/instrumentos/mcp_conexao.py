"""Como o Batuta fala com um servidor MCP: identificação, transporte e erros.

Separado de `mcp.py` (o instrumento) porque é a parte que muda por SERVIDOR, não por
agente. Três responsabilidades:

1. **Identificação** (`montar_destino`): cada modo vira endereço + cabeçalhos.
   - nenhuma / url_secreta: nada além do endereço. No Make e no Zapier a chave está
     no próprio endereço.
   - bearer: `Authorization: Bearer <token>`.
   - cabecalho: `<nome>: <valor>`, ex.: `X-API-Key`.
   - query: `?<nome>=<valor>` no endereço.
   - basic: usuário + senha. É o WordPress com senha de aplicativo.
   Os cabeçalhos extras protegidos se somam a qualquer modo.
2. **Erros sem segredo** (`classificar`): a biblioteca devolve o erro HTTP com a URL
   INTEIRA no texto. No Zapier e no Make a URL é a chave, e esse texto ia para a tela
   e para o banco de logs. Aqui a mensagem é montada do zero: diz o que houve, o que
   fazer, e um `codigo` estável (`mcp.auth_401`…) para o diagnóstico.
3. **Transporte** (`descobrir`): "automático" tenta o Streamable HTTP (o atual da
   especificação) e cai para o SSE de 2024-11-05 quando o servidor responde como
   legado (400/404/405 ao POST) — o mesmo teste de compatibilidade que a
   especificação manda o cliente fazer.
"""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from instrumentos.base import FalhaInstrumento, validar_cabecalhos_ascii

MODOS_AUTH = (
    "nenhuma", "url_secreta", "bearer", "cabecalho", "query", "basic",
    "oauth_login", "oauth_cliente",
)
TRANSPORTES = ("automatico", "streamable_http", "sse")

# Tetos (CLAUDE.md §12-A: nenhuma ligação sem limite). O servidor é de terceiro.
TIMEOUT_HTTP_S = 30
TIMEOUT_LEITURA_SSE_S = 300
TIMEOUT_DESCOBERTA_S = 60
# Paginação de tools/list: um servidor que nunca para de devolver cursor não pode
# prender o passo. 50 páginas é muito mais do que qualquer servidor real publica.
MAX_PAGINAS = 50

# Respostas do servidor que, ao POST do Streamable HTTP, indicam servidor LEGADO
# (HTTP+SSE de 2024-11-05) — é o critério da própria especificação.
_STATUS_LEGADO = {400, 404, 405}


@dataclass
class Destino:
    url: str
    cabecalhos: dict[str, str] = field(default_factory=dict)
    # Contexto SSL da conexão (com o certificado do cliente, se houver — mTLS).
    ssl: object | None = None


def _contexto_base():
    """O contexto SSL padrão (verifica o servidor). Separado para os testes poderem
    confiar numa autoridade local."""
    return httpx.create_ssl_context()


def contexto_mtls(certificado: str, chave_privada: str):
    """Contexto SSL que APRESENTA o certificado do cliente. O `ssl` só carrega de
    arquivo: o par vira arquivo temporário só durante o `load_cert_chain`."""
    import certificados

    contexto = _contexto_base()
    if not (certificado or "").strip() or not (chave_privada or "").strip():
        return contexto  # sem certificado: a verificação normal do servidor
    try:
        with certificados.material_mtls(certificado, chave_privada) as par:
            contexto.load_cert_chain(*par)
    except Exception:  # noqa: BLE001 — PEM corrompido, par que não bate
        raise FalhaInstrumento(
            "o certificado guardado neste instrumento não abre (ou a chave não é dele). "
            "Envie o arquivo do certificado de novo em “Avançado”.",
            retentavel=False,
            codigo="mcp.certificado_invalido",
        )
    return contexto


def fabrica_http(contexto):
    """Fábrica de cliente HTTP no formato que a biblioteca MCP espera, com o
    certificado do cliente — usada no SSE e nas ferramentas do cinto."""

    def criar(headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(
            headers=headers, timeout=timeout or httpx.Timeout(TIMEOUT_HTTP_S),
            auth=auth, follow_redirects=True, verify=contexto if contexto is not None else True,
        )

    return criar


def modo_efetivo(config) -> str:
    """O modo de identificação desta configuração.

    Instrumentos criados antes do campo existir não têm modo: viram `bearer` se têm
    token (era o único jeito de mandar um) e `nenhuma` se não têm — exatamente o que
    faziam antes, sem migração."""
    modo = (getattr(config, "auth_modo", "") or "").strip()
    if modo:
        return modo
    return "bearer" if (getattr(config, "token_bearer", "") or "").strip() else "nenhuma"


def _faltou(o_que: str) -> FalhaInstrumento:
    return FalhaInstrumento(
        f"falta {o_que} deste instrumento — preencha na tela do instrumento, em "
        "“Como o Batuta se conecta”.",
        retentavel=False,
        codigo="mcp.segredo_faltando",
    )


def cabecalhos_secretos(config) -> dict[str, str]:
    """Os cabeçalhos extras marcados como protegidos. Guardados como UM segredo (JSON
    `{nome: valor}`), porque o cofre do instrumento guarda texto por campo."""
    cru = (getattr(config, "cabecalhos_secretos", "") or "").strip()
    if not cru:
        return {}
    try:
        dados = json.loads(cru)
    except ValueError:
        dados = None
    if not isinstance(dados, dict):
        raise FalhaInstrumento(
            "os cabeçalhos protegidos deste instrumento estão num formato que o Batuta "
            "não entende — apague-os e cadastre de novo na tela do instrumento.",
            retentavel=False,
            codigo="mcp.config_invalida",
        )
    return {str(k): str(v) for k, v in dados.items() if str(k).strip()}


def montar_destino(config) -> Destino:
    """Endereço + cabeçalhos para o modo de identificação escolhido.

    Levanta `FalhaInstrumento` (não retentável) quando falta um pedaço do modo — é
    melhor dizer "falta a senha" do que mandar a chamada e ouvir um 401."""
    url = (getattr(config, "url", "") or "").strip()
    if not url:
        raise FalhaInstrumento(
            "este instrumento não tem endereço de servidor MCP — preencha o endereço "
            "na tela do instrumento.",
            retentavel=False,
            codigo="mcp.sem_endereco",
        )
    cab = dict(getattr(config, "cabecalhos", None) or {})
    cab.update(cabecalhos_secretos(config))
    modo = modo_efetivo(config)
    segredo = (getattr(config, "auth_segredo", "") or "").strip()
    nome = (getattr(config, "auth_nome", "") or "").strip()

    if modo == "bearer":
        token = (getattr(config, "token_bearer", "") or "").strip()
        if not token:
            raise _faltou("o token")
        cab["Authorization"] = f"Bearer {token}"
    elif modo == "cabecalho":
        if not nome:
            raise _faltou("o nome do cabeçalho")
        if not segredo:
            raise _faltou("o valor do cabeçalho")
        cab[nome] = segredo
    elif modo == "query":
        if not nome:
            raise _faltou("o nome do parâmetro")
        if not segredo:
            raise _faltou("o valor da chave")
        url = str(httpx.URL(url).copy_merge_params({nome: segredo}))
    elif modo == "basic":
        usuario = (getattr(config, "auth_usuario", "") or "").strip()
        if not usuario:
            raise _faltou("o usuário")
        if not segredo:
            raise _faltou("a senha")
        par = base64.b64encode(f"{usuario}:{segredo}".encode("utf-8")).decode("ascii")
        cab["Authorization"] = f"Basic {par}"
    elif modo in ("oauth_login", "oauth_cliente"):
        # O token chega pronto: a borda (`anexar_aos_instrumentos`) o renova antes.
        token = (getattr(config, "oauth_access_token", "") or "").strip()
        if not token:
            raise FalhaInstrumento(
                "este instrumento não está conectado (ou a conexão da conta caiu). Abra "
                "o instrumento e clique em “Conectar”."
                if modo == "oauth_login"
                else "o servidor não entregou o token de acesso — confira o Client ID e "
                "o Client Secret em “Como o Batuta se conecta”.",
                retentavel=False,
                codigo="mcp.precisa_conectar" if modo == "oauth_login" else "mcp.oauth_recusado",
            )
        cab["Authorization"] = f"Bearer {token}"
    elif modo not in ("nenhuma", "url_secreta"):
        raise FalhaInstrumento(
            f"modo de identificação desconhecido: {modo!r}.",
            retentavel=False,
            codigo="mcp.config_invalida",
        )
    validar_cabecalhos_ascii(cab)
    return Destino(
        url=url, cabecalhos=cab,
        ssl=contexto_mtls(
            getattr(config, "certificado", "") or "", getattr(config, "chave_privada", "") or ""
        ),
    )


# ───────────────────────────── erros sem segredo ─────────────────────────────

def _folhas(e: BaseException) -> list[BaseException]:
    """A biblioteca MCP roda em grupos de tarefas: o erro real vem embrulhado em
    `ExceptionGroup` (às vezes em dois níveis). Achata para as causas de verdade."""
    if isinstance(e, BaseExceptionGroup):
        saida: list[BaseException] = []
        for sub in e.exceptions:
            saida.extend(_folhas(sub))
        return saida
    return [e]


def status_http(e: BaseException) -> int | None:
    for f in _folhas(e):
        if isinstance(f, httpx.HTTPStatusError):
            return f.response.status_code
    return None


def _sessao_encerrada(e: BaseException) -> bool:
    """O Streamable HTTP da biblioteca traduz um 404 ao POST em "Session terminated"."""
    from mcp.shared.exceptions import McpError

    return any(
        isinstance(f, McpError) and "session terminated" in str(f).lower()
        for f in _folhas(e)
    )


def parece_legado(e: BaseException) -> bool:
    """O erro do Streamable HTTP indica um servidor do transporte antigo (SSE)?"""
    return status_http(e) in _STATUS_LEGADO or _sessao_encerrada(e)


def _msg_auth(modo: str) -> str:
    return {
        "bearer": "Confira se o token continua valendo (alguns serviços invalidam o "
        "antigo quando você gera outro).",
        "basic": "Confira o usuário e a senha. No WordPress, use uma senha de "
        "aplicativo, não a senha de entrar no site.",
        "cabecalho": "Confira o nome do cabeçalho e o valor da chave.",
        "query": "Confira o nome do parâmetro e o valor da chave.",
        "url_secreta": "Confira se o endereço copiado está completo e ainda vale "
        "(gerar um endereço novo invalida o antigo).",
        "nenhuma": "Este servidor pede identificação — escolha como ele pede em "
        "“Como o Batuta se conecta”.",
        "oauth_login": "A conexão da conta caiu — abra o instrumento e clique em "
        "“Conectar” de novo.",
        "oauth_cliente": "Confira o Client ID, o Client Secret e o escopo.",
    }.get(modo, "Confira a identificação do instrumento.")


def classificar(e: BaseException, modo: str = "") -> FalhaInstrumento:
    """Traduz qualquer erro da conexão numa `FalhaInstrumento` com mensagem humana e
    `codigo`, SEM o texto original (que carrega a URL — e a URL pode ser a chave)."""
    if isinstance(e, FalhaInstrumento):
        return e
    status = status_http(e)
    if status == 401:
        return FalhaInstrumento(
            "o servidor MCP recusou a identificação (401). " + _msg_auth(modo),
            retentavel=False, codigo="mcp.auth_401",
        )
    if status == 403:
        return FalhaInstrumento(
            "o servidor MCP reconheceu a identificação mas negou o acesso (403). "
            "Confira se esta conta tem permissão para usar o servidor.",
            retentavel=False, codigo="mcp.auth_403",
        )
    if status == 404 or _sessao_encerrada(e):
        return FalhaInstrumento(
            "o servidor não encontrou o endereço MCP (404). Confira se o endereço está "
            "completo — muitos terminam em /mcp ou /sse.",
            retentavel=False, codigo="mcp.endereco_404",
        )
    if status in (400, 405, 406, 415):
        return FalhaInstrumento(
            f"o servidor não aceitou o jeito de conversar do Batuta ({status}). Em "
            "“Avançado”, deixe o tipo de conexão em “Automático” ou troque para o outro.",
            retentavel=False, codigo="mcp.transporte_incompativel",
        )
    if status == 429:
        return FalhaInstrumento(
            "o servidor MCP pediu para esperar (limite de uso, 429). Tente de novo em "
            "alguns minutos.",
            retentavel=True, codigo="mcp.limite_429",
        )
    if status is not None and status >= 500:
        return FalhaInstrumento(
            f"o servidor MCP está com problema ({status}). Não é a configuração do "
            "Batuta — tente de novo mais tarde.",
            retentavel=True, codigo="mcp.servidor_5xx",
        )
    folhas = _folhas(e)
    if any(isinstance(f, (httpx.TimeoutException, asyncio.TimeoutError, TimeoutError)) for f in folhas):
        return FalhaInstrumento(
            "o servidor MCP demorou demais para responder. Tente de novo; se continuar, "
            "o servidor pode estar fora do ar.",
            retentavel=True, codigo="mcp.tempo_esgotado",
        )
    import ssl as _ssl

    if any(
        isinstance(f, _ssl.SSLError)
        or (isinstance(f, httpx.ConnectError) and ("ssl" in str(f).lower() or "certificate" in str(f).lower()))
        for f in folhas
    ):
        return FalhaInstrumento(
            "a conexão segura com o servidor MCP falhou — ou ele exige o certificado do "
            "cliente (envie-o em “Avançado”), ou recusou o certificado enviado.",
            retentavel=False, codigo="mcp.certificado_recusado",
        )
    if any(isinstance(f, (httpx.RemoteProtocolError, httpx.ReadError)) for f in folhas):
        # Um servidor que EXIGE certificado do cliente e não recebe nenhum derruba a
        # conexão sem responder (TLS 1.3) — indistinguível de um servidor que caiu no
        # meio. A mensagem diz as duas coisas, em vez de chutar uma.
        return FalhaInstrumento(
            "o servidor MCP encerrou a conexão sem responder. Se ele exige certificado "
            "do cliente (bancos, por exemplo), envie-o em “Avançado”; senão, ele pode "
            "estar fora do ar — tente de novo mais tarde.",
            retentavel=True, codigo="mcp.conexao_encerrada",
        )
    if any(isinstance(f, (httpx.ConnectError, httpx.NetworkError)) for f in folhas):
        return FalhaInstrumento(
            "não foi possível alcançar o servidor MCP — ele pode estar fora do ar, ou o "
            "endereço está errado.",
            retentavel=True, codigo="mcp.fora_do_ar",
        )
    if any(isinstance(f, httpx.UnsupportedProtocol) or isinstance(f, httpx.InvalidURL) for f in folhas):
        return FalhaInstrumento(
            "o endereço do servidor MCP não é válido — ele precisa começar com https://.",
            retentavel=False, codigo="mcp.endereco_invalido",
        )
    # Sem o texto original: só o NOME do erro, que não carrega segredo.
    nomes = ", ".join(sorted({type(f).__name__ for f in folhas}))
    return FalhaInstrumento(
        "a conversa com o servidor MCP falhou de um jeito inesperado. Use “Conectar e "
        f"listar ferramentas” para testar de novo. (detalhe técnico: {nomes})",
        retentavel=True, codigo="mcp.falha_protocolo",
    )


# ───────────────────────────── sessão e descoberta ─────────────────────────────

async def _com_sessao(transporte: str, destino: Destino, trabalho):
    """Abre uma sessão MCP no transporte pedido e roda `trabalho(sessao, init)`."""
    from mcp import ClientSession

    if transporte == "sse":
        from mcp.client.sse import sse_client

        extra = {"httpx_client_factory": fabrica_http(destino.ssl)} if destino.ssl else {}
        async with sse_client(
            destino.url, headers=destino.cabecalhos or None,
            timeout=TIMEOUT_HTTP_S, sse_read_timeout=TIMEOUT_LEITURA_SSE_S, **extra,
        ) as (leitura, escrita):
            async with ClientSession(leitura, escrita) as sessao:
                init = await sessao.initialize()
                return await trabalho(sessao, init)
    from mcp.client.streamable_http import streamable_http_client

    cliente_http = fabrica_http(destino.ssl)(
        headers=destino.cabecalhos or None,
        timeout=httpx.Timeout(TIMEOUT_HTTP_S, read=TIMEOUT_LEITURA_SSE_S),
    )
    async with cliente_http:
        async with streamable_http_client(destino.url, http_client=cliente_http) as (
            leitura, escrita, _sessao_id,
        ):
            async with ClientSession(leitura, escrita) as sessao:
                init = await sessao.initialize()
                return await trabalho(sessao, init)


def _sugestao(anotacoes) -> str | None:
    """O que o SERVIDOR diz da ferramenta — só sugestão para a tela, nunca decisão."""
    if anotacoes is None:
        return None
    if getattr(anotacoes, "destructiveHint", None):
        return "altera"
    if getattr(anotacoes, "readOnlyHint", None):
        return "so_le"
    return None


async def _inventario(sessao, init) -> dict:
    ferramentas: list[dict] = []
    cursor = None
    for _ in range(MAX_PAGINAS):
        pagina = await sessao.list_tools(cursor=cursor) if cursor else await sessao.list_tools()
        for t in pagina.tools:
            ferramentas.append({
                "nome": t.name,
                "descricao": t.description or "",
                "sugestao": _sugestao(t.annotations),
            })
        cursor = getattr(pagina, "nextCursor", None)
        if not cursor:
            break
    capacidades = init.capabilities
    recursos: list[dict] = []
    prompts: list[dict] = []
    # Recursos e prompts só são LISTADOS (a tela mostra; o agente ainda não usa).
    # Falhar aqui não pode derrubar a conexão, que já provou funcionar.
    if getattr(capacidades, "resources", None) is not None:
        try:
            r = await sessao.list_resources()
            recursos = [
                {"nome": x.name, "uri": str(x.uri), "descricao": x.description or ""}
                for x in r.resources
            ]
        except Exception:  # noqa: BLE001
            recursos = []
    if getattr(capacidades, "prompts", None) is not None:
        try:
            p = await sessao.list_prompts()
            prompts = [{"nome": x.name, "descricao": x.description or ""} for x in p.prompts]
        except Exception:  # noqa: BLE001
            prompts = []
    info = init.serverInfo
    return {
        "protocolo": init.protocolVersion,
        "servidor": {"nome": info.name, "versao": info.version} if info else None,
        "ferramentas": ferramentas,
        "recursos": recursos,
        "prompts": prompts,
    }


async def com_transporte(transporte: str, tentar) -> tuple[str, object]:
    """Roda `tentar(transporte)` no transporte pedido; no "automático", tenta o
    Streamable HTTP e cai para o SSE se o servidor responder como legado. Devolve
    (transporte usado, resultado). Os erros saem crus — quem chama classifica.

    Serve às duas portas: a descoberta ("Conectar e listar") e o cinto do agente."""
    if transporte in ("streamable_http", "sse"):
        return transporte, await asyncio.wait_for(tentar(transporte), TIMEOUT_DESCOBERTA_S)
    try:
        return "streamable_http", await asyncio.wait_for(
            tentar("streamable_http"), TIMEOUT_DESCOBERTA_S
        )
    except BaseException as primeiro:  # noqa: BLE001 — grupos de exceção incluídos
        if isinstance(primeiro, (KeyboardInterrupt, SystemExit)) or not parece_legado(primeiro):
            raise
        try:
            return "sse", await asyncio.wait_for(tentar("sse"), TIMEOUT_DESCOBERTA_S)
        except BaseException as segundo:  # noqa: BLE001
            # Se o SSE falhou por identificação, ESSE é o problema real; senão o
            # servidor não é SSE e o primeiro erro diz mais.
            if status_http(segundo) in (401, 403):
                raise segundo
            raise primeiro


def descobrir_sync(config) -> dict:
    """Conecta, negocia o protocolo e lista tudo o que o servidor oferece.

    No "automático" sempre redescobre o transporte: o "Conectar" é o teste da verdade.
    Devolve o inventário + o estado da conexão a guardar. Levanta `FalhaInstrumento`
    classificada (sem segredo)."""
    destino = montar_destino(config)
    pedido = getattr(config, "transport", "automatico") or "automatico"
    try:
        usado, inventario = asyncio.run(
            com_transporte(pedido, lambda t: _com_sessao(t, destino, _inventario))
        )
    except BaseException as e:  # noqa: BLE001
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        raise classificar(e, modo_efetivo(config)) from None
    inventario["transporte"] = usado
    inventario["conexao"] = {
        "estado": "conectado",
        "transporte": usado,
        "protocolo": inventario["protocolo"],
        "servidor": inventario["servidor"],
        "verificado_em": datetime.now(timezone.utc).isoformat(),
    }
    return inventario


def estado_de_falha(falha: FalhaInstrumento) -> dict:
    """O que guardar no estado da conexão quando o teste falha (sem segredo)."""
    return {
        "estado": "falhou",
        "codigo": falha.codigo,
        "mensagem": str(falha)[:300],
        "verificado_em": datetime.now(timezone.utc).isoformat(),
    }
