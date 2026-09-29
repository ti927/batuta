"""Instrumento "Conectar a servidor MCP" (PRODUTO §13; doc `docs/MCP-AGENTES.md`).

O MCP (Model Context Protocol) é o padrão universal de integração de IA com
sistemas. Diferente dos outros instrumentos, UM instrumento MCP expõe VÁRIAS
ferramentas à IA — as que o servidor MCP publica. Por isso ele implementa
`expandir_ferramentas` (em vez de um único `executar`): a orquestração coloca
essas ferramentas no cinto do agente.

O protocolo MCP é assíncrono; aqui ele é embrulhado de forma SÍNCRONA
(`asyncio.run`, conexão por chamada), para o motor síncrono não mudar. Suporta
servidores MCP por HTTP (`streamable_http`, padrão) ou `sse`.

**2026-09-21 — o que mudou e por quê.** O instrumento existia desde junho e tinha
ZERO instâncias em produção. Três motivos, todos consertados aqui:

1. **Trazia TODAS as ferramentas do servidor.** Um servidor como o do Zapier publica
   dezenas: o cinto entope, o custo por passo sobe e o agente escolhe errado. Agora a
   pessoa ESCOLHE quais entram (`ConfigMCP.ferramentas`).
2. **`acao_irreversivel` era `True` fixo** — até uma consulta parava e pedia aprovação,
   e desligar liberava tudo, inclusive o que apaga. Agora a decisão é POR FERRAMENTA
   (cada uma nasce pedindo aprovação; liberar é ato consciente).
3. **A URL era campo aberto.** Servidores como o do Zapier embutem a chave no endereço
   (`.../mcp/s/<chave>/mcp`) — ali a URL É a credencial, e credencial não aparece na
   interface (CLAUDE.md §8). Virou campo secreto, e o "Acionar" parou de devolvê-la.

O segredo pode vir da central de credenciais da ORGANIZAÇÃO (tipos `mcp` e
`token_bearer`): o instrumento é do time, a credencial é uma só, e a chave rotaciona
num lugar só.
"""

import asyncio
import hashlib
import time
from datetime import timedelta
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from instrumentos import mcp_conexao
from instrumentos.base import TipoInstrumento, registrar

# Por quanto tempo a lista de ferramentas de um servidor é reaproveitada. Sem cache,
# ela era buscada NA REDE a cada passo do agente — uma ida ao servidor de terceiro só
# para saber o que ele oferece, antes de qualquer trabalho útil.
CACHE_SEGUNDOS = 600
_CACHE: dict[str, tuple[float, list]] = {}


class FerramentaMCP(BaseModel):
    """Uma ferramenta do servidor, como ESTE instrumento a usa.

    `irreversivel` nasce `True` de propósito: o servidor é de terceiro e o Batuta não
    tem como saber o que cada ferramenta faz. Liberar é decisão de quem configurou —
    por ferramenta, e não no atacado."""

    nome: str = Field(min_length=1, description="Nome da ferramenta no servidor MCP.")
    usar: bool = Field(default=True, description="Entra no cinto do agente?")
    irreversivel: bool = Field(
        default=True,
        description="Altera algo lá fora (publica, envia, grava, apaga). Se falhar, o "
        "passo para. NÃO pede aprovação sozinha: quem pede é o agente (pedir_aprovacao).",
    )


