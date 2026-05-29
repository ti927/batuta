"""Acesso à LLM para a orquestração.

A chave vem sempre do ambiente (ANTHROPIC_API_KEY), carregada pelo `db`/dotenv —
nunca do código (CLAUDE.md §8). Cada agente pode usar um modelo diferente
(PRODUTO.md §11); quando não define, usa-se o padrão.
"""

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage

# Modelo padrão quando o agente não escolheu um. Haiku: barato para o trivial.
MODELO_PADRAO = "claude-haiku-4-5"
MAX_TOKENS = 2048


def construir_modelo(
    modelo_ia: str | None = None, temperatura: float = 0.0
) -> ChatAnthropic:
    """Cria o cliente de chat para o modelo dado, lendo a chave do ambiente."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY não está definida no ambiente do cérebro."
        )
    return ChatAnthropic(
        model=modelo_ia or MODELO_PADRAO,
        max_tokens=MAX_TOKENS,
        temperature=temperatura,
    )


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
