"""Medição de uso — preços aproximados e resumo de custo (Tarefa 5.4).

Informativo, não para cobrança (PRODUTO §25): só dá transparência ao cliente.
Os preços são aproximados (USD por milhão de tokens) e podem ficar
desatualizados — a tela deixa claro que é uma estimativa.
"""

# (preço de entrada, preço de saída) em USD por 1 milhão de tokens — aproximado.
# Opus 4.x = $5/$25 (o antigo $15/$75 aqui inflava a tela /uso ~2,3× — corrigido
# 2026-07-26, achado do estudo de tokens `docs/ESTUDO-TOKENS-MARCO-0.md`).
# `_preco` casa por SUBSTRING na ordem de inserção: chaves mais específicas ANTES
# das mais genéricas (ex.: "gpt-4o-mini" antes de "gpt-4o", que é prefixo dele).
# Espelhado no seletor de modelo da interface (interface/lib/modelos.ts).
PRECOS_USD_POR_MTOK = {
    # Anthropic (por família; as versões específicas ANTES da família genérica).
    # Opus 5.5 custa menos que os outros Opus. Sonnet 5 e 5.5 custam $2/$10 — até
    # 2026-09-29 o Sonnet 5 caía em "sonnet" ($3/$15) e o custo mostrado ficava ~50%
    # acima do real.
    "opus-5-5": (4.0, 20.0),
    "opus": (5.0, 25.0),
    "sonnet-5": (2.0, 10.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
    # OpenAI GPT-5.6 (Luna teve corte de 80% em 30/jul/2026)
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.0, 12.0),
    "gpt-5.6-sol": (5.0, 30.0),
    # OpenAI GPT-4 (legado ainda ofertado; -mini antes de -4o)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.5, 10.0),
    "gpt-4.1": (2.0, 8.0),
    # Google Gemini (ai.google.dev/gemini-api/docs/pricing, 2026-10-02). Os Flash 3.6
    # e 3.8 sobem para $1,50/$7,50 em 01/01/2027 — reveja aqui na virada.
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-pro-preview": (2.0, 12.0),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-1.5-flash": (0.075, 0.30),
}

# Multiplicadores do cache de prompt (Anthropic, Parte D): a RELEITURA do prefixo
# cacheado custa ~10% do preço de entrada; a CRIAÇÃO do cache custa ~1,25×. O resto da
# entrada e a saída seguem a preço cheio.
CACHE_READ_MULT = 0.10
CACHE_WRITE_MULT = 1.25
# Usado quando o modelo não casa com nenhuma família conhecida.
PRECO_PADRAO = (1.0, 5.0)

# Transcrição (Whisper) é cobrada por MINUTO de áudio, não por token (whisper-1 =
# US$0,006/min). A entrada de uso traz `segundos` e um `custo_usd` pré-calculado.
PRECO_WHISPER_MIN = 0.006
# Pelo Google (Flash-Lite ouvindo o áudio): ~US$ 0,005 por minuto
# (ai.google.dev/gemini-api/docs/pricing, 2026-10-02).
PRECO_TRANSCRICAO_GOOGLE_MIN = 0.005

# Geração de imagem é cobrada por IMAGEM (não por token), variando sobretudo pela
# QUALIDADE (low/medium/high) — aproximado, como todo este módulo (informativo, não
# cobrança). A entrada de uso traz `imagens` e um `custo_usd` pré-calculado. Tabela
# por modelo → qualidade (USD/imagem ~1024x1024). Mantida alinhada ao
# `instrumentos.gerar_imagem.CATALOGO_IMAGEM` (um teste-guarda garante o par).
PRECOS_IMAGEM_USD = {
    "gpt-image-1": {"low": 0.011, "medium": 0.042, "high": 0.167},
    "gpt-image-1-mini": {"low": 0.005, "medium": 0.015, "high": 0.060},
    "gpt-image-1.5": {"low": 0.011, "medium": 0.042, "high": 0.167},
    "gpt-image-2": {"low": 0.011, "medium": 0.042, "high": 0.167},
    # Os 2.5 cobram a saída como o gpt-image-2 (US$ 30 por 1M tokens de imagem).
    "gpt-image-2.5-flare": {"low": 0.011, "medium": 0.042, "high": 0.167},
    "gpt-image-2.5-sunburst": {"low": 0.011, "medium": 0.042, "high": 0.167},
    # Google (ai.google.dev/gemini-api/docs/pricing, 2026-10-02): por RESOLUÇÃO.
    "gemini-3.1-flash-image": {"1K": 0.067, "2K": 0.101, "4K": 0.151},
    "gemini-3.1-flash-lite-image": {"1K": 0.034},
    "gemini-3-pro-image": {"1K": 0.134, "2K": 0.134, "4K": 0.24},
}
PRECO_IMAGEM_PADRAO = 0.042