class ConfigMCP(BaseModel):
    """Configuração de um servidor MCP.

    SEGREDOS (cofre do instrumento): `url`, `token_bearer`, `auth_segredo`,
    `cabecalhos_secretos`. O resto é público. Os modos de identificação estão em
    `mcp_conexao` (2026-09-29): antes só existia o token Bearer, e servidores reais —
    o WordPress com senha de aplicativo, APIs com `X-API-Key` — ficavam de fora."""

    url: str = Field(
        default="",
        description="Endereço do servidor MCP (segredo: costuma embutir a chave).",
    )
    # "automatico" é o padrão dos novos; instrumentos antigos guardaram
    # "streamable_http" e continuam exatamente como estavam.
    transport: Literal["automatico", "streamable_http", "sse"] = Field(
        default="automatico",
        description="Tipo de conexão: automático (tenta o atual e cai para o antigo), "
        "Streamable HTTP ou SSE (servidores antigos).",
    )
    auth_modo: Literal[
        "", "nenhuma", "url_secreta", "bearer", "cabecalho", "query", "basic",
        "oauth_login", "oauth_cliente",
    ] = Field(
        default="",
        description="Como o servidor pede identificação: nenhuma, url_secreta (a chave "
        "está no endereço: Make, Zapier), bearer (token), cabecalho (nome + valor), "
        "query (parâmetro no endereço), basic (usuário + senha; WordPress com senha de "
        "aplicativo), oauth_login (entrar com a conta: o consultor clica em Conectar na "
        "tela), oauth_cliente (OAuth entre sistemas: client_id + client secret). "
        "Vazio = instrumento antigo: bearer se tiver token, senão nenhuma.",
    )
    oauth_client_id: str = Field(
        default="",
        description="OAuth: Client ID. No oauth_cliente é obrigatório; no oauth_login é "
        "opcional (sem ele o Batuta se registra sozinho no servidor).",
    )
    oauth_url_token: str = Field(
        default="",
        description="OAuth entre sistemas: endereço que emite o token. Vazio = o Batuta "
        "descobre pelo servidor MCP.",
    )
    oauth_escopo: str = Field(
        default="", description="OAuth: escopo pedido (opcional; vazio = o que o servidor anuncia)."
    )
    # Preenchidos pelo Batuta (login e renovação), nunca digitados — segredos.
    oauth_access_token: str = Field(default="", description="Token de acesso OAuth (automático).")
    oauth_refresh_token: str = Field(default="", description="Token de renovação OAuth (automático).")
    oauth_client_secret: str = Field(
        default="", description="Client secret dado pelo registro automático (automático)."
    )
    # Certificado do cliente (mTLS), para servidores que exigem se identificar com um
    # certificado (bancos). Mesmo mecanismo do Construtor: a tela manda o ARQUIVO (e a
    # senha) só na hora de salvar; o Batuta guarda o par PEM no cofre do instrumento.
    certificado: str = Field(default="", description="Certificado do cliente em PEM (automático).")
    chave_privada: str = Field(default="", description="Chave do certificado em PEM (automático).")
    arquivo: str = Field(default="", description="Arquivo do certificado (.pfx/.p12/.pem), em base64 — só na hora de salvar.")
    chave_arquivo: str = Field(default="", description="Arquivo da chave (.key), se vier separado — só na hora de salvar.")
    senha_certificado: str = Field(default="", description="Senha do arquivo do certificado — não fica guardada.")
    auth_nome: str = Field(
        default="",
        description="Nome do cabeçalho (modo cabecalho, ex.: X-API-Key) ou do parâmetro "
        "(modo query, ex.: api_key). Não é segredo.",
    )
    auth_usuario: str = Field(
        default="", description="Usuário do modo basic (não é segredo)."
    )
    auth_segredo: str = Field(
        default="",
        description="A parte secreta do modo (segredo): o valor do cabeçalho, o valor "
        "do parâmetro, ou a senha do basic.",
    )
    cabecalhos: dict[str, str] = Field(
        default_factory=dict,
        description="Cabeçalhos fixos não-secretos (não coloque segredos aqui).",
    )
    cabecalhos_secretos: str = Field(
        default="",
        description="Cabeçalhos extras protegidos (segredo), em JSON {nome: valor}.",
    )
    token_bearer: str = Field(
        default="",
        description="Token do modo bearer (segredo) → cabeçalho Authorization Bearer.",
    )
    ferramentas: list[FerramentaMCP] = Field(
        default_factory=list,
        description="Quais ferramentas do servidor entram no cinto, e quais alteram "
        "algo lá fora. Lista vazia = todas entram (e todas contam como 'altera algo').",
        # A tela desenha isto como uma LISTA DE ESCOLHA, não como um JSON cru: o
        # formulário genérico renderiza `array` num campo de texto, e pedir para alguém
        # digitar o JSON das ferramentas seria a mesma coisa que não ter a escolha.
        json_schema_extra={"ui": "ferramentas_mcp"},
    )


class ArgsMCP(BaseModel):
    """O acionamento isolado do MCP não pede argumentos — só testa a conexão e
    lista as ferramentas que o servidor publica."""


