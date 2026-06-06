"""Acesso à LLM para a orquestração.

As chaves de IA são resolvidas na fronteira da execução (Fase 7.3): a chave da
Organização, ou a chave-mãe da consultoria, ou — para a Anthropic — a
`ANTHROPIC_API_KEY` legada do ambiente (retrocompatibilidade). A Fase 7-A tornou
o motor MULTI-PROVEDOR: cada agente pode rodar em Anthropic, OpenAI ou Google
(PRODUTO §11). A fronteira resolve um MAPA `{provedor: chave}` e o fixa no
contexto com `usar_chaves(...)`; `construir_modelo`, lá no fundo, descobre o
provedor do modelo e constrói o cliente certo com a chave certa. O núcleo do
grafo (cadeia/agente) não muda — só muda de onde a chave vem. A chave nunca vem
do código (CLAUDE.md §8).
"""

import contextvars
import os
from collections.abc import Iterator
from contextlib import contextmanager

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage

from orquestracao.modelos_ia import (
    PROVEDOR_ANTHROPIC,
    PROVEDOR_GOOGLE,
    PROVEDOR_OPENAI,
    provedor_do_modelo,
)

# Modelo padrão quando o agente não escolheu um. Haiku: barato para o trivial.
# Também é o modelo do passo de roteamento da cadeia (sempre Anthropic).
MODELO_PADRAO = "claude-haiku-4-5"
# Teto de tokens de SAÍDA por resposta. Folga para saídas estruturadas e longas
# (tabelas, vários candidatos, artigos) — 2048 cortava saídas ricas no meio.
MAX_TOKENS = 8192

# Mapa {provedor: chave} resolvido para a execução em curso (Fases 7.3/7-A). É um
# contextvar para atravessar o stack do motor sem mudar a assinatura de nenhuma
# função do grafo: a fronteira (disparo/retomada/agente isolado) põe o mapa aqui
# com `usar_chaves`, e `construir_modelo`, lá no fundo, pega a chave do provedor
# do modelo. Provedor ausente no mapa → sem chave de cofre (a Anthropic cai na
# ANTHROPIC_API_KEY do ambiente; os demais falham de forma clara).
_chaves_ia: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
    "chaves_ia", default={}
)


@contextmanager
def usar_chaves(mapa: dict[str, str] | None) -> Iterator[None]:
    """Fixa o mapa {provedor: chave} durante o bloco. Sai sempre limpando o
    contexto (try/finally), para que um trabalhador reutilizado não vaze as
    chaves de uma execução para a próxima."""
    token = _chaves_ia.set(mapa or {})
    try:
        yield
    finally:
        _chaves_ia.reset(token)


def construir_modelo(
    modelo_ia: str | None = None, temperatura: float = 0.0
) -> BaseChatModel:
    """Cria o cliente de chat para o modelo dado, do provedor certo, com a chave
    resolvida no contexto (`usar_chaves`). A Anthropic cai na ANTHROPIC_API_KEY do
    ambiente quando não há chave de cofre; OpenAI e Google exigem a chave no cofre
    (sem fallback de ambiente) e falham de forma clara se faltar."""
    modelo = modelo_ia or MODELO_PADRAO
    provedor = provedor_do_modelo(modelo)
    chave = _chaves_ia.get().get(provedor)

    if provedor == PROVEDOR_ANTHROPIC:
        parametros: dict = {
            "model": modelo,
            "max_tokens": MAX_TOKENS,
            "temperature": temperatura,
        }
        if chave:
            parametros["api_key"] = chave
        elif not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "Nenhuma chave de IA Anthropic disponível: nem chave de projeto/"
                "consultoria no cofre, nem ANTHROPIC_API_KEY no ambiente."
            )
        return ChatAnthropic(**parametros)

    if provedor == PROVEDOR_OPENAI:
        if not chave:
            raise RuntimeError(
                f"O modelo '{modelo}' usa OpenAI, mas não há chave OpenAI no cofre "
                "desta organização nem da consultoria."
            )
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=modelo, api_key=chave, max_tokens=MAX_TOKENS, temperature=temperatura
        )

    if provedor == PROVEDOR_GOOGLE:
        if not chave:
            raise RuntimeError(
                f"O modelo '{modelo}' usa Google, mas não há chave Google no cofre "
                "desta organização nem da consultoria."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=modelo,
            api_key=chave,
            max_output_tokens=MAX_TOKENS,
            temperature=temperatura,
        )

    raise ValueError(f"Provedor de IA não suportado: {provedor}")


def texto_da_resposta(resposta: AIMessage) -> str:
    """Extrai o texto de uma resposta, seja ela string ou lista de blocos.
    Robusto entre versões do langchain."""
    conteudo = resposta.content
    if isinstance(conteudo, str):
        return conteudo
    partes: list[str] = []
    for bloco in conteudo:
        if isinstance(bloco, str):
            partes.append(bloco)
        elif isinstance(bloco, dict) and bloco.get("type") == "text":
            partes.append(bloco.get("text", ""))
    return "".join(partes)


def chamar(texto: str, modelo_ia: str | None = None) -> str:
    """Chamada simples: manda um texto, devolve a resposta em texto.
    É a peça mínima da Fase 4; a orquestração completa cresce a partir daqui."""
    modelo = construir_modelo(modelo_ia)
    resposta = modelo.invoke(texto)
    return texto_da_resposta(resposta)
