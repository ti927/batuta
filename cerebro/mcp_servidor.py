"""Batuta-MCP profissional — servidor MCP que o claude.ai do consultor aciona.

Diferente da prova (`mcp_prova.py`, descartável, login auto-aprovado, um time fixo),
este servidor tem **login real por consultor** (`mcp_login`) e **escopo por
organização/papel** (`mcp_escopo`): cada ferramenta descobre QUEM está falando pelo
token e só enxerga/mexe no que aquele consultor pode, pelos MESMOS guardas das rotas
REST. A IA roda na assinatura do consultor (claude.ai); o Batuta só oferece as
ferramentas.

Fatia 0 (esta): a FUNDAÇÃO de login + escopo, provada por um punhado de ferramentas de
LEITURA escopadas (`listar_organizacoes`, `listar_times`, `descrever_time`). As demais
ferramentas (leitura completa, criação, diagnóstico) entram nas fatias seguintes.

Roda como serviço próprio na RAIZ de um domínio (as `.well-known` do OAuth ficam na
raiz). Sobe com: `uv run python mcp_servidor.py`.
"""

import os
import uuid

import anyio
from fastapi import HTTPException
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import mcp_escopo
import mcp_login
from mcp_escopo import SemAcesso
from sessao import CriadorDeSessao

# ───────────────────────────── Servidor ─────────────────────────────

mcp = FastMCP(
    "Batuta",
    instructions=(
        "Ferramentas para operar o Batuta — a plataforma onde se montam TIMES de agentes "
        "de IA que executam tarefas de uma empresa. Modelo mental: uma ORGANIZAÇÃO tem "
        "TIMES; um time tem AGENTES (um deles é o líder), INSTRUMENTOS (as ferramentas do "
        "cinto de cada agente) e AUTOMAÇÕES (o fluxo que encadeia os agentes). Você opera "
        "em nome do consultor autenticado e só enxerga as organizações/times dele. "
        "Comece sempre LENDO o contexto (`listar_organizacoes`, `listar_times`, "
        "`descrever_time`) antes de criar ou ajustar qualquer coisa."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path=mcp_login.CAMINHO_MCP,
    # Login OAuth REAL por consultor (Supabase + escopo por org/papel). O SDK monta
    # /authorize, /token, /register e os metadados; o provedor implementa a lógica e a
    # telinha de login.
    auth_server_provider=mcp_login.ProvedorLoginBatuta(),
    auth=AuthSettings(
        issuer_url=mcp_login.BASE_URL,
        resource_server_url=f"{mcp_login.BASE_URL}{mcp_login.CAMINHO_MCP}",
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[mcp_login.ESCOPO],
            default_scopes=[mcp_login.ESCOPO],
        ),
        required_scopes=[],  # basta um token válido; a autorização real é por org/papel
    ),
    # Proteção anti-DNS-rebinding é para blindar servidores LOCAIS de navegadores; o
    # nosso é remoto e server-to-server (claude.ai → Railway/Cloudflare).
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

# Telinha de login (rotas públicas /login GET+POST).
mcp_login.registrar_rotas_login(mcp)


# ───────────────────── Helpers (síncronos, rodam em thread) ─────────────────────
# Recebem o `sub` (id do consultor) porque o contextvar do token não atravessa a
# thread. Traduzem os guardas de acesso (que levantam HTTPException 403/404) em texto.

def _traduzir_acesso(e: HTTPException) -> str:
    if e.status_code == 404:
        return "Não encontrei isso entre as suas organizações/times (ou ele não existe)."
    if e.status_code == 403:
        return f"Você não tem permissão para isso. {e.detail}"
    return str(e.detail)


def _listar_organizacoes_sync(sub: str | None) -> str:
    sessao = CriadorDeSessao()
    try:
        usuario = mcp_escopo.usuario_do_sub(sessao, sub)
        orgs = mcp_escopo.organizacoes_do_usuario(sessao, usuario)
        if not orgs:
            return "Você ainda não participa de nenhuma organização no Batuta."
        linhas = [f"- {org.nome} (id {org.id}) — seu papel: {papel}" for org, papel in orgs]
        return "Suas organizações:\n" + "\n".join(linhas)
    except SemAcesso as e:
        return str(e)
    finally:
        sessao.close()


def _listar_times_sync(sub: str | None, organizacao_id: str | None) -> str:
    sessao = CriadorDeSessao()
    try:
        usuario = mcp_escopo.usuario_do_sub(sessao, sub)
        org_id = None
        if organizacao_id:
            try:
                org_id = uuid.UUID(str(organizacao_id))
            except (ValueError, TypeError):
                return f"Id de organização inválido: {organizacao_id}."
            try:
                mcp_escopo.organizacao_acessivel(sessao, usuario, org_id)
            except HTTPException as e:
                return _traduzir_acesso(e)
        times = mcp_escopo.times_do_usuario(sessao, usuario, org_id)
        if not times:
            return "Nenhum time encontrado no seu escopo."
        linhas = [f"- {t.nome} (id {t.id}) — organização {t.organizacao_id}" for t in times]
        return "Times que você pode ver:\n" + "\n".join(linhas)
    except SemAcesso as e:
        return str(e)
    finally:
        sessao.close()


def _descrever_time_sync(sub: str | None, time_id: str) -> str:
    sessao = CriadorDeSessao()
    try:
        usuario = mcp_escopo.usuario_do_sub(sessao, sub)
        try:
            tid = uuid.UUID(str(time_id))
        except (ValueError, TypeError):
            return f"Id de time inválido: {time_id}."
        try:
            time = mcp_escopo.time_acessivel(sessao, usuario, tid)
        except HTTPException as e:
            return _traduzir_acesso(e)
        n = mcp_escopo.contar_agentes(sessao, time.id)
        return (
            f"Time '{time.nome}' (id {time.id}) — {n} agente(s). "
            f"Organização {time.organizacao_id}."
            + (f" {time.descricao}" if time.descricao else "")
        )
    except SemAcesso as e:
        return str(e)
    finally:
        sessao.close()


# ───────────────────────────── Ferramentas MCP ─────────────────────────────
# São async: leem a identidade do token (contexto async) e delegam o banco a uma thread.

@mcp.tool()
async def listar_organizacoes() -> str:
    """Lista as organizações do Batuta em que você (o consultor autenticado) participa,
    com o seu papel em cada uma. Comece por aqui para saber onde pode trabalhar."""
    return await anyio.to_thread.run_sync(_listar_organizacoes_sync, mcp_escopo.sub_do_token())


@mcp.tool()
async def listar_times(organizacao_id: str | None = None) -> str:
    """Lista os times que você pode ver — de todas as suas organizações ou, se informar
    `organizacao_id`, só daquela organização."""
    return await anyio.to_thread.run_sync(
        _listar_times_sync, mcp_escopo.sub_do_token(), organizacao_id
    )


@mcp.tool()
async def descrever_time(time_id: str) -> str:
    """Mostra um time seu (nome, id, organização e quantos agentes tem). Use os ids que
    aparecem em `listar_times`."""
    return await anyio.to_thread.run_sync(
        _descrever_time_sync, mcp_escopo.sub_do_token(), time_id
    )


# O app ASGI standalone (com o próprio lifespan que roda o session manager).
asgi_app = mcp.streamable_http_app()


if __name__ == "__main__":
    # Ponto de entrada para o Railway: `uv run python mcp_servidor.py`.
    import uvicorn

    mcp_login.preparar()  # garante a tabela de clientes OAuth (idempotente)
    uvicorn.run(asgi_app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