# Leitura/descrição de imagem (instrumento de visão `descrever_imagem`) — a chamada
# real é por TOKEN, mas a borda só vê o NOME da ferramenta (não os tokens), então
# estimamos POR IMAGEM lida, por família do modelo. Informativo, não cobrança. Ordem
# importa (substring): 'gpt-4o-mini' antes de 'gpt-4o'.
PRECOS_DESCRICAO_USD = {
    "opus": 0.02,
    "sonnet": 0.006,
    "haiku": 0.002,
    "gpt-4.1": 0.006,
    "gpt-4o-mini": 0.001,
    "gpt-4o": 0.004,
    "gemini": 0.001,
}
PRECO_DESCRICAO_PADRAO = 0.004

# Geração de VÍDEO (Google/Veo, desde 2026-10-02; a Sora da OpenAI foi desligada em
# 24/09/2026) é cobrada POR SEGUNDO, pelo modelo e pela resolução — com áudio
# (ai.google.dev/gemini-api/docs/pricing). Aproximado (informativo, não cobrança). A
# entrada de uso traz `segundos` e um `custo_usd` pré-calculado. Mantida alinhada ao
# `instrumentos.gerar_video.CATALOGO_VIDEO` (um teste-guarda garante o par).
PRECOS_VIDEO_USD = {
    "veo-3.1-lite-generate-preview": {"720p": 0.05, "1080p": 0.08},
    "veo-3.1-fast-generate-preview": {"720p": 0.10, "1080p": 0.12, "4k": 0.30},
    "veo-3.1-generate-preview": {"720p": 0.40, "1080p": 0.40, "4k": 0.60},
}
PRECO_VIDEO_PADRAO_POR_S = 0.10

# Rótulos internos das categorias de uso (em que FUNÇÃO a IA paga foi gasta). A
# interface dá o nome amigável (`interface/lib/uso.ts`). Carimbadas na borda:
# execucao (disparo), conversa (IA criadora), mensageria/transcricao (atendimento),
# instrumento (instrumentos com IA paga, ex.: gerar_imagem).
CATEGORIAS = ("execucao", "conversa", "mensageria", "transcricao", "instrumento")


def preco_conhecido(modelo: str) -> tuple[float, float] | None:
    """(entrada, saída) por 1M tokens, ou None se o modelo não casa com nenhuma
    família da tabela — para a tela não mostrar um preço inventado."""
    m = (modelo or "").lower()
    for familia, preco in PRECOS_USD_POR_MTOK.items():
        if familia in m:
            return preco
    return None


def _preco(modelo: str) -> tuple[float, float]:
    return preco_conhecido(modelo) or PRECO_PADRAO


def custo_usd(
    modelo: str,
    tokens_entrada: int,
    tokens_saida: int,
    tokens_cache_read: int = 0,
    tokens_cache_write: int = 0,
) -> float:
    """Custo aproximado de uma chamada, em USD. `tokens_entrada` JÁ inclui o que veio do
    cache (convenção do usage_metadata): descontamos a parte lida/criada no cache e a
    cobramos aos multiplicadores do cache (releitura ~10%, criação ~1,25×). Sem campos de
    cache (default 0), é o cálculo de sempre — chamadas antigas não mudam."""
    pe, ps = _preco(modelo)
    cr = tokens_cache_read or 0
    cw = tokens_cache_write or 0
    regular = max(0, (tokens_entrada or 0) - cr - cw)
    entrada = (regular + cr * CACHE_READ_MULT + cw * CACHE_WRITE_MULT) / 1_000_000 * pe
    return entrada + (tokens_saida or 0) / 1_000_000 * ps


def custo_transcricao(modelo: str, segundos: float) -> float:
    """Custo aproximado de uma transcrição, por minuto de áudio e pela IA que transcreveu."""
    if (modelo or "").startswith("gemini"):
        return (max(0.0, segundos or 0) / 60.0) * PRECO_TRANSCRICAO_GOOGLE_MIN
    return custo_whisper(segundos)


def custo_whisper(segundos: float) -> float:
    """Custo aproximado de uma transcrição (Whisper), em USD, por minuto de áudio."""
    return (max(0.0, segundos or 0) / 60.0) * PRECO_WHISPER_MIN


