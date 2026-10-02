"""Chamada às ferramentas que rodam NA OPENAI (busca na web, leitura de página,
leitura de PDF, execução de código) — a peça comum dos instrumentos de IA quando a
IA escolhida é a OpenAI (2026-10-02). Par da `anthropic_servidor`: os instrumentos
"por capacidade" (pesquisar na web, ler página, ler documento, gerar arquivo) chamam
uma ou outra conforme o MODELO escolhido na configuração.

O que é igual para todos, aqui:

- a chave vem do pool da organização (contexto `usar_chaves`); a OpenAI não tem
  chave de reserva no ambiente — sem chave no pool, falha com o caminho;
- TEMPO LIMITE em toda chamada (§12-A) e sinal de vida durante a espera longa;
- ERRO DEVOLVIDO COMO DADO: a resposta pode voltar `incomplete`/`failed`, ou uma
  busca com `status: failed` — sem tratar, o agente narraria sucesso;
- MODELO DESLIGADO: o recado honesto do `llm.modelo_indisponivel`;
- CUSTO REAL: tokens (com cache) + buscas + espaço de execução, em `uso`.

Referência: developers.openai.com/api/docs (Responses API, web search, code
interpreter, file inputs, pricing). Medido ao vivo em 2026-10-02 com gpt-5.6-luna:
pesquisa ~US$ 0,012 em 4-6 s; planilha com gráfico ~US$ 0,03 em 11 s.
"""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import openai

import precos
from instrumentos.anthropic_servidor import _com_batimento
from instrumentos.base import FalhaInstrumento
from orquestracao import ciclo_modelos
from orquestracao.llm import chaves_atuais, modelo_indisponivel

TIMEOUT_S = 180.0
MAX_RETENTATIVAS = 2

# US$ por busca na web (US$ 10 por mil — os tokens do conteúdo são cobrados à parte,
# ao preço do modelo, e já estão no `usage`).
PRECO_BUSCA_USD = 0.01
# US$ por espaço de execução de 1 GB (sessão de até 20 min) — o que o code interpreter
# cria a cada pedido com `container: auto`.
PRECO_CONTAINER_USD = 0.03

# Padrões: Luna (o mais barato, raciocina e abre páginas) para web e arquivo; Terra
# para documento, onde a precisão pesa (paralelo ao Sonnet 5 na Anthropic).
MODELO_PADRAO_WEB = "gpt-5.6-luna"
MODELO_PADRAO = "gpt-5.6-terra"


def modelos_disponiveis() -> list[str]:
    """Os modelos da OpenAI que servem a estes instrumentos (do registro de validade).
    Ficam de fora os da geração GPT-4: não abrem página na busca (só os que raciocinam
    abrem) e a execução de código neles é a antiga."""
    return [
        m for m in ciclo_modelos.modelos(ciclo_modelos.TEXTO, "openai")
        if not m.startswith(("gpt-4", "o1", "o3", "o4"))
    ]


def _chave() -> str:
    chave = chaves_atuais().get("openai")
    if not chave:
        raise FalhaInstrumento(
            "não há chave da OpenAI: um admin precisa cadastrá-la em Organização › Chaves "
            "(ou escolha um modelo da Anthropic neste instrumento).",
            retentavel=False, codigo="ia.sem_chave",
        )
    return chave


def cliente(timeout: float | None = None) -> openai.OpenAI:
    return openai.OpenAI(
        api_key=_chave(), timeout=timeout or TIMEOUT_S, max_retries=MAX_RETENTATIVAS
    )


def traduzir_excecao(e: Exception, modelo: str) -> FalhaInstrumento:
    recado = modelo_indisponivel(e, modelo)
    if recado:
        return FalhaInstrumento(recado, retentavel=False, codigo="ia.modelo_desligado")
    if isinstance(e, openai.AuthenticationError):
        return FalhaInstrumento(
            "a OpenAI recusou a chave cadastrada (revogada ou errada). Um admin precisa "
            "trocá-la em Organização › Chaves.", retentavel=False, codigo="ia.chave_recusada",
        )
    if isinstance(e, openai.PermissionDeniedError):
        return FalhaInstrumento(
            f"a conta da OpenAI da empresa não tem acesso a este recurso ou modelo "
            f"({modelo or 'pedido'}). Escolha outro modelo no instrumento.",
            retentavel=False, codigo="ia.recurso_desligado",
        )
    if isinstance(e, openai.BadRequestError):
        return FalhaInstrumento(f"a OpenAI recusou o pedido: {str(e)[:300]}", retentavel=False)
    if isinstance(e, (openai.RateLimitError, openai.InternalServerError,
                      openai.APIConnectionError, openai.APITimeoutError)):
        return FalhaInstrumento(
            "a OpenAI não respondeu a tempo ou está sobrecarregada; tente de novo em instantes.",
            retentavel=True, codigo="ia.indisponivel",
        )
    return FalhaInstrumento(f"a chamada à OpenAI falhou: {str(e)[:300]}", retentavel=True)


