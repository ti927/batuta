"""Prova de conceito — Batuta como servidor MCP (Model Context Protocol).

Expõe um punhado de ferramentas de CRIAÇÃO/AJUSTE do Batuta por um MCP remoto
(Streamable HTTP), para o consultor conectar do PRÓPRIO claude.ai (custom connector)
e montar/ajustar agentes conversando com o Claude — rodando na ASSINATURA dele, não
na API do Batuta. É o padrão permitido pela Anthropic (o app do usuário aciona a
ferramenta; o Batuta não roteia assinatura de ninguém).

ESCOPO DELIBERADAMENTE MÍNIMO E DESCARTÁVEL (ver docs do plano):
- Tudo escopado a UM time de teste fixo (`MCP_PROVA_TIME_ID`) — o raio de dano é um
  time descartável, mesmo que a URL vaze.
- Sem autenticação (o connector PESSOAL do claude.ai Pro/Max aceita servidor sem
  auth para desenvolvimento). Segurança real = OAuth 2.1 + escopo por consultor, que
  é a PRÓXIMA fatia, fora desta prova.
- Só liga quando `MCP_PROVA_ATIVA` está setada; com a flag off, este módulo não é
  montado e nada no cérebro muda.

Reuso: as ferramentas NÃO usam os tools da criadora (acoplados a um turno/conversa);
usam a camada de serviço por baixo — `criacao.servicos` (a MESMA porta validada por
onde a IA e as rotas REST escrevem no time real).
"""

import contextlib
import os
import uuid

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import func, select

from criacao import servicos
from modelos import Agente, Time
from sessao import CriadorDeSessao


# ───────────────────────────── Configuração ─────────────────────────────

def ativa() -> bool:
    """Se a prova está ligada. Off = o cérebro não muda em nada."""
    return os.environ.get("MCP_PROVA_ATIVA", "").strip().lower() in ("1", "true", "yes", "sim")


def _time_id() -> str | None:
    return (os.environ.get("MCP_PROVA_TIME_ID") or "").strip() or None


# Caminho onde o MCP é montado no cérebro. O consultor cola a URL completa
# (ex.: https://api.batuta.team/mcp-prova/) no custom connector do claude.ai. Para
# obscurecer, dá para setar um sufixo aleatório via env (ex.: /mcp-prova-a1b2c3).
PATH = os.environ.get("MCP_PROVA_PATH", "/mcp-prova").rstrip("/") or "/mcp-prova"


