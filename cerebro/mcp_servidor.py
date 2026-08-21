"""Batuta-MCP profissional — servidor MCP que o claude.ai do consultor aciona.

Diferente da prova (`mcp_prova.py`, descartável, login auto-aprovado, um time fixo),
este servidor tem **login real por consultor** (`mcp_login`) e **escopo por
organização/papel** (`mcp_escopo`): cada ferramenta descobre QUEM está falando pelo
token e só enxerga/mexe no que aquele consultor pode, pelos MESMOS guardas das rotas
REST. A IA roda na assinatura do consultor (claude.ai); o Batuta só oferece as
ferramentas.

Este módulo é a camada FINA de registro: monta o `FastMCP`, liga a telinha de login e
declara as tools (async) que leem o `sub` do token e delegam a lógica para
`mcp_ferramentas` numa thread. Fatias entregues:
- Fatia 0: fundação de login + escopo.
- Fatia 1: LEITURA completa + diagnóstico (agentes, automações, execuções, conversas,
  memórias, custo, catálogo de instrumentos, Central de Conhecimento).

Roda como serviço próprio na RAIZ de um domínio (as `.well-known` do OAuth ficam na
raiz). Sobe com: `uv run python mcp_servidor.py`.
"""

import os

import anyio
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import mcp_escopo
import mcp_ferramentas
import mcp_login

# ───────────────────────────── Servidor ─────────────────────────────