def chamar(
    *, modelo: str, sistema: str, conteudo: list[dict], ferramentas: list[dict],
    include: list[str] | None = None, max_ferramentas: int | None = None,
    timeout: float | None = None, frase_espera: str | None = None,
    cliente_pronto: openai.OpenAI | None = None,
) -> dict:
    """Uma chamada à Responses API. Devolve `{"texto", "itens", "erros", "uso"}`: a
    resposta final, os itens da saída (dicts), os motivos de falha das ferramentas e
    o uso real."""
    cli = cliente_pronto or cliente(timeout)
    extra: dict = {}
    if ferramentas:
        extra["tools"] = ferramentas
    if include:
        extra["include"] = include
    if max_ferramentas:
        extra["max_tool_calls"] = max_ferramentas
    criar = lambda: cli.responses.create(  # noqa: E731
        model=modelo, instructions=sistema,
        input=[{"role": "user", "content": conteudo}], **extra,
    )
    try:
        resposta = _com_batimento(criar, frase_espera)
    except openai.APIError as e:
        raise traduzir_excecao(e, modelo) from e

    itens = [i.model_dump() for i in resposta.output]
    if resposta.status == "failed":
        erro = getattr(resposta, "error", None)
        raise FalhaInstrumento(
            f"a OpenAI não concluiu o pedido: {getattr(erro, 'message', None) or 'sem detalhe'}.",
            retentavel=True, codigo="openai.falhou",
        )
    if any(i.get("type") == "refusal" for item in itens for i in item.get("content") or []):
        raise FalhaInstrumento(
            "a IA se recusou a fazer este pedido por política de segurança da OpenAI.",
            retentavel=False, codigo="ia.recusa",
        )
    erros = [
        f"{i.get('type')}: {i.get('status')}" for i in itens
        if str(i.get("type", "")).endswith("_call") and i.get("status") == "failed"
    ]
    texto = (resposta.output_text or "").strip()
    if not texto and resposta.status == "incomplete":
        motivo = getattr(getattr(resposta, "incomplete_details", None), "reason", None)
        raise FalhaInstrumento(
            f"a OpenAI parou antes de terminar ({motivo or 'sem motivo informado'}); "
            "peça algo mais específico.", retentavel=False, codigo="openai.incompleto",
        )
    if not texto and erros:
        raise FalhaInstrumento(
            "a ferramenta da OpenAI falhou (" + "; ".join(erros) + ").",
            retentavel=True, codigo="openai.ferramenta_falhou",
        )
    return {"texto": texto, "itens": itens, "erros": erros, "uso": _uso(modelo, resposta.usage, itens)}


def _uso(modelo: str, usage, itens: list[dict]) -> dict:
    """O gasto real no formato do uso do Batuta. A OpenAI não cobra a mais por gravar
    no cache: só a releitura sai com desconto."""
    u = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage or {})
    entrada = u.get("input_tokens") or 0
    saida = u.get("output_tokens") or 0
    cache_read = (u.get("input_tokens_details") or {}).get("cached_tokens") or 0
    buscas = sum(
        1 for i in itens
        if i.get("type") == "web_search_call" and (i.get("action") or {}).get("type") == "search"
    )
    leituras = sum(
        1 for i in itens
        if i.get("type") == "web_search_call" and (i.get("action") or {}).get("type") != "search"
    )
    containers = {
        i.get("container_id") for i in itens
        if i.get("type") == "code_interpreter_call" and i.get("container_id")
    }
    custo = precos.custo_usd(modelo, entrada, saida, cache_read, 0)
    custo += buscas * PRECO_BUSCA_USD + len(containers) * PRECO_CONTAINER_USD
    return {
        "modelo": modelo,
        "tokens_entrada": entrada,
        "tokens_saida": saida,
        "tokens_cache_read": cache_read,
        "tokens_cache_write": 0,
        "buscas": buscas,
        "leituras": leituras,
        "custo_usd": round(custo, 6),
    }


def anotacoes(itens: list[dict]) -> list[dict]:
    """As anotações do texto final (citações de páginas, arquivos gerados)."""
    return [
        a for item in itens if item.get("type") == "message"
        for c in item.get("content") or [] for a in c.get("annotations") or []
    ]


def _sem_marca(url: str) -> str:
    """Tira o `utm_source=openai` que a OpenAI pendura nos links citados."""
    partes = urlsplit(url)
    consulta = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
                if not (k == "utm_source" and v == "openai")]
    return urlunsplit(partes._replace(query=urlencode(consulta)))


def fontes(itens: list[dict]) -> list[dict]:
    """As páginas citadas na resposta e as que a busca consultou, sem repetir."""
    vistas: dict[str, dict] = {}

    def anotar(url: str, titulo: str | None) -> None:
        url = _sem_marca(url)
        vistas.setdefault(url, {"titulo": titulo or "", "url": url})

    for a in anotacoes(itens):
        if a.get("type") == "url_citation" and a.get("url"):
            anotar(a["url"], a.get("title"))
    for i in itens:
        if i.get("type") == "web_search_call":
            for s in (i.get("action") or {}).get("sources") or []:
                if s.get("url"):
                    anotar(s["url"], s.get("title"))
    return list(vistas.values())


def sem_marca_no_texto(texto: str) -> str:
    """O mesmo `utm_source=openai`, dentro dos links que vêm no texto da resposta."""
    return re.sub(r"[?&]utm_source=openai(?=[)\s\]]|$)", "", texto)
