"""Medição de uso — preços aproximados e resumo de custo (Tarefa 5.4).

Informativo, não para cobrança (PRODUTO §25): só dá transparência ao cliente.
Os preços são aproximados (USD por milhão de tokens) e podem ficar
desatualizados — a tela deixa claro que é uma estimativa.
"""

# (preço de entrada, preço de saída) em USD por 1 milhão de tokens — aproximado.
PRECOS_USD_POR_MTOK = {
    "opus": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}
# Usado quando o modelo não casa com nenhuma família conhecida.
PRECO_PADRAO = (1.0, 5.0)

# Transcrição (Whisper) é cobrada por MINUTO de áudio, não por token (whisper-1 =
# US$0,006/min). A entrada de uso traz `segundos` e um `custo_usd` pré-calculado.
PRECO_WHISPER_MIN = 0.006

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

# Geração de VÍDEO (OpenAI/Sora) é cobrada POR SEGUNDO, variando pelo modelo e pela
# CLASSE de resolução (720p/1080p — só o pro faz 1080p). Aproximado (informativo, não
# cobrança). A entrada de uso traz `segundos` e um `custo_usd` pré-calculado. Mantida
# alinhada ao `instrumentos.gerar_video.CATALOGO_VIDEO`.
PRECOS_VIDEO_USD = {
    "sora-2": {"720p": 0.10},
    "sora-2-pro": {"720p": 0.30, "1080p": 0.70},
}
PRECO_VIDEO_PADRAO_POR_S = 0.10

# Rótulos internos das categorias de uso (em que FUNÇÃO a IA paga foi gasta). A
# interface dá o nome amigável (`interface/lib/uso.ts`). Carimbadas na borda:
# execucao (disparo), conversa (IA criadora), mensageria/transcricao (atendimento),
# instrumento (instrumentos com IA paga, ex.: gerar_imagem).
CATEGORIAS = ("execucao", "conversa", "mensageria", "transcricao", "instrumento")


def _preco(modelo: str) -> tuple[float, float]:
    m = (modelo or "").lower()
    for familia, preco in PRECOS_USD_POR_MTOK.items():
        if familia in m:
            return preco
    return PRECO_PADRAO


def custo_usd(modelo: str, tokens_entrada: int, tokens_saida: int) -> float:
    """Custo aproximado de uma chamada, em USD."""
    pe, ps = _preco(modelo)
    return (tokens_entrada / 1_000_000) * pe + (tokens_saida / 1_000_000) * ps


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
    return tabela.get((qualidade or "medium").lower(), tabela.get("medium", PRECO_IMAGEM_PADRAO))


def custo_por_descricao(modelo: str) -> float:
    """Custo aproximado de LER/descrever UMA imagem, em USD, por família do modelo.
    Informativo (a cobrança real é por token). Desconhecido → padrão."""
    m = (modelo or "").lower()
    for familia, preco in PRECOS_DESCRICAO_USD.items():
        if familia in m:
            return preco
    return PRECO_DESCRICAO_PADRAO


def custo_por_video(modelo: str, tamanho: str = "", segundos="8") -> float:
    """Custo aproximado de UM vídeo, em USD = preço/segundo × segundos. O preço/s vem
    do modelo e da classe de resolução (1080p quando o `tamanho` tem 1080/1920, senão
    720p). Modelo desconhecido tenta por família (o 'pro' antes do base, pois 'sora-2'
    é prefixo de 'sora-2-pro'); nada casando → padrão."""
    classe = "1080p" if ("1080" in (tamanho or "") or "1920" in (tamanho or "")) else "720p"
    tabela = PRECOS_VIDEO_USD.get((modelo or "").strip())
    if tabela is None:
        for familia in ("sora-2-pro", "sora-2"):
            if (modelo or "").strip().startswith(familia):
                tabela = PRECOS_VIDEO_USD[familia]
                break
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
        e.get("modelo", ""), e.get("tokens_entrada", 0) or 0, e.get("tokens_saida", 0) or 0
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