def custo_por_imagem(modelo: str, tamanho: str = "", qualidade: str = "medium") -> float:
    """Custo aproximado de UMA imagem gerada, em USD, por modelo e qualidade
    (`tamanho` é mantido por compatibilidade, mas o preço varia por qualidade).
    Modelo desconhecido cai no padrão; qualidade desconhecida cai em 'medium'."""
    m = (modelo or "").strip()
    tabela = PRECOS_IMAGEM_USD.get(m)
    if tabela is None:
        # Modelo não tabelado (ex.: legado/aposentado): tenta por família.
        for familia, t in PRECOS_IMAGEM_USD.items():
            if m.lower().startswith(familia):
                tabela = t
                break
    if tabela is None:
        return PRECO_IMAGEM_PADRAO
    if qualidade in tabela:  # resolução do Google ("1K", "2K", "4K")
        return tabela[qualidade]
    return tabela.get((qualidade or "medium").lower(), tabela.get("medium", PRECO_IMAGEM_PADRAO))


def custo_por_descricao(modelo: str) -> float:
    """Custo aproximado de LER/descrever UMA imagem, em USD, por família do modelo.
    Informativo (a cobrança real é por token). Desconhecido → padrão."""
    m = (modelo or "").lower()
    for familia, preco in PRECOS_DESCRICAO_USD.items():
        if familia in m:
            return preco
    return PRECO_DESCRICAO_PADRAO


def custo_por_video(modelo: str, resolucao: str = "", segundos="8") -> float:
    """Custo aproximado de UM vídeo, em USD = preço/segundo × segundos. O preço/s vem
    do modelo e da resolução (720p quando não informada). Modelo desconhecido → padrão."""
    classe = (resolucao or "720p").strip().lower()
    tabela = PRECOS_VIDEO_USD.get((modelo or "").strip())
    por_s = (
        tabela.get(classe, tabela.get("720p", PRECO_VIDEO_PADRAO_POR_S))
        if tabela
        else PRECO_VIDEO_PADRAO_POR_S
    )
    try:
        segs = int(str(segundos).strip())
    except (TypeError, ValueError):
        segs = 0
    return por_s * max(0, segs)


def custo_de_entrada(e: dict) -> float:
    """Custo (USD) de UMA entrada de uso. Honra `custo_usd` pré-calculado quando a
    entrada o traz (itens não-token, como o Whisper); senão estima por token."""
    pre = e.get("custo_usd")
    if pre is not None:
        return float(pre)
    return custo_usd(
        e.get("modelo", ""),
        e.get("tokens_entrada", 0) or 0,
        e.get("tokens_saida", 0) or 0,
        e.get("tokens_cache_read", 0) or 0,
        e.get("tokens_cache_write", 0) or 0,
    )


def _com_categoria(e: dict, padrao: str) -> dict:
    """Garante que a entrada tenha uma `categoria` para a agregação, sem mutar o
    dict guardado (entradas antigas, anteriores ao carimbo, herdam o padrão da
    fonte de onde foram colhidas)."""
    if e.get("categoria"):
        return e
    return {**e, "categoria": padrao}


def entradas_dos_passos(passos):
    """Achata os passos de execução numa sequência de entradas de uso, cada uma um
    dict {modelo, tokens_entrada, tokens_saida, origem?, categoria?}. Entradas sem
    categoria caem em 'execucao' (a fonte)."""
    for p in passos:
        for e in (getattr(p, "saida", None) or {}).get("uso") or []:
            yield _com_categoria(e, "execucao")


def entradas_das_conversas(conversas):
    """Achata as conversas da IA criadora numa sequência de entradas de uso. Cada
    turno da IA guarda UM dict `uso` (não uma lista) em `mensagens[].uso`. Sem
    categoria → 'conversa'."""
    for c in conversas:
        for m in getattr(c, "mensagens", None) or []:
            if m.get("papel") == "ia" and m.get("uso"):
                yield _com_categoria(m["uso"], "conversa")


def entradas_das_mensagens(mensagens):
    """Achata as mensagens da mensageria numa sequência de entradas de uso. A
    mensagem do AGENTE guarda em `uso` a LISTA de entradas do turno (chamadas do
    agente + transcrições de áudio), cada uma já com origem e categoria. Sem
    categoria → 'mensageria'."""
    for m in mensagens:
        for e in getattr(m, "uso", None) or []:
            yield _com_categoria(e, "mensageria")


