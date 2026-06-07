"""Instrumento "Conectar a servidor MCP" (PRODUTO §13; Fase adicional).

O MCP (Model Context Protocol) é o padrão universal de integração de IA com
sistemas. Diferente dos outros instrumentos, UM instrumento MCP expõe VÁRIAS
ferramentas à IA — todas as que o servidor MCP publica. Por isso ele implementa
`expandir_ferramentas` (em vez de um único `executar`): a orquestração coloca
todas as ferramentas do servidor no cinto do agente.

O protocolo MCP é assíncrono; aqui ele é embrulhado de forma SÍNCRONA
(`asyncio.run`, conexão por chamada), para o motor síncrono não mudar. Suporta
servidores MCP por HTTP (`streamable_http`, padrão) ou `sse`. O token de
autenticação é um SEGREDO (cofre da Fase 7-B) e vira `Authorization: Bearer`.
"""

import asyncio
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar


class ConfigMCP(BaseModel):
    """Configuração de um servidor MCP. `token_bearer` é SEGREDO (cofre 7-B)."""

    url: str = Field(min_length=1, description="Endereço do servidor MCP.")
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


async def _carregar_ferramentas(config: ConfigMCP) -> list:
    """Conecta ao servidor MCP e devolve suas ferramentas (langchain tools,
    assíncronas). Cada chamada de ferramenta abre sua própria conexão."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    cliente = MultiServerMCPClient({"servidor": _conexao(config)})
    return await cliente.get_tools()


def _carregar_sync(config: ConfigMCP) -> list:
    """Versão síncrona de `_carregar_ferramentas` — embrulha o async para o
    motor síncrono. Levanta FalhaInstrumento se o servidor não responde."""
    try:
        return asyncio.run(_carregar_ferramentas(config))
    except Exception as e:  # conexão recusada, auth, protocolo — visível
        raise FalhaInstrumento(
            f"não foi possível conectar ao servidor MCP em {config.url}: {e}",
            retentavel=True,
        )


def _envolver_sync(ferramenta) -> StructuredTool:
    """Embrulha uma ferramenta MCP (assíncrona) numa ferramenta síncrona, para
    o laço de tool-calling síncrono do agente. Cada acionamento abre a própria
    conexão (stateless), via `asyncio.run`."""

    def acionar(**kwargs):
        return asyncio.run(ferramenta.ainvoke(kwargs))

    return StructuredTool(
        name=ferramenta.name,
        description=ferramenta.description or f"Ferramenta MCP {ferramenta.name}",
        args_schema=ferramenta.args_schema,
        func=acionar,
    )


class ConectarMCP(TipoInstrumento):
    tipo = "conectar_mcp"
    nome_exibicao = "Conectar a servidor MCP"
    descricao = (
        "Conecta o agente a um servidor MCP, dando-lhe acesso a TODAS as "
        "ferramentas que o servidor publica. Use para integrar com sistemas que "
        "expõem um servidor MCP."
    )
    Config = ConfigMCP
    Args = ArgsMCP
    campos_secretos = ("token_bearer",)
    acao_irreversivel = True  # não sabemos o que o servidor MCP faz; por segurança

    def executar(self, config: ConfigMCP, args: ArgsMCP) -> dict:
        """Acionamento isolado: testa a conexão e lista as ferramentas do
        servidor (não chama nenhuma)."""
        ferramentas = _carregar_sync(config)
        return {
            "ok": True,
            "url": config.url,
            "ferramentas": [
                {"nome": f.name, "descricao": f.description} for f in ferramentas
            ],
        }

    def expandir_ferramentas(self, config: ConfigMCP) -> list:
        """Todas as ferramentas do servidor MCP, prontas para o cinto do agente."""
        return [_envolver_sync(f) for f in _carregar_sync(config)]


registrar(ConectarMCP())
