"""Chamada às ferramentas que rodam NA ANTHROPIC (busca na web, leitura de página,
leitura de documento) — a peça comum dos instrumentos de IA da Anthropic (2026-10-02).

O instrumento faz uma chamada PRÓPRIA à Anthropic, como o `gerar_imagem` faz à OpenAI:
serve a qualquer agente, seja qual for o modelo dele, e o custo é medido de verdade.
Esta peça cuida do que é igual para todos:

- a chave vem do pool da organização (contexto `usar_chaves`) e, como no motor, cai
  na ANTHROPIC_API_KEY do ambiente (a chave da consultoria) se não houver;
- TEMPO LIMITE em toda chamada (§12-A: nenhuma ligação sem limite de espera);
- TURNO PAUSADO: com ferramentas de servidor, a Anthropic pode parar no meio
  (`stop_reason: "pause_turn"`); reenviamos a conversa e ela continua de onde parou;
- ERRO DEVOLVIDO COMO DADO: a busca/leitura que falha volta com HTTP 200 e um bloco
  de erro (`max_uses_exceeded`, `url_not_accessible`…). Sem tratar, o agente narraria
  sucesso — aqui vira `FalhaInstrumento` com o motivo em português;
- MODELO DESLIGADO: o recado honesto do `llm.modelo_indisponivel`;
- CUSTO REAL: tokens (com cache) + buscas, devolvidos em `uso` para a medição.

Referência: platform.claude.com/docs (web search tool, web fetch tool, PDF support,
citations, handling stop reasons).
"""

import os

import anthropic

import precos
from instrumentos.base import FalhaInstrumento
from orquestracao import ciclo_modelos
from orquestracao.llm import chaves_atuais, modelo_indisponivel

# Uma chamada com busca/leitura costuma levar segundos; uma pesquisa com várias buscas,
# um ou dois minutos. Teto generoso, mas finito.
TIMEOUT_S = 180.0
# O SDK já retenta 429/5xx/queda de conexão; poucas vezes, para a falha chegar rápido.
MAX_RETENTATIVAS = 2
# Quantas vezes continuamos um turno pausado antes de desistir (evita laço sem fim).
MAX_CONTINUACOES = 5
MAX_TOKENS = 8000

# Versões das ferramentas. As de 2026-02-09 filtram o resultado antes de o modelo ler
# (mais barato e mais preciso) e exigem Sonnet 4.6+/Opus 4.6+; o Haiku usa a básica.
# FONTE ÚNICA: se a Anthropic aposentar uma versão, é só aqui.
BUSCA_NOVA, BUSCA_BASICA = "web_search_20260209", "web_search_20250305"
LEITURA_NOVA, LEITURA_BASICA = "web_fetch_20260209", "web_fetch_20250910"

# US$ por busca na web (US$ 10 por mil — platform.claude.com/docs/en/about-claude/pricing).
PRECO_BUSCA_USD = 0.01

# Padrões medidos ao vivo em 2026-10-02 (mesma pergunta): busca com Haiku 4.5 (versão
# básica) = US$ 0,02; com Sonnet 5 (versão que filtra) = US$ 0,20 — dez vezes mais, e a
# resposta do Haiku veio mais atual. Para buscar e ler página, Haiku; para documento
# (contrato, nota fiscal, onde a precisão pesa), Sonnet 5 — custou US$ 0,006 num PDF.
MODELO_PADRAO = "claude-sonnet-5"
MODELO_PADRAO_WEB = "claude-haiku-4-5"


def modelos_disponiveis() -> list[str]:
    """Os modelos da Anthropic que se podem escolher (do registro de validade)."""
    return ciclo_modelos.modelos(ciclo_modelos.TEXTO, "anthropic")


def versoes(modelo: str) -> tuple[str, str]:
    """(busca, leitura) que este modelo aceita."""
    if "haiku" in (modelo or "").lower():
        return BUSCA_BASICA, LEITURA_BASICA
    return BUSCA_NOVA, LEITURA_NOVA


