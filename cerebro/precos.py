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


def resumir_uso(passos) -> dict:
    """Soma o uso de uma lista de passos (objetos com `.saida['uso']`, uma lista
    de {modelo, tokens_entrada, tokens_saida, origem?}) e estima o custo total.

    Devolve {tokens_entrada, tokens_saida, custo_usd, por_modelo, por_origem}.
    `por_origem` (Fase 7.6) separa o consumo por origem da chave (cliente ×
    consultoria × legado), para a tela de transparência. Passos antigos sem
    origem registrada caem em 'desconhecida'."""
    total_e = total_s = 0
    custo = 0.0
    por_modelo: dict[str, dict] = {}
    por_origem: dict[str, dict] = {}

    def _acumular(agrupador: dict, chave: str, te: int, ts: int, c: float) -> None:
        d = agrupador.setdefault(
            chave, {"tokens_entrada": 0, "tokens_saida": 0, "custo_usd": 0.0}
        )
        d["tokens_entrada"] += te
        d["tokens_saida"] += ts
        d["custo_usd"] = round(d["custo_usd"] + c, 6)

    for p in passos:
        for e in (getattr(p, "saida", None) or {}).get("uso") or []:
            modelo = e.get("modelo", "?")
            te = e.get("tokens_entrada", 0) or 0
            ts = e.get("tokens_saida", 0) or 0
            c = custo_usd(modelo, te, ts)
            total_e += te
            total_s += ts
            custo += c
            _acumular(por_modelo, modelo, te, ts, c)
            _acumular(por_origem, e.get("origem") or "desconhecida", te, ts, c)
    return {
        "tokens_entrada": total_e,
        "tokens_saida": total_s,
        "custo_usd": round(custo, 6),
        "por_modelo": por_modelo,
        "por_origem": por_origem,
    }