def _conexao(destino: mcp_conexao.Destino, transporte: str) -> dict:
    """A conexão no formato do langchain-mcp-adapters, já com a identificação."""
    conexao = {
        "transport": transporte,
        "url": destino.url,
        "headers": destino.cabecalhos or None,
    }
    if destino.ssl is not None:
        # Certificado do cliente (mTLS): o contexto SSL já vem com ele carregado.
        conexao["httpx_client_factory"] = mcp_conexao.fabrica_http(destino.ssl)
    if transporte == "streamable_http":
        conexao["timeout"] = timedelta(seconds=mcp_conexao.TIMEOUT_HTTP_S)
        conexao["sse_read_timeout"] = timedelta(seconds=mcp_conexao.TIMEOUT_LEITURA_SSE_S)
    else:
        conexao["timeout"] = mcp_conexao.TIMEOUT_HTTP_S
        conexao["sse_read_timeout"] = mcp_conexao.TIMEOUT_LEITURA_SSE_S
    return conexao


def _chave_cache(config: ConfigMCP, transporte: str) -> str:
    """Identidade do servidor para o cache — em HASH, nunca a URL crua: ela é
    segredo, e uma chave de dicionário vaza em qualquer dump de memória ou log.
    Entra tudo o que muda a conexão (endereço, identificação, transporte)."""
    destino = mcp_conexao.montar_destino(config)
    cert = hashlib.sha256((config.certificado or "").encode()).hexdigest()
    cru = f"{transporte}|{destino.url}|{sorted(destino.cabecalhos.items())}|{cert}"
    return hashlib.sha256(cru.encode("utf-8")).hexdigest()