# O que cada código de erro das ferramentas quer dizer, para quem usa.
_ERROS = {
    "max_uses_exceeded": "a IA atingiu o limite de buscas/leituras desta configuração",
    "too_many_requests": "a Anthropic pediu para esperar (muitas buscas seguidas)",
    "invalid_input": "o pedido de busca/leitura veio inválido",
    "query_too_long": "a pergunta é longa demais para a busca",
    "url_too_long": "o endereço é longo demais (máximo de 250 caracteres)",
    "url_not_allowed": "este endereço está bloqueado na configuração do instrumento",
    "url_not_accessible": "a página não pôde ser aberta (fora do ar, exige login ou bloqueia robôs)",
    "url_not_in_prior_context": "o endereço não estava no pedido (passe o link completo)",
    "unsupported_content_type": "o tipo de conteúdo não é suportado (só texto, HTML e PDF)",
    "unavailable": "o serviço de busca/leitura da Anthropic está indisponível agora",
}
# Erros que valem tentar de novo (o resto não muda com outra tentativa).
_ERROS_RETENTAVEIS = {"too_many_requests", "unavailable"}


def _chave() -> str:
    chave = chaves_atuais().get("anthropic") or os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise FalhaInstrumento(
            "não há chave da Anthropic: um admin precisa cadastrá-la em Organização › Chaves.",
            retentavel=False, codigo="ia.sem_chave",
        )
    return chave


def _cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=_chave(), timeout=TIMEOUT_S, max_retries=MAX_RETENTATIVAS)