# O servidor MCP. Streamable HTTP em modo STATELESS + JSON (o mais simples de montar
# num app existente; cada chamada é independente). `streamable_http_path="/"` faz o
# endpoint ficar na raiz do mount (a URL fica limpa: {PATH}/).
mcp = FastMCP(
    "Batuta — prova (criação de agentes)",
    instructions=(
        "Ferramentas para criar e ajustar AGENTES de um time de teste do Batuta. "
        "Use `descrever_time` e `listar_agentes` para ver o contexto antes de criar "
        "ou ajustar. Tudo opera só no time de teste configurado."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    # A proteção anti-DNS-rebinding do SDK valida o cabeçalho Host contra uma lista
    # (vazia por padrão → recusa TUDO com 421). Ela existe para blindar servidores
    # LOCAIS de navegadores maliciosos; o nosso é remoto e server-to-server
    # (claude.ai → api.batuta.team, atrás do Cloudflare/Railway), então a
    # desligamos nesta PROVA. A versão real (com OAuth) volta a travar por host.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


# ───────────────────────── Helpers (síncronos, DB) ─────────────────────────

def _abrir():
    return CriadorDeSessao()


def _time_teste(sessao) -> Time | None:
    tid = _time_id()
    if not tid:
        return None
    try:
        return sessao.get(Time, uuid.UUID(tid))
    except (ValueError, TypeError):
        return None


def _descrever_time_sync() -> str:
    sessao = _abrir()
    try:
        time = _time_teste(sessao)
        if time is None:
            return "Time de teste não configurado (falta MCP_PROVA_TIME_ID válido no servidor)."
        n = sessao.scalar(select(func.count()).select_from(Agente).where(Agente.time_id == time.id))
        return (
            f"Time de teste: '{time.nome}' (id {time.id}) — {n} agente(s). "
            f"Organização {time.organizacao_id}. Toda criação/ajuste desta conexão fica neste time."
        )
    finally:
        sessao.close()


def _listar_agentes_sync() -> str:
    sessao = _abrir()
    try:
        time = _time_teste(sessao)
        if time is None:
            return "Time de teste não configurado (falta MCP_PROVA_TIME_ID válido no servidor)."
        agentes = sessao.scalars(
            select(Agente).where(Agente.time_id == time.id).order_by(Agente.criado_em)
        ).all()
        if not agentes:
            return f"O time '{time.nome}' ainda não tem agentes. Crie um com `criar_agente`."
        linhas = [
            f"- {a.nome} ({a.papel}) — id {a.id}, modelo {a.modelo_ia or 'padrão'}"
            for a in agentes
        ]
        return f"Agentes do time '{time.nome}':\n" + "\n".join(linhas)
    finally:
        sessao.close()


def _criar_agente_sync(nome: str, instrucoes: str | None, papel: str) -> str:
    nome = (nome or "").strip()
    if not nome:
        return "Dê um nome ao agente."
    sessao = _abrir()
    try:
        time = _time_teste(sessao)
        if time is None:
            return "Time de teste não configurado (falta MCP_PROVA_TIME_ID válido no servidor)."
        try:
            agente = servicos.adicionar_agente(
                sessao, time, nome=nome, papel=(papel or "agente"),
                agent_md=(instrucoes or None),
            )
        except servicos.ConflitoDominio as e:
            return f"Não deu para criar: {e}"
        sessao.commit()
        return (
            f"Agente '{agente.nome}' criado no time '{time.nome}' "
            f"(id {agente.id}, papel {agente.papel})."
        )
    finally:
        sessao.close()


def _ajustar_agente_sync(agente_id: str, nome: str | None, instrucoes: str | None) -> str:
    sessao = _abrir()
    try:
        time = _time_teste(sessao)
        if time is None:
            return "Time de teste não configurado (falta MCP_PROVA_TIME_ID válido no servidor)."
        try:
            aid = uuid.UUID(str(agente_id))
        except (ValueError, TypeError):
            return f"Id de agente inválido: {agente_id}."
        agente = sessao.get(Agente, aid)
        # Trava de escopo: a prova só mexe em agente DO time de teste.
        if agente is None or agente.time_id != time.id:
            return "Esse agente não existe no time de teste (a prova só ajusta agentes do time de teste)."
        campos: dict = {}
        if nome and nome.strip():
            campos["nome"] = nome.strip()
        if instrucoes and instrucoes.strip():
            campos["agent_md"] = instrucoes
        if not campos:
            return "Nada para ajustar — passe um novo nome e/ou novas instruções."
        try:
            servicos.editar_agente(sessao, agente, **campos)
        except servicos.ConflitoDominio as e:
            return f"Não deu para ajustar: {e}"
        sessao.commit()
        return f"Agente '{agente.nome}' ajustado (id {agente.id})."
    finally:
        sessao.close()


# ───────────────────────────── Ferramentas MCP ─────────────────────────────
# São async e delegam o trabalho de banco (SQLAlchemy síncrono) a uma thread, para
# não bloquear o loop do servidor. O docstring vira a descrição que o Claude lê.

@mcp.tool()
async def descrever_time() -> str:
    """Mostra o time de teste do Batuta em que esta conexão opera (nome, id e quantos
    agentes tem). Use antes de criar ou ajustar, para saber onde está mexendo."""
    return await anyio.to_thread.run_sync(_descrever_time_sync)


@mcp.tool()
async def listar_agentes() -> str:
    """Lista os agentes do time de teste (nome, papel, id e modelo de IA de cada um)."""
    return await anyio.to_thread.run_sync(_listar_agentes_sync)


@mcp.tool()
async def criar_agente(nome: str, instrucoes: str | None = None, papel: str = "agente") -> str:
    """Cria um novo agente no time de teste do Batuta.

    - nome: como o agente se chama.
    - instrucoes: o que o agente é e faz (vira o documento principal do agente).
    - papel: 'agente' (padrão) ou 'lider' (só pode haver um líder por time).
    """
    return await anyio.to_thread.run_sync(_criar_agente_sync, nome, instrucoes, papel)


@mcp.tool()
async def ajustar_agente(
    agente_id: str, nome: str | None = None, instrucoes: str | None = None
) -> str:
    """Ajusta um agente existente do time de teste (renomeia e/ou reescreve as
    instruções). Passe o `agente_id` que aparece em `listar_agentes`."""
    return await anyio.to_thread.run_sync(_ajustar_agente_sync, agente_id, nome, instrucoes)


# ─────────────────────── Montagem no cérebro (main.py) ───────────────────────

_app = None


def app():
    """O sub-app ASGI (Streamable HTTP) para montar no FastAPI do cérebro. Construído
    uma vez; reusa o mesmo `session_manager` que o `ciclo()` roda no lifespan."""
    global _app
    if _app is None:
        _app = mcp.streamable_http_app()
    return _app


@contextlib.asynccontextmanager
async def ciclo():
    """Roda o gerenciador de sessão do Streamable HTTP durante a vida do processo.
    Precisa entrar no lifespan do cérebro (o sub-app montado NÃO tem o próprio
    lifespan executado pelo FastAPI — é a armadilha conhecida do SDK #1367)."""
    app()  # garante que o app e o session_manager existam
    async with mcp.session_manager.run():
        yield
