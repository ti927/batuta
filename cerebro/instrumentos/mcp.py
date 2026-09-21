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
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

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
        description="Pede aprovação humana antes de rodar (ação que não dá para desfazer).",
    )


class ConfigMCP(BaseModel):
    """Configuração de um servidor MCP. `url` e `token_bearer` são SEGREDOS."""

    url: str = Field(
        default="",
        description="Endereço do servidor MCP (segredo: costuma embutir a chave).",
    )
    transport: Literal["streamable_http", "sse"] = Field(
        default="streamable_http",
        description="Protocolo de transporte do servidor MCP.",
    )
    cabecalhos: dict[str, str] = Field(
        default_factory=dict,
        description="Cabeçalhos fixos não-secretos (não coloque segredos aqui).",
    )
    token_bearer: str = Field(
        default="",
        description="Token de autenticação (segredo) → cabeçalho Authorization Bearer.",
    )
    ferramentas: list[FerramentaMCP] = Field(
        default_factory=list,
        description="Quais ferramentas do servidor entram no cinto, e quais pedem "
        "aprovação. Lista vazia = todas entram (e todas pedem aprovação).",
        # A tela desenha isto como uma LISTA DE ESCOLHA, não como um JSON cru: o
        # formulário genérico renderiza `array` num campo de texto, e pedir para alguém
        # digitar o JSON das ferramentas seria a mesma coisa que não ter a escolha.
        json_schema_extra={"ui": "ferramentas_mcp"},
    )


class ArgsMCP(BaseModel):
    """O acionamento isolado do MCP não pede argumentos — só testa a conexão e
    lista as ferramentas que o servidor publica."""


def _conexao(config: ConfigMCP) -> dict:
    cabecalhos = dict(config.cabecalhos or {})
    if config.token_bearer:
        cabecalhos["Authorization"] = f"Bearer {config.token_bearer}"
    return {
        "transport": config.transport,
        "url": config.url,
        "headers": cabecalhos or None,
    }


def _chave_cache(config: ConfigMCP) -> str:
    """Identidade do servidor para o cache — em HASH, nunca a URL crua: ela é
    segredo, e uma chave de dicionário vaza em qualquer dump de memória ou log."""
    cru = f"{config.transport}|{config.url}|{config.token_bearer}|{sorted((config.cabecalhos or {}).items())}"
    return hashlib.sha256(cru.encode("utf-8")).hexdigest()


async def _carregar_ferramentas(config: ConfigMCP) -> list:
    """Conecta ao servidor MCP e devolve suas ferramentas (langchain tools,
    assíncronas). Cada chamada de ferramenta abre sua própria conexão."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    cliente = MultiServerMCPClient({"servidor": _conexao(config)})
    return await cliente.get_tools()


def _carregar_sync(config: ConfigMCP, *, usar_cache: bool = True) -> list:
    """Versão síncrona de `_carregar_ferramentas` — embrulha o async para o
    motor síncrono. Levanta FalhaInstrumento se o servidor não responde.

    Com cache curto: a lista de ferramentas de um servidor não muda de minuto a
    minuto, e buscá-la a cada passo é uma ida à rede antes de todo trabalho útil."""
    if not (config.url or "").strip():
        raise FalhaInstrumento(
            "este instrumento não tem endereço de servidor MCP — preencha a URL "
            "(ou aponte para uma credencial 'Servidor MCP' da central).",
            retentavel=False,
        )
    chave = _chave_cache(config)
    agora = time.monotonic()
    if usar_cache:
        guardado = _CACHE.get(chave)
        if guardado and agora - guardado[0] < CACHE_SEGUNDOS:
            return guardado[1]
    try:
        ferramentas = asyncio.run(_carregar_ferramentas(config))
    except Exception as e:  # conexão recusada, auth, protocolo — visível
        # A URL é segredo: ela NÃO entra na mensagem (o erro vai para o rastro, que
        # o consultor lê na tela). Dizer "o servidor não respondeu" basta.
        raise FalhaInstrumento(
            f"não foi possível conectar ao servidor MCP deste instrumento: {e}",
            retentavel=True,
        )
    _CACHE[chave] = (agora, ferramentas)
    return ferramentas


def _envolver_sync(ferramenta, irreversivel: bool) -> StructuredTool:
    """Embrulha uma ferramenta MCP (assíncrona) numa ferramenta síncrona, para
    o laço de tool-calling síncrono do agente. Cada acionamento abre a própria
    conexão (stateless), via `asyncio.run`.

    O `metadata` carrega a irreversibilidade DESTA ferramenta — é por ele que o motor
    sabe quais param e pedem aprovação. Sem isso, a decisão só existiria no atacado
    (todo o instrumento), que é o que tornava o MCP inutilizável."""

    def acionar(**kwargs):
        return asyncio.run(ferramenta.ainvoke(kwargs))

    return StructuredTool(
        name=ferramenta.name,
        description=ferramenta.description or f"Ferramenta MCP {ferramenta.name}",
        args_schema=ferramenta.args_schema,
        func=acionar,
        metadata={"irreversivel": irreversivel},
    )


def _escolhidas(config: ConfigMCP) -> dict[str, FerramentaMCP] | None:
    """As ferramentas marcadas para entrar no cinto, por nome. `None` = a pessoa não
    escolheu nada ainda → todas entram (e todas pedem aprovação), que é o
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
    campos_secretos = ("url", "token_bearer")
    # `token_bearer` é opcional de verdade: um servidor que autentica pela URL não
    # tem token, e cobrá-lo faria o instrumento parecer incompleto para sempre.
    campos_secretos_opcionais = ("token_bearer",)
    tipos_credencial_aceitos = ("mcp", "token_bearer")
    # Baseline do TIPO. A irreversibilidade real é por instância (e, aqui, por
    # ferramenta) — ver `irreversivel_para`.
    acao_irreversivel = True

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

    def executar(self, config: ConfigMCP, args: ArgsMCP) -> dict:
        """Acionamento isolado: testa a conexão e lista as ferramentas do
        servidor (não chama nenhuma).

        É o que a tela usa para montar a lista de escolha. NÃO devolve a URL: ela é
        segredo, e o retorno do instrumento vai inteiro para o rastro da execução."""
        ferramentas = _carregar_sync(config, usar_cache=False)
        escolhidas = _escolhidas(config)
        return {
            "ok": True,
            "transporte": config.transport,
            "ferramentas": [
                {
                    "nome": f.name,
                    "descricao": f.description,
                    "no_cinto": escolhidas is None or f.name in escolhidas,
                    "pede_aprovacao": (
                        True
                        if escolhidas is None
                        else escolhidas[f.name].irreversivel
                        if f.name in escolhidas
                        else None
                    ),
                }
                for f in ferramentas
            ],
        }

    def expandir_ferramentas(self, config: ConfigMCP) -> list:
        """As ferramentas ESCOLHIDAS do servidor, prontas para o cinto do agente.

        Uma ferramenta escolhida que sumiu do servidor é simplesmente ignorada — o
        agente fica sem ela, e o rastro do "Acionar" mostra a diferença. Derrubar o
        passo porque um servidor de terceiro renomeou uma ferramenta seria pior."""
        escolhidas = _escolhidas(config)
        return [
            _envolver_sync(
                f, True if escolhidas is None else escolhidas[f.name].irreversivel
            )
            for f in _carregar_sync(config)
            if escolhidas is None or f.name in escolhidas
        ]


registrar(ConectarMCP())
