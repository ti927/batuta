"""Cache de prompt da Anthropic para TODA a conversa com o modelo — não só o prompt de
sistema (2026-10-08).

Por que existe. Até aqui só o prompt de sistema era marcado. Mas a cada ida e volta do
laço de ferramentas o agente reenvia o HISTÓRICO inteiro do turno (mensagens + resultados
de ferramenta, que costumam ser o grosso) — e esse histórico ia a preço cheio. A medição
de produção (30 dias até 08/10) mostrou só ~27% da entrada vinda do cache.

O cache da Anthropic é um casamento de PREFIXO: um ponto de cache grava "tudo até aqui";
o pedido seguinte que começar igual relê a ~10% do preço. Esta peça põe os 4 pontos que a
API permite, cada um num limite de estabilidade:

1. **Prompt de sistema** — cobre também as ferramentas (vêm antes dele na ordem da API).
2. **Penúltima fala humana** — RELÊ o ponto que o turno anterior gravou na fala dele.
3. **Última fala humana** — GRAVA o ponto que o próximo turno vai reler.
4. **Automático (topo do pedido)** — anda junto com o laço de ferramentas DENTRO do turno.

Os pontos 2–3 existem porque o histórico de um turno para o outro NÃO é byte-idêntico até
o fim: a IA criadora guarda os resultados de ferramenta truncados, e o contexto volátil vai
depois da fala. O que se repete com certeza é tudo ATÉ a fala humana — então o ponto fica
nela, e não no fim.

Contexto volátil (a foto do time da criadora, que muda a cada edição): vai numa mensagem
humana SEPARADA, logo depois da fala, marcada com `CONTEXTO_VOLATIL`. Ela nunca recebe
ponto e nunca entra no histórico salvo — assim a fala que a precede fica idêntica no
próximo turno.

Só na Anthropic (`ChatAnthropic`); em OpenAI/Google a peça não faz nada (lá o cache é
automático e `cache_control` quebraria). A marcação vale só para o PEDIDO — o checkpointer
e o histórico salvo não a recebem."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# Um só valor, usado em todos os pontos: a API recusa (400) um ponto explícito no último
# bloco com TTL diferente do automático, e exige TTL longo antes de curto.
PONTO_DE_CACHE = {"type": "ephemeral", "ttl": "5m"}

# Marca (em `additional_kwargs`, que não vai à API) da mensagem de contexto volátil.
CONTEXTO_VOLATIL = "batuta_contexto_volatil"


def mensagem_de_contexto_volatil(texto: str) -> HumanMessage:
    """A mensagem que leva o contexto que muda a cada turno, depois da fala humana."""
    return HumanMessage(content=texto, additional_kwargs={CONTEXTO_VOLATIL: True})


def _sem_ponto(bloco):
    if isinstance(bloco, dict) and "cache_control" in bloco:
        return {k: v for k, v in bloco.items() if k != "cache_control"}
    return bloco


def _marcar_ultimo_bloco(conteudo) -> list:
    """O conteúdo como lista de blocos, com o ponto SÓ no último bloco de texto (e
    nenhum outro ponto sobrando — o teto da API é 4 por pedido)."""
    if isinstance(conteudo, str):
        return [{"type": "text", "text": conteudo, "cache_control": PONTO_DE_CACHE}]
    blocos = [_sem_ponto(b) for b in conteudo]
    for i in range(len(blocos) - 1, -1, -1):
        b = blocos[i]
        if isinstance(b, str):
            blocos[i] = {"type": "text", "text": b, "cache_control": PONTO_DE_CACHE}
            break
        if isinstance(b, dict) and b.get("type") == "text":
            blocos[i] = {**b, "cache_control": PONTO_DE_CACHE}
            break
    return blocos


def _e_volatil(m) -> bool:
    return bool((getattr(m, "additional_kwargs", None) or {}).get(CONTEXTO_VOLATIL))


def marcar_pedido(request: ModelRequest) -> ModelRequest:
    """Devolve o pedido com os 4 pontos de cache (cópias — nada do estado é mutado)."""
    sobrescrever: dict = {
        "model_settings": {**request.model_settings, "cache_control": PONTO_DE_CACHE}
    }
    if request.system_message is not None:
        sobrescrever["system_message"] = SystemMessage(
            content=_marcar_ultimo_bloco(request.system_message.content)
        )
    mensagens = list(request.messages)
    marcadas = 0
    for i in range(len(mensagens) - 1, -1, -1):
        m = mensagens[i]
        if isinstance(m, HumanMessage) and not _e_volatil(m) and m.content:
            mensagens[i] = m.model_copy(update={"content": _marcar_ultimo_bloco(m.content)})
            marcadas += 1
            if marcadas == 2:
                break
    sobrescrever["messages"] = mensagens
    return request.override(**sobrescrever)


class CacheDePrompt(AgentMiddleware):
    """Middleware do `create_agent` que aplica `marcar_pedido` só na Anthropic."""

    def wrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ):
        if not isinstance(request.model, ChatAnthropic):
            return handler(request)
        return handler(marcar_pedido(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ):
        if not isinstance(request.model, ChatAnthropic):
            return await handler(request)
        return await handler(marcar_pedido(request))


def tokens_de_cache(usage_metadata: dict | None) -> tuple[int, int]:
    """(lidos, gravados) do cache numa resposta, pelo `usage_metadata` do LangChain.

    A gravação NÃO pode ser lida só de `cache_creation`: quando a API detalha a gravação
    por TTL, o langchain-anthropic zera `cache_creation` e põe o número em
    `ephemeral_5m_input_tokens`/`ephemeral_1h_input_tokens`. Lendo só a chave antiga, toda
    gravação de produção saiu 0 até 2026-10-08 (o painel cobrava a 1× o que custa 1,25×)."""
    det = (usage_metadata or {}).get("input_token_details") or {}
    lidos = det.get("cache_read") or 0
    gravados = (det.get("ephemeral_5m_input_tokens") or 0) + (
        det.get("ephemeral_1h_input_tokens") or 0
    )
    return lidos, gravados or (det.get("cache_creation") or 0)