mcp = FastMCP(
    "Batuta",
    instructions=(
        "Ferramentas para operar o Batuta — a plataforma onde se montam TIMES de agentes "
        "de IA que executam tarefas de uma empresa. Modelo mental: uma ORGANIZAÇÃO tem "
        "TIMES; um time tem AGENTES (um deles é o líder), INSTRUMENTOS (as ferramentas do "
        "cinto de cada agente) e AUTOMAÇÕES (o fluxo que encadeia os agentes, disparado "
        "por um gatilho). Você opera em nome do consultor autenticado e só enxerga as "
        "organizações/times dele. Comece sempre LENDO o contexto (`listar_organizacoes`, "
        "`listar_times`, `descrever_time`, `listar_agentes`) antes de agir. Para investigar "
        "um problema, use `listar_execucoes` (com apenas_problemas) e `diagnosticar_execucao` "
        "— o diagnóstico traz avisos com ação sugerida. Em dúvida sobre COMO um recurso do "
        "Batuta funciona, consulte a Central com `consultar_conhecimento` em vez de adivinhar."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path=mcp_login.CAMINHO_MCP,
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
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

# Telinha de login (rotas públicas /login GET+POST).
mcp_login.registrar_rotas_login(mcp)


def _sub() -> str | None:
    return mcp_escopo.sub_do_token()


# ───────────────────────────── Ferramentas (Fatia 0 + 1) ─────────────────────────────
# Cada tool lê a identidade do token (contexto async) e delega o banco a uma thread.

@mcp.tool()
async def listar_organizacoes() -> str:
    """Lista as organizações do Batuta em que você (o consultor autenticado) participa,
    com o seu papel em cada uma. Comece por aqui para saber onde pode trabalhar."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_organizacoes, _sub())


@mcp.tool()
async def listar_times(organizacao_id: str | None = None) -> str:
    """Lista os times que você pode ver — de todas as suas organizações ou, se informar
    `organizacao_id`, só daquela organização."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_times, _sub(), organizacao_id)


@mcp.tool()
async def descrever_time(time_id: str) -> str:
    """Mostra um time seu (nome, id, organização e quantos agentes tem)."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.descrever_time, _sub(), time_id)


@mcp.tool()
async def listar_agentes(time_id: str) -> str:
    """Lista os agentes de um time seu (nome, papel, id, modelo de IA e se a memória está
    ligada). Use os ids em `ver_agente`."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_agentes, _sub(), time_id)


@mcp.tool()
async def ver_agente(agente_id: str) -> str:
    """Mostra os textos completos de um agente (os 4 markdowns: agent_md/skill_md/
    tools_md/soul_md), o modelo, se a memória está ligada e o cinto de instrumentos."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ver_agente, _sub(), agente_id)


@mcp.tool()
async def ver_memoria_agente(agente_id: str) -> str:
    """Mostra o que um agente aprendeu com o próprio trabalho (fichas de memória por
    assunto). Só leitura — para supervisionar e explicar ao consultor."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ver_memoria_agente, _sub(), agente_id)


@mcp.tool()
async def listar_automacoes(time_id: str) -> str:
    """Lista as automações de um time seu (nome, id, gatilho e se está ativa)."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_automacoes, _sub(), time_id)


@mcp.tool()
async def ver_automacao(automacao_id: str) -> str:
    """Mostra a cadeia completa (o fluxo/grafo de nós) de uma automação, com o gatilho e
    se está ativa."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ver_automacao, _sub(), automacao_id)


@mcp.tool()
async def listar_execucoes(
    time_id: str,
    automacao_id: str | None = None,
    apenas_problemas: bool = False,
    limite: int = 10,
) -> str:
    """Lista as execuções recentes de um time — para achar a que o consultor relata como
    problema. Filtre por automação e/ou só as com problema (`apenas_problemas=true`:
    falhou, parada esperando humano, presa ou na fila)."""
    return await anyio.to_thread.run_sync(
        mcp_ferramentas.listar_execucoes, _sub(), time_id, automacao_id, apenas_problemas, limite
    )


@mcp.tool()
async def diagnosticar_execucao(execucao_id: str) -> str:
    """Investiga UMA execução a fundo e devolve o diagnóstico: estado, linha do tempo dos
    passos e AVISOS (cada um com título, detalhe e ação sugerida). Use para explicar ao
    consultor por que uma execução falhou ou ficou parada e propor o próximo passo. Nunca
    expõe segredos (só diz se um canal 'tem token', nunca o valor)."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.diagnosticar_execucao, _sub(), execucao_id)


@mcp.tool()
async def listar_conversas(time_id: str, estado: str | None = None) -> str:
    """Lista as conversas de mensageria de um time (contato, canal, estado, nº de turnos).
    Filtro opcional por estado."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_conversas, _sub(), time_id, estado)


@mcp.tool()
async def ler_conversa(conversa_id: str) -> str:
    """Lê a thread completa de uma conversa de mensageria (as mensagens entre o contato e
    o agente/operador)."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ler_conversa, _sub(), conversa_id)


@mcp.tool()
async def ver_uso(time_id: str) -> str:
    """Mostra o custo de IA (US$) de um time — execuções + mensageria — com a quebra por
    categoria e os tokens. (O custo da IA criadora é por organização, não por time.)"""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ver_uso, _sub(), time_id)


@mcp.tool()
async def listar_tipos_instrumento() -> str:
    """Lista os tipos de instrumento disponíveis, com o que cada um faz, os campos de
    configuração (obrigatório/secreto) e se a ação é irreversível. Use para saber o que é
    possível montar e o que precisa de portão de aprovação."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_tipos_instrumento, _sub())


@mcp.tool()
async def consultar_conhecimento(topico: str) -> str:
    """Consulta a Central de Conhecimento do Batuta — o manual dos recursos (instrumentos,
    automações, gatilhos, portão de aprovação, chaves, credenciais, mensageria, memória do
    agente, etc.). Use quando não souber COMO um recurso funciona, em vez de adivinhar."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.consultar_conhecimento, _sub(), topico)


# O app ASGI standalone (com o próprio lifespan que roda o session manager).
asgi_app = mcp.streamable_http_app()


if __name__ == "__main__":
    # Ponto de entrada para o Railway: `uv run python mcp_servidor.py`.
    import uvicorn

    mcp_login.preparar()  # garante a tabela de clientes OAuth (idempotente)
    uvicorn.run(asgi_app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
