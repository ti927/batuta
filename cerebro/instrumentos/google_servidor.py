"""Chamada às ferramentas que rodam NO GOOGLE (busca do Google, leitura de link, leitura
de PDF) — a peça comum dos instrumentos de IA quando a IA escolhida é a do Google
(2026-10-02). Par da `anthropic_servidor` e da `openai_servidor`.

O que é igual para todos, aqui:

- a chave vem do pool da organização (contexto `usar_chaves`); o Google não tem chave
  de reserva no ambiente — sem chave no pool, falha com o caminho;
- TEMPO LIMITE em toda chamada (§12-A) e sinal de vida durante a espera longa;
- ERRO DEVOLVIDO COMO DADO: resposta bloqueada por segurança, sem texto, ou link que
  o Google não conseguiu abrir — sem tratar, o agente narraria sucesso;
- CONTA SEM CRÉDITO: o projeto do Google pode ser pré-pago e zerar (402) — recado de
  onde pôr crédito, em vez de um erro cru;
- MODELO DESLIGADO: o recado honesto do `llm.modelo_indisponivel`;
- CUSTO REAL: tokens (o raciocínio e o que as ferramentas leram entram no `usage`) +
  buscas, em `uso`.

Referência: ai.google.dev/gemini-api/docs (Google Search grounding, URL context,
document understanding, pricing, deprecations).
"""

import httpx
from google import genai
from google.genai import errors, types

import precos
from instrumentos.anthropic_servidor import _com_batimento
from instrumentos.base import FalhaInstrumento
from orquestracao import ciclo_modelos
from orquestracao.llm import chaves_atuais, modelo_indisponivel

TIMEOUT_S = 180.0
MAX_TENTATIVAS = 3

# US$ por busca do Google nos Gemini 3.x: 5.000 grátis por mês (somadas entre todos os
# modelos 3.x do projeto), depois US$ 14 por mil. O Batuta não sabe quanto da franquia
# já foi usado: conta o preço cheio (o custo mostrado é o teto, não menos).
PRECO_BUSCA_USD = 0.014

# Padrões: Flash-Lite (o mais barato) para buscar e ler página; Flash 3.8 para
# documento, onde a precisão pesa.
MODELO_PADRAO_WEB = "gemini-3.5-flash-lite"
MODELO_PADRAO = "gemini-3.8-flash"


def modelos_disponiveis() -> list[str]:
    """Os modelos do Google que servem a estes instrumentos (do registro de validade)."""
    return ciclo_modelos.modelos(ciclo_modelos.TEXTO, "google")


def _chave() -> str:
    chave = chaves_atuais().get("google")
    if not chave:
        raise FalhaInstrumento(
            "não há chave do Google: um admin precisa cadastrá-la em Organização › Chaves "
            "(ou escolha um modelo de outra IA neste instrumento).",
            retentavel=False, codigo="ia.sem_chave",
        )
    return chave


def cliente(timeout: float | None = None) -> genai.Client:
    return genai.Client(
        api_key=_chave(),
        http_options=types.HttpOptions(
            timeout=int((timeout or TIMEOUT_S) * 1000),
            retry_options=types.HttpRetryOptions(attempts=MAX_TENTATIVAS),
        ),
    )


def traduzir_excecao(e: Exception, modelo: str) -> FalhaInstrumento:
    recado = modelo_indisponivel(e, modelo)
    if recado:
        return FalhaInstrumento(recado, retentavel=False, codigo="ia.modelo_desligado")
    codigo = getattr(e, "code", None)
    texto = str(e)
    if codigo == 402 or "prepayment credits" in texto.lower():
        return FalhaInstrumento(
            "a conta do Google da empresa está sem crédito. Um admin precisa pôr crédito em "
            "ai.studio/projects (Billing) e tentar de novo.",
            retentavel=False, codigo="ia.sem_credito",
        )
    if codigo == 401 or "api key not valid" in texto.lower() or "API_KEY_INVALID" in texto:
        return FalhaInstrumento(
            "o Google recusou a chave cadastrada (revogada ou errada). Um admin precisa "
            "trocá-la em Organização › Chaves.", retentavel=False, codigo="ia.chave_recusada",
        )
    if codigo == 403:
        return FalhaInstrumento(
            f"a conta do Google da empresa não tem acesso a este recurso ou modelo "
            f"({modelo or 'pedido'}). Escolha outro modelo no instrumento.",
            retentavel=False, codigo="ia.recurso_desligado",
        )
    if codigo == 429 or isinstance(e, errors.ServerError):
        return FalhaInstrumento(
            "o Google não respondeu a tempo ou está sobrecarregado; tente de novo em instantes.",
            retentavel=True, codigo="ia.indisponivel",
        )
    if isinstance(e, errors.ClientError):
        return FalhaInstrumento(f"o Google recusou o pedido: {texto[:300]}", retentavel=False)
    return FalhaInstrumento(f"a chamada ao Google falhou: {texto[:300]}", retentavel=True)