def _traduzir_excecao(e: Exception, modelo: str) -> FalhaInstrumento:
    recado = modelo_indisponivel(e, modelo)
    if recado:
        return FalhaInstrumento(recado, retentavel=False, codigo="ia.modelo_desligado")
    if isinstance(e, anthropic.AuthenticationError):
        return FalhaInstrumento(
            "a Anthropic recusou a chave cadastrada (revogada ou errada). Um admin "
            "precisa trocá-la em Organização › Chaves.", retentavel=False, codigo="ia.chave_recusada",
        )
    if isinstance(e, anthropic.PermissionDeniedError):
        return FalhaInstrumento(
            "a conta da Anthropic da empresa não permite este recurso (ex.: a busca na "
            "web está desligada no painel da Anthropic, em Privacy settings).",
            retentavel=False, codigo="ia.recurso_desligado",
        )
    if isinstance(e, anthropic.BadRequestError):
        texto = str(e)
        if "web search" in texto.lower() or "web_search" in texto.lower():
            return FalhaInstrumento(
                "a busca na web está desligada na conta da Anthropic da empresa. Um admin "
                "precisa ligá-la no painel da Anthropic (Settings › Privacy).",
                retentavel=False, codigo="ia.recurso_desligado",
            )
        return FalhaInstrumento(f"a Anthropic recusou o pedido: {texto[:300]}", retentavel=False)
    if isinstance(e, (anthropic.RateLimitError, anthropic.InternalServerError,
                      anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return FalhaInstrumento(
            "a Anthropic não respondeu a tempo ou está sobrecarregada; tente de novo em instantes.",
            retentavel=True, codigo="ia.indisponivel",
        )
    return FalhaInstrumento(f"a chamada à Anthropic falhou: {str(e)[:300]}", retentavel=True)


def _somar_uso(total: dict, usage) -> None:
    u = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage or {})
    total["entrada"] += u.get("input_tokens") or 0
    total["saida"] += u.get("output_tokens") or 0
    total["cache_read"] += u.get("cache_read_input_tokens") or 0
    total["cache_write"] += u.get("cache_creation_input_tokens") or 0
    servidor = u.get("server_tool_use") or {}
    total["buscas"] += servidor.get("web_search_requests") or 0
    total["leituras"] += servidor.get("web_fetch_requests") or 0


def chamar(*, modelo: str, sistema: str, conteudo: list[dict], ferramentas: list[dict]) -> dict:
    """Uma rodada completa (com continuações de turno pausado). Devolve
    `{"texto", "blocos", "erros", "uso"}`: o texto final, todos os blocos (dicts) de
    todas as rodadas, os códigos de erro das ferramentas e o uso real para a medição."""
    cliente = _cliente()
    mensagens: list[dict] = [{"role": "user", "content": conteudo}]
    blocos: list[dict] = []
    total = {"entrada": 0, "saida": 0, "cache_read": 0, "cache_write": 0, "buscas": 0, "leituras": 0}
    resposta = None
    for _ in range(MAX_CONTINUACOES + 1):
        try:
            resposta = cliente.messages.create(
                model=modelo, max_tokens=MAX_TOKENS, system=sistema, messages=mensagens,
                **({"tools": ferramentas} if ferramentas else {}),
            )
        except anthropic.APIError as e:
            raise _traduzir_excecao(e, modelo) from e
        _somar_uso(total, resposta.usage)
        rodada = [b.model_dump() for b in resposta.content]
        blocos.extend(rodada)
        if resposta.stop_reason != "pause_turn":
            break
        # Continua de onde parou: reenvia o pedido + o que já veio (sem "continue").
        mensagens = [mensagens[0], {"role": "assistant", "content": resposta.content}]
    else:
        raise FalhaInstrumento(
            "a pesquisa não terminou dentro do limite de continuações; peça algo mais específico.",
            retentavel=False,
        )

    if resposta.stop_reason == "refusal":
        raise FalhaInstrumento(
            "a IA se recusou a fazer este pedido por política de segurança da Anthropic.",
            retentavel=False, codigo="ia.recusa",
        )

    erros = _erros_das_ferramentas(blocos)
    texto = "".join(b.get("text") or "" for b in blocos if b.get("type") == "text").strip()
    if not texto and erros:
        codigo = erros[0]
        raise FalhaInstrumento(
            _ERROS.get(codigo, f"a ferramenta da Anthropic falhou ({codigo})") + ".",
            retentavel=codigo in _ERROS_RETENTAVEIS, codigo=f"anthropic.{codigo}",
        )
    return {"texto": texto, "blocos": blocos, "erros": erros, "uso": _uso(modelo, total)}


def _erros_das_ferramentas(blocos: list[dict]) -> list[str]:
    """Os códigos de erro que vieram DENTRO dos resultados (HTTP 200 + bloco de erro).
    Na busca, sucesso = lista de resultados; erro = um objeto com `error_code`."""
    erros = []
    for b in blocos:
        if not str(b.get("type", "")).endswith("_tool_result"):
            continue
        conteudo = b.get("content")
        if isinstance(conteudo, dict) and conteudo.get("error_code"):
            erros.append(conteudo["error_code"])
    return erros


def _uso(modelo: str, t: dict) -> dict:
    """O gasto real, no formato do uso do Batuta (`custo_usd` pré-calculado). A
    convenção de `tokens_entrada` do Batuta INCLUI o que veio do cache."""
    entrada_total = t["entrada"] + t["cache_read"] + t["cache_write"]
    custo = precos.custo_usd(modelo, entrada_total, t["saida"], t["cache_read"], t["cache_write"])
    custo += t["buscas"] * PRECO_BUSCA_USD
    return {
        "modelo": modelo,
        "tokens_entrada": entrada_total,
        "tokens_saida": t["saida"],
        "tokens_cache_read": t["cache_read"],
        "tokens_cache_write": t["cache_write"],
        "buscas": t["buscas"],
        "leituras": t["leituras"],
        "custo_usd": round(custo, 6),
    }


def fontes(blocos: list[dict]) -> list[dict]:
    """As páginas que a busca trouxe e as citações usadas na resposta, sem repetir."""
    vistas: dict[str, dict] = {}
    for b in blocos:
        if b.get("type") == "web_search_tool_result" and isinstance(b.get("content"), list):
            for r in b["content"]:
                if r.get("url"):
                    vistas.setdefault(r["url"], {"titulo": r.get("title") or "", "url": r["url"]})
        for c in b.get("citations") or []:
            if c.get("url"):
                vistas.setdefault(c["url"], {"titulo": c.get("title") or "", "url": c["url"]})
    return list(vistas.values())


def citacoes_de_documento(blocos: list[dict]) -> list[dict]:
    """Os trechos que sustentam a resposta sobre um documento, com a página."""
    saida = []
    for b in blocos:
        for c in b.get("citations") or []:
            if c.get("type") == "page_location":
                saida.append({
                    "trecho": c.get("cited_text") or "",
                    "pagina": c.get("start_page_number"),
                })
            elif c.get("cited_text"):
                saida.append({"trecho": c["cited_text"], "pagina": None})
    return saida
