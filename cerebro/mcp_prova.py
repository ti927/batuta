"""Prova de conceito — Batuta como servidor MCP (Model Context Protocol).

Expõe um punhado de ferramentas de CRIAÇÃO/AJUSTE do Batuta por um MCP remoto
(Streamable HTTP), para o consultor conectar do PRÓPRIO claude.ai (custom connector)
e montar/ajustar agentes conversando com o Claude — rodando na ASSINATURA dele, não
na API do Batuta. É o padrão permitido pela Anthropic (o app do usuário aciona a
ferramenta; o Batuta não roteia assinatura de ninguém).

RODA COMO SERVIÇO PRÓPRIO (na RAIZ de um domínio), não montado no cérebro: o
claude.ai exige OAuth no connector, e as URLs de descoberta do OAuth (`.well-known`)
que o SDK gera ficam na raiz do domínio — montar sob um subcaminho quebraria a
descoberta. Sobe com: `uvicorn mcp_prova:asgi_app --host 0.0.0.0 --port $PORT`.

ESCOPO DELIBERADAMENTE MÍNIMO E DESCARTÁVEL:
- Tudo escopado a UM time de teste fixo (`MCP_PROVA_TIME_ID`) — o raio de dano é um
  time descartável.
- Login OAuth AUTO-APROVADO (ver `mcp_auth.py`): cumpre o ritual que o claude.ai
  exige, sem senha/usuário real. Segurança real (login do Batuta + escopo por
  consultor) é a PRÓXIMA fatia.

Reuso: as ferramentas NÃO usam os tools da criadora (acoplados a um turno/conversa);
usam a camada de serviço por baixo — `criacao.servicos` (a MESMA porta validada por
onde a IA e as rotas REST escrevem no time real).
"""

import os
import uuid

import anyio
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import func, select

import mcp_auth
from criacao import servicos
from modelos import Agente, Time
from sessao import CriadorDeSessao


# ───────────────────────────── Configuração ─────────────────────────────

# URL pública (raiz) DESTE serviço MCP — precisa bater com o domínio real, senão a
# descoberta do OAuth não fecha. Ordem: MCP_PROVA_PUBLIC_URL (override manual) →
# RAILWAY_PUBLIC_DOMAIN (o Railway injeta sozinho no serviço, então nem precisa
# setar a URL à mão) → localhost (dev). O caminho do MCP é `/mcp`.
_railway = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
BASE_URL = (
    os.environ.get("MCP_PROVA_PUBLIC_URL")
    or (f"https://{_railway}" if _railway else "http://localhost:8000")
).rstrip("/")
CAMINHO_MCP = "/mcp"


def _time_id() -> str | None:
    return (os.environ.get("MCP_PROVA_TIME_ID") or "").strip() or None


mcp = FastMCP(
    "Batuta — prova (criação de agentes)",
    instructions=(
        "Ferramentas para criar e ajustar AGENTES de um time de teste do Batuta. "
        "Use `descrever_time` e `listar_agentes` para ver o contexto antes de criar "
        "ou ajustar. Tudo opera só no time de teste configurado."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path=CAMINHO_MCP,
    # Login OAuth auto-aprovado (o claude.ai exige OAuth no connector). O SDK monta
    # /authorize, /token, /register e os metadados; o provedor implementa a lógica.
    auth_server_provider=mcp_auth.ProvedorAutoAprovado(),
    auth=AuthSettings(
        issuer_url=BASE_URL,
        resource_server_url=f"{BASE_URL}{CAMINHO_MCP}",
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[mcp_auth.ESCOPO],
            default_scopes=[mcp_auth.ESCOPO],
        ),
        required_scopes=[],  # basta um token válido (login auto-aprovado)
    ),
    # A proteção anti-DNS-rebinding valida o Host contra uma lista (vazia = recusa
    # tudo). É para blindar servidores LOCAIS de navegadores; o nosso é remoto e
    # server-to-server (claude.ai → Railway/Cloudflare), então desligamos na PROVA.
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


# O app ASGI standalone (com o próprio lifespan que roda o session manager).
asgi_app = mcp.streamable_http_app()


if __name__ == "__main__":
    # Ponto de entrada para o Railway: `uv run python mcp_prova.py`. Lê a porta do
    # ambiente (PORT, que o Railway injeta) em vez de depender de expandir `$PORT` no
    # comando de start — o builder passa `$PORT` literal e o uvicorn recusa.
    import uvicorn

    uvicorn.run(asgi_app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