def falha_inesperada(e: Exception) -> FalhaInstrumento:
    """Erro que não veio da API do Google: rede/tempo esgotado (vale tentar de novo) ou
    um pedido que o próprio SDK recusou antes de sair (não vale — diz o porquê)."""
    if isinstance(e, (httpx.TimeoutException, httpx.TransportError, TimeoutError, ConnectionError)):
        return FalhaInstrumento(
            f"o Google não respondeu a tempo ({type(e).__name__}); tente de novo em instantes.",
            retentavel=True, codigo="ia.indisponivel",
        )
    return FalhaInstrumento(f"a chamada ao Google falhou: {str(e)[:300]}", retentavel=False)


def chamar(
    *, modelo: str, sistema: str, conteudo: list, ferramentas: list[types.Tool],
    timeout: float | None = None, frase_espera: str | None = None,
) -> dict:
    """Uma chamada a `generate_content`. Devolve `{"texto", "resposta", "uso"}`: o texto
    final, a resposta crua (para fontes e metadados) e o uso real."""
    cli = cliente(timeout)
    config = types.GenerateContentConfig(system_instruction=sistema, tools=ferramentas or None)
    criar = lambda: cli.models.generate_content(  # noqa: E731
        model=modelo, contents=conteudo, config=config,
    )
    try:
        resposta = _com_batimento(criar, frase_espera)
    except errors.APIError as e:
        raise traduzir_excecao(e, modelo) from e
    except Exception as e:
        raise falha_inesperada(e) from e

    bloqueio = getattr(getattr(resposta, "prompt_feedback", None), "block_reason", None)
    candidato = (resposta.candidates or [None])[0]
    motivo = str(getattr(candidato, "finish_reason", "") or "")
    if bloqueio or any(m in motivo for m in ("SAFETY", "PROHIBITED", "BLOCKLIST", "SPII")):
        raise FalhaInstrumento(
            "a IA se recusou a fazer este pedido por política de segurança do Google.",
            retentavel=False, codigo="ia.recusa",
        )
    texto = (resposta.text or "").strip() if candidato else ""
    return {"texto": texto, "resposta": resposta, "uso": _uso(modelo, resposta)}


def _buscas(resposta) -> int:
    candidato = (resposta.candidates or [None])[0]
    meta = getattr(candidato, "grounding_metadata", None)
    return len(getattr(meta, "web_search_queries", None) or [])


def _uso(modelo: str, resposta) -> dict:
    """O gasto real no formato do uso do Batuta. O raciocínio é cobrado como saída; o
    que as ferramentas leram (página, resultados da busca) como entrada."""
    u = resposta.usage_metadata
    entrada = (getattr(u, "prompt_token_count", 0) or 0) + (getattr(u, "tool_use_prompt_token_count", 0) or 0)
    saida = (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
    cache_read = getattr(u, "cached_content_token_count", 0) or 0
    buscas = _buscas(resposta)
    custo = precos.custo_usd(modelo, entrada, saida, cache_read, 0) + buscas * PRECO_BUSCA_USD
    return {
        "modelo": modelo,
        "tokens_entrada": entrada,
        "tokens_saida": saida,
        "tokens_cache_read": cache_read,
        "tokens_cache_write": 0,
        "buscas": buscas,
        "leituras": 0,
        "custo_usd": round(custo, 6),
    }


def fontes(resposta) -> list[dict]:
    """As páginas em que a resposta se apoiou (busca do Google), sem repetir. O Google
    devolve um link de redirecionamento dele, que leva à página; o título é o site."""
    candidato = (resposta.candidates or [None])[0]
    meta = getattr(candidato, "grounding_metadata", None)
    vistas: dict[str, dict] = {}
    for pedaco in getattr(meta, "grounding_chunks", None) or []:
        web = getattr(pedaco, "web", None)
        if web and web.uri:
            vistas.setdefault(web.uri, {"titulo": web.title or "", "url": web.uri})
    return list(vistas.values())


def links_lidos(resposta) -> dict[str, str]:
    """{link: situação} dos links que a leitura tentou abrir (`url_context`)."""
    candidato = (resposta.candidates or [None])[0]
    meta = getattr(candidato, "url_context_metadata", None)
    return {
        m.retrieved_url: str(getattr(m.url_retrieval_status, "value", m.url_retrieval_status))
        for m in getattr(meta, "url_metadata", None) or [] if m.retrieved_url
    }