async def _carregar_ferramentas(config: ConfigMCP, transporte: str) -> tuple[str, list]:
    """Conecta ao servidor MCP e devolve (transporte usado, ferramentas langchain
    assíncronas). Cada chamada de ferramenta abre sua própria conexão."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    destino = mcp_conexao.montar_destino(config)

    async def tentar(t: str) -> list:
        cliente = MultiServerMCPClient({"servidor": _conexao(destino, t)})
        return await cliente.get_tools()

    return await mcp_conexao.com_transporte(transporte, tentar)


def _transporte_pedido(config: ConfigMCP, conhecido: str | None = None) -> str:
    """No "automático", usa o transporte que o último "Conectar" descobriu (evita
    uma tentativa perdida a cada passo); sem isso, descobre de novo."""
    if config.transport == "automatico" and conhecido in ("streamable_http", "sse"):
        return conhecido
    return config.transport


def _carregar_sync(
    config: ConfigMCP, *, usar_cache: bool = True, transporte: str | None = None
) -> list:
    """Versão síncrona de `_carregar_ferramentas` — embrulha o async para o
    motor síncrono. Levanta FalhaInstrumento (com `codigo`, sem segredo) se o
    servidor não responde.

    Com cache curto: a lista de ferramentas de um servidor não muda de minuto a
    minuto, e buscá-la a cada passo é uma ida à rede antes de todo trabalho útil."""
    pedido = transporte or config.transport
    chave = _chave_cache(config, pedido)  # já valida endereço e identificação
    agora = time.monotonic()
    if usar_cache:
        guardado = _CACHE.get(chave)
        if guardado and agora - guardado[0] < CACHE_SEGUNDOS:
            return guardado[1]
    try:
        _usado, ferramentas = asyncio.run(_carregar_ferramentas(config, pedido))
    except BaseException as e:  # noqa: BLE001 — conexão, identificação, protocolo
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        # O texto original do erro traz a URL — e a URL pode ser a chave. A mensagem
        # sai montada do zero em `classificar`.
        raise mcp_conexao.classificar(e, mcp_conexao.modo_efetivo(config)) from None
    _CACHE[chave] = (agora, ferramentas)
    return ferramentas


def _envolver_sync(ferramenta, irreversivel: bool, modo: str = "") -> StructuredTool:
    """Embrulha uma ferramenta MCP (assíncrona) numa ferramenta síncrona, para
    o laço de tool-calling síncrono do agente. Cada acionamento abre a própria
    conexão (stateless), via `asyncio.run`.

    O `metadata` carrega a irreversibilidade DESTA ferramenta — é por ele que o motor
    sabe quais alteram algo (falha delas para o passo). Sem isso, a decisão só existiria no atacado
    (todo o instrumento), que é o que tornava o MCP inutilizável."""

    def acionar(**kwargs):
        try:
            return asyncio.run(ferramenta.ainvoke(kwargs))
        except BaseException as e:  # noqa: BLE001
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            # Erro de conexão/HTTP carrega a URL (que pode ser a chave): sai
            # classificado. Um erro que a PRÓPRIA ferramenta devolveu (ToolException)
            # é dado do servidor e segue como está.
            from langchain_core.tools import ToolException

            if isinstance(e, ToolException):
                raise
            raise mcp_conexao.classificar(e, modo) from None

    return StructuredTool(
        name=ferramenta.name,
        description=ferramenta.description or f"Ferramenta MCP {ferramenta.name}",
        args_schema=ferramenta.args_schema,
        func=acionar,
        metadata={"irreversivel": irreversivel},
    )


def _escolhidas(config: ConfigMCP) -> dict[str, FerramentaMCP] | None:
    """As ferramentas marcadas para entrar no cinto, por nome. `None` = a pessoa não
    escolheu nada ainda → todas entram (e todas contam como "altera algo"), que é o
    comportamento antigo e o mais seguro dos dois."""
    escolhidas = [f for f in (config.ferramentas or []) if f.usar]
    if not escolhidas:
        return None
    return {f.nome: f for f in escolhidas}


class ConectarMCP(TipoInstrumento):
    tipo = "conectar_mcp"
    categoria = "Integrações e dados"
    nome_exibicao = "Conectar a servidor MCP"
    descricao = (
        "Conecta o agente a um servidor MCP (Zapier, Composio, ou um servidor "
        "próprio), dando-lhe acesso às ferramentas que você escolher entre as que o "
        "servidor publica."
    )
    Config = ConfigMCP
    Args = ArgsMCP
    # A URL é segredo junto com o token: servidores como o do Zapier embutem a chave
    # no endereço, e ali a URL É a credencial.
    campos_secretos = (
        "url", "token_bearer", "auth_segredo", "cabecalhos_secretos",
        "oauth_access_token", "oauth_refresh_token", "oauth_client_secret",
        "certificado", "chave_privada", "arquivo", "chave_arquivo", "senha_certificado",
    )
    # Qual deles FALTA depende do modo de identificação — ver `segredos_exigidos`.
    campos_secretos_opcionais = (
        "token_bearer", "auth_segredo", "cabecalhos_secretos",
        "oauth_access_token", "oauth_refresh_token", "oauth_client_secret",
        "certificado", "chave_privada", "arquivo", "chave_arquivo", "senha_certificado",
    )
    # Só existem na hora de salvar (viram o par PEM em `normalizar_config`).
    _TRANSITORIOS = ("arquivo", "chave_arquivo", "senha_certificado")
    tipos_credencial_aceitos = ("mcp", "token_bearer")
    # Baseline do TIPO. A irreversibilidade real é por instância (e, aqui, por
    # ferramenta) — ver `irreversivel_para`.
    acao_irreversivel = True
    # O "Conectar e listar" guarda o que descobriu em `instrumentos.conexao`.
    guarda_conexao = True

    def irreversivel_para(self, configuracao: dict) -> bool:
        """Esta instância faz ação irreversível?

        Antes isto era `True` fixo, e era um dos motivos de o MCP nunca ter rodado:
        um servidor só de consulta obrigava portão de aprovação. Agora a resposta sai
        das ferramentas ESCOLHIDAS — se nenhuma delas é irreversível, o instrumento
        não é. Sem escolha nenhuma, continua `True` (não sabemos o que o servidor faz).
        """
        try:
            config = ConfigMCP.model_validate(configuracao or {})
        except Exception:  # noqa: BLE001 — config inválida não é permissão para agir
            return True
        escolhidas = _escolhidas(config)
        if escolhidas is None:
            return True
        return any(f.irreversivel for f in escolhidas.values())

    def normalizar_config(self, bruta: dict) -> dict:
        """Converte o ARQUIVO de certificado no par PEM (igual ao Construtor). Sem
        arquivo, não mexe: o certificado guardado antes é preservado. A senha só abre
        o arquivo e não é guardada."""
        import certificados

        limpa = {k: v for k, v in bruta.items() if k not in self._TRANSITORIOS}
        arquivo = str(bruta.get("arquivo", "") or "").strip()
        if not arquivo:
            return limpa
        try:
            cert_pem, chave_pem, _titular, _expira = certificados.normalizar(
                arquivo,
                senha=str(bruta.get("senha_certificado", "") or ""),
                chave_b64=str(bruta.get("chave_arquivo", "") or ""),
            )
        except certificados.CertificadoInvalido as e:
            raise ValueError(f"Certificado: {e}")
        return {**limpa, "certificado": cert_pem, "chave_privada": chave_pem}

    def segredos_exigidos(self, configuracao: dict) -> tuple[str, ...]:
        """O endereço sempre; e a parte secreta do modo escolhido."""
        try:
            config = ConfigMCP.model_validate(configuracao or {})
        except Exception:  # noqa: BLE001
            return ("url",)
        modo = mcp_conexao.modo_efetivo(config)
        if modo == "bearer" and config.auth_modo:
            return ("url", "token_bearer")
        if modo in ("cabecalho", "query", "basic", "oauth_cliente"):
            return ("url", "auth_segredo")
        # oauth_login: o token vem do "Conectar", não de um campo colado.
        # Instrumento antigo (sem modo) não passa a acusar pendência que não tinha.
        return ("url",)

    def executar(self, config: ConfigMCP, args: ArgsMCP) -> dict:
        """Acionamento isolado: testa a conexão e lista o que o servidor oferece
        (não chama nenhuma ferramenta).

        É o que a tela usa para montar a lista de escolha. NÃO devolve a URL: ela é
        segredo, e o retorno do instrumento vai inteiro para o rastro da execução.

        `sugestao` é o que o SERVIDOR diz de cada ferramenta ("so_le"/"altera"). A tela
        mostra e pré-marca — quem decide continua sendo a pessoa. `conexao` é o estado
        que a rota guarda no instrumento (transporte, protocolo, servidor)."""
        inventario = mcp_conexao.descobrir_sync(config)
        escolhidas = _escolhidas(config)
        return {
            "ok": True,
            "transporte": inventario["transporte"],
            "protocolo": inventario["protocolo"],
            "servidor": inventario["servidor"],
            "ferramentas": [
                {
                    "nome": f["nome"],
                    "descricao": f["descricao"],
                    "sugestao": f["sugestao"],
                    "no_cinto": escolhidas is None or f["nome"] in escolhidas,
                    "pede_aprovacao": (
                        True
                        if escolhidas is None
                        else escolhidas[f["nome"]].irreversivel
                        if f["nome"] in escolhidas
                        else None
                    ),
                }
                for f in inventario["ferramentas"]
            ],
            "recursos": inventario["recursos"],
            "prompts": inventario["prompts"],
            "conexao": inventario["conexao"],
        }

    def expandir_ferramentas(self, config: ConfigMCP, transporte: str | None = None) -> list:
        """As ferramentas ESCOLHIDAS do servidor, prontas para o cinto do agente.

        Uma ferramenta escolhida que sumiu do servidor é simplesmente ignorada — o
        agente fica sem ela, e o rastro do "Acionar" mostra a diferença. Derrubar o
        passo porque um servidor de terceiro renomeou uma ferramenta seria pior."""
        escolhidas = _escolhidas(config)
        modo = mcp_conexao.modo_efetivo(config)
        return [
            _envolver_sync(
                f, True if escolhidas is None else escolhidas[f.name].irreversivel, modo
            )
            for f in _carregar_sync(config, transporte=transporte)
            if escolhidas is None or f.name in escolhidas
        ]

    def expandir_ferramentas_da_instancia(self, instrumento, config: ConfigMCP) -> list:
        """Usa o transporte que o último "Conectar" descobriu (guardado no estado da
        conexão do instrumento), para o "automático" não gastar uma tentativa por passo."""
        conhecido = (getattr(instrumento, "conexao", None) or {}).get("transporte")
        return self.expandir_ferramentas(config, _transporte_pedido(config, conhecido))


registrar(ConectarMCP())