def resumir_uso_de_entradas(entradas) -> dict:
    """Soma uma sequência de entradas de uso (dicts {modelo, tokens_entrada,
    tokens_saida, origem?}) e estima o custo total.

    Devolve {tokens_entrada, tokens_saida, custo_usd, por_modelo, por_origem,
    por_categoria}. `por_origem` (Fase 7.6) separa o consumo por origem da chave
    (cliente × consultoria × legado); `por_categoria` separa por FUNÇÃO em que a IA
    foi gasta (execução × conversa × atendimento × transcrição) — transparência ao
    usuário. Entradas sem origem/categoria registrada caem em 'desconhecida'."""
    total_e = total_s = 0
    custo = 0.0
    por_modelo: dict[str, dict] = {}
    por_origem: dict[str, dict] = {}
    por_categoria: dict[str, dict] = {}

    def _acumular(agrupador: dict, chave: str, te: int, ts: int, c: float) -> None:
        d = agrupador.setdefault(
            chave, {"tokens_entrada": 0, "tokens_saida": 0, "custo_usd": 0.0}
        )
        d["tokens_entrada"] += te
        d["tokens_saida"] += ts
        d["custo_usd"] = round(d["custo_usd"] + c, 6)

    for e in entradas:
        modelo = e.get("modelo", "?")
        te = e.get("tokens_entrada", 0) or 0
        ts = e.get("tokens_saida", 0) or 0
        c = custo_de_entrada(e)
        total_e += te
        total_s += ts
        custo += c
        _acumular(por_modelo, modelo, te, ts, c)
        _acumular(por_origem, e.get("origem") or "desconhecida", te, ts, c)
        _acumular(por_categoria, e.get("categoria") or "desconhecida", te, ts, c)
    return {
        "tokens_entrada": total_e,
        "tokens_saida": total_s,
        "custo_usd": round(custo, 6),
        "por_modelo": por_modelo,
        "por_origem": por_origem,
        "por_categoria": por_categoria,
    }


# Categorias em que o gasto é do PRÓPRIO agente (o modelo que pensa e responde); o
# resto é de um instrumento/serviço que ele acionou (imagem, visão, busca, leitura,
# transcrição de áudio…). É a divisão que o resumo do time mostra.
CATEGORIAS_IA_DO_AGENTE = ("execucao", "mensageria", "conversa")


def separar_custos(itens) -> dict:
    """Separa o custo entre a IA DOS AGENTES e os INSTRUMENTOS, por agente e por
    instrumento. `itens` = pares (entrada de uso, agente_id ou None).

    Devolve {ia_agentes_usd, instrumentos_usd, por_agente, por_instrumento}:
    - `por_agente[agente_id]` = {ia_usd, instrumentos_usd} ("" = agente não identificado);
    - `por_instrumento[chave]` = {instrumento_id, nome, tipo, custo_usd, chamadas}. A
      chave é o id do instrumento; a transcrição de áudio vira "transcricao"; o custo de
      instrumento gravado antes de 2026-09-26 (sem id) cai em "anteriores"."""
    ia_total = inst_total = 0.0
    por_agente: dict[str, dict] = {}
    por_instrumento: dict[str, dict] = {}
    for e, agente_id in itens:
        c = custo_de_entrada(e)
        ag = por_agente.setdefault(
            str(agente_id or ""), {"ia_usd": 0.0, "instrumentos_usd": 0.0}
        )
        if (e.get("categoria") or "execucao") in CATEGORIAS_IA_DO_AGENTE:
            ia_total += c
            ag["ia_usd"] = round(ag["ia_usd"] + c, 6)
            continue
        inst_total += c
        ag["instrumentos_usd"] = round(ag["instrumentos_usd"] + c, 6)
        if e.get("categoria") == "transcricao":
            chave, nome, tipo = "transcricao", None, "transcricao"
        elif e.get("instrumento_id"):
            chave, nome, tipo = str(e["instrumento_id"]), e.get("instrumento"), e.get("tipo")
        else:
            chave, nome, tipo = "anteriores", None, None
        d = por_instrumento.setdefault(
            chave,
            {"instrumento_id": chave if tipo not in (None, "transcricao") else None,
             "nome": nome, "tipo": tipo, "custo_usd": 0.0, "chamadas": 0},
        )
        d["custo_usd"] = round(d["custo_usd"] + c, 6)
        d["chamadas"] += 1
    return {
        "ia_agentes_usd": round(ia_total, 6),
        "instrumentos_usd": round(inst_total, 6),
        "por_agente": por_agente,
        "por_instrumento": por_instrumento,
    }


def resumir_uso(passos=(), conversas=(), mensagens=()) -> dict:
    """Soma o uso de passos de execução, conversas da IA criadora e/ou mensagens da
    mensageria. O dashboard do time passa `passos` (+ mensageria); a visão por
    organização passa os três (a conversa Opus e o atendimento são caros e não
    podem ficar invisíveis)."""
    return resumir_uso_de_entradas(
        [
            *entradas_dos_passos(passos),
            *entradas_das_conversas(conversas),
            *entradas_das_mensagens(mensagens),
        ]
    )
