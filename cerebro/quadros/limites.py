"""Os limites de um quadro — todos VISÍVEIS e AJUSTÁVEIS (PRODUTO.md §21, "nenhum limite
é secreto").

Cada quadro guarda só os ajustes do usuário (`Quadro.limites`); o efetivo é o padrão
daqui com o ajuste por cima. O TETO é a borda do que o ajuste aceita — também visível,
porque um limite que só aparece quando estoura é secreto do mesmo jeito.
"""

from modelos import Quadro

# chave → (padrão, teto, rótulo para a tela, o que acontece ao estourar)
LIMITES: dict[str, tuple[int, int, str, str]] = {
    "colunas": (
        60, 200, "Colunas no quadro",
        "o quadro não aceita mais colunas",
    ),
    "linhas_por_gravacao": (
        500, 5000, "Linhas por gravação",
        "uma gravação com mais linhas é recusada inteira",
    ),
    "linhas_por_consulta": (
        200, 1000, "Linhas devolvidas por consulta",
        "a consulta devolve até esse número e avisa quantas faltaram",
    ),
    "linhas_no_quadro": (
        100_000, 1_000_000, "Linhas no quadro",
        "gravações que passariam do total são recusadas",
    ),
    "tamanho_texto_longo": (
        20_000, 200_000, "Caracteres num texto longo",
        "um texto maior é recusado",
    ),
}

ONDE_MUDAR = "Dá para mudar nos limites do quadro."


def efetivos(quadro: Quadro) -> dict[str, int]:
    """O valor que vale para este quadro, limite a limite."""
    ajustes = quadro.limites or {}
    return {
        chave: int(ajustes.get(chave) or padrao)
        for chave, (padrao, _teto, _rot, _efeito) in LIMITES.items()
    }


def descrever(quadro: Quadro) -> list[dict]:
    """Os limites como a tela e as IAs mostram: rótulo, valor, padrão, teto, efeito."""
    ajustes = quadro.limites or {}
    return [
        {
            "chave": chave,
            "rotulo": rotulo,
            "valor": int(ajustes.get(chave) or padrao),
            "padrao": padrao,
            "teto": teto,
            "ajustado": chave in ajustes,
            "ao_estourar": efeito,
        }
        for chave, (padrao, teto, rotulo, efeito) in LIMITES.items()
    ]


def validar_ajuste(chave: str, valor) -> str | None:
    """Motivo da recusa (em português) ou None. `valor` None = voltar ao padrão."""
    if chave not in LIMITES:
        return f"não existe limite chamado “{chave}”. Os limites são: {', '.join(LIMITES)}"
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int):
        return f"o limite “{chave}” precisa ser um número inteiro"
    _padrao, teto, rotulo, _efeito = LIMITES[chave]
    if valor < 1 or valor > teto:
        return f"“{rotulo}” aceita de 1 a {teto}"
    return None
