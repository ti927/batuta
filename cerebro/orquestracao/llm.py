"""Acesso à LLM para a orquestração.

A chave de IA é resolvida na fronteira da execução (Fase 7.3): a chave da
Organização, ou a chave-mãe da consultoria, ou — quando nenhuma está cadastrada —
a `ANTHROPIC_API_KEY` legada do ambiente (retrocompatibilidade). A chave resolvida
é colocada no contexto por `usar_chave(...)`; `construir_modelo` a lê daqui. O
núcleo do grafo (cadeia/agente) não muda: só muda DE ONDE a chave vem. A chave
nunca vem do código (CLAUDE.md §8). Cada agente pode usar um modelo diferente
(PRODUTO.md §11); quando não define, usa-se o padrão.
"""

import contextvars
import os
from collections.abc import Iterator
from contextlib import contextmanager

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage

# Modelo padrão quando o agente não escolheu um. Haiku: barato para o trivial.
MODELO_PADRAO = "claude-haiku-4-5"
# Teto de tokens de SAÍDA por resposta. Folga para saídas estruturadas e longas
# (tabelas, vários candidatos, artigos) — 2048 cortava saídas ricas no meio.
MAX_TOKENS = 8192

# Chave de IA resolvida para a execução em curso (Fase 7.3). É um contextvar para
# atravessar o stack do motor sem mudar a assinatura de nenhuma função do grafo:
# a fronteira (disparo/retomada/agente isolado) põe a chave aqui com `usar_chave`,
# e `construir_modelo`, lá no fundo, a lê. None = nenhuma chave de cofre resolvida
# → cai na ANTHROPIC_API_KEY do ambiente (legado).
_chave_ia: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "chave_ia", default=None
)


@contextmanager
def usar_chave(chave: str | None) -> Iterator[None]:
    """Fixa a chave de IA resolvida durante o bloco. Sai sempre limpando o
    contexto (try/finally), para que um trabalhador reutilizado não vaze a chave
    de uma execução para a próxima."""
    token = _chave_ia.set(chave)
    try:
        yield
    finally:
        _chave_ia.reset(token)


def construir_modelo(
    modelo_ia: str | None = None, temperatura: float = 0.0
) -> ChatAnthropic:
    """Cria o cliente de chat para o modelo dado. Usa a chave resolvida no
    contexto (`usar_chave`); na ausência dela, cai na ANTHROPIC_API_KEY do
    ambiente (legado). Sem nenhuma das duas, falha de forma clara."""
    chave = _chave_ia.get()
    parametros: dict = {
        "model": modelo_ia or MODELO_PADRAO,
        "max_tokens": MAX_TOKENS,
        "temperature": temperatura,
    }
    if chave:
        parametros["api_key"] = chave
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "Nenhuma chave de IA disponível: nem chave de projeto/consultoria no "
            "cofre, nem ANTHROPIC_API_KEY no ambiente do cérebro."
        )
    return ChatAnthropic(**parametros)


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
