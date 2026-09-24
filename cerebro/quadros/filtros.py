"""A linguagem ÚNICA de filtro e ordem dos quadros — a mesma para agente, tela, IA
criadora e MCP. Quem aprende uma vez usa em consultar, totalizar, editar e apagar.

Um filtro é `{"coluna": <nome ou id>, "operador": <op>, "valor": <valor>}`. Os filtros
de uma lista valem TODOS juntos (e). Operadores (com os apelidos aceitos):

| operador    | apelidos                 | vale para                                   |
|-------------|--------------------------|---------------------------------------------|
| `=`         | igual, ==                | todos                                       |
| `!=`        | ≠, diferente, <>         | todos (inclui as linhas vazias)             |
| `>` `>=`    | ≥, maior…                | número, dinheiro, data, data e hora, texto  |
| `<` `<=`    | ≤, menor…                | idem                                        |
| `contem`    | contém, like             | texto, texto longo, opção                   |
| `em`        | está em, in              | todos — `valor` é uma lista                 |
| `vazio`     | é vazio, nulo            | todos — sem `valor`                         |
| `nao_vazio` | não vazio, preenchido    | todos — sem `valor`                         |

Além das colunas do quadro, dá para filtrar e ordenar pelo CARIMBO: `_criado_em`,
`_atualizado_em` (data e hora), `_origem` (agente, pessoa, ia_criadora, mcp,
importacao), `_execucao_id` e `_agente_id`.

O valor do filtro passa pela MESMA normalização da gravação: "21/09/2026" filtra uma
coluna de data, "1.234,56" filtra dinheiro, "Sim" filtra sim/não.
"""

import uuid

from sqlalchemy import Numeric, cast, func, or_
from sqlalchemy.sql.elements import ColumnElement

from modelos import Quadro, QuadroLinha
from quadros import tipos
from quadros.tipos import ValorInvalido

_APELIDOS = {
    "=": "=", "==": "=", "igual": "=", "igual a": "=", "eq": "=",
    "!=": "!=", "≠": "!=", "<>": "!=", "diferente": "!=", "diferente de": "!=", "ne": "!=",
    ">": ">", "maior": ">", "maior que": ">", "gt": ">",
    ">=": ">=", "≥": ">=", "maior ou igual": ">=", "gte": ">=",
    "<": "<", "menor": "<", "menor que": "<", "lt": "<",
    "<=": "<=", "≤": "<=", "menor ou igual": "<=", "lte": "<=",
    "contem": "contem", "contém": "contem", "like": "contem", "inclui": "contem",
    "em": "em", "esta em": "em", "está em": "em", "in": "em", "um de": "em",
    "vazio": "vazio", "e vazio": "vazio", "é vazio": "vazio", "nulo": "vazio",
    "nao_vazio": "nao_vazio", "não vazio": "nao_vazio", "nao vazio": "nao_vazio",
    "preenchido": "nao_vazio", "não é vazio": "nao_vazio",
}
OPERADORES = ("=", "!=", ">", ">=", "<", "<=", "contem", "em", "vazio", "nao_vazio")

# Colunas do carimbo: nome → (tipo lógico, coluna da tabela)
PSEUDO = {
    "_criado_em": ("data_hora", QuadroLinha.criado_em),
    "_atualizado_em": ("data_hora", QuadroLinha.atualizado_em),
    "_origem": ("texto", QuadroLinha.origem),
    "_execucao_id": ("uuid", QuadroLinha.execucao_id),
    "_agente_id": ("uuid", QuadroLinha.agente_id),
}
ORIGENS = ("agente", "pessoa", "ia_criadora", "mcp", "importacao")


class FiltroInvalido(ValueError):
    """Filtro ou ordem que não dá para aplicar. `str(e)` é o motivo, para a pessoa."""


def resolver_coluna(quadro: Quadro, ref) -> dict | None:
    """A coluna pelo id ou pelo NOME (sem diferenciar maiúscula nem acento)."""
    if not isinstance(ref, str):
        return None
    alvo = tipos.sem_acento(ref.strip().lower())
    for c in quadro.colunas or []:
        if c["id"] == ref.strip():
            return c
    for c in quadro.colunas or []:
        if tipos.sem_acento(c["nome"].strip().lower()) == alvo:
            return c
    return None


def nomes_das_colunas(quadro: Quadro) -> str:
    return ", ".join(f"“{c['nome']}”" for c in quadro.colunas or [])


def _operador(op) -> str:
    chave = str(op or "=").strip().lower()
    if chave not in _APELIDOS:
        raise FiltroInvalido(
            f"operador “{op}” não existe. Use um destes: {', '.join(OPERADORES)}"
        )
    return _APELIDOS[chave]


def _alvo(quadro: Quadro, ref) -> tuple[str, ColumnElement, dict | None]:
    """(tipo lógico, expressão SQL comparável, coluna do quadro ou None se pseudo)."""
    if isinstance(ref, str) and ref.strip() in PSEUDO:
        tipo, expr = PSEUDO[ref.strip()]
        return tipo, expr, None
    col = resolver_coluna(quadro, ref)
    if col is None:
        raise FiltroInvalido(
            f"o quadro “{quadro.nome}” não tem a coluna “{ref}”. "
            f"As colunas são: {nomes_das_colunas(quadro)}"
        )
    texto = QuadroLinha.valores[col["id"]].astext
    if col["tipo"] in tipos.TIPOS_NUMERICOS:
        return col["tipo"], cast(texto, Numeric), col
    return col["tipo"], texto, col


def _valor_normalizado(tipo: str, col: dict | None, valor, tamanho: int):
    try:
        if tipo == "uuid":
            return uuid.UUID(str(valor))
        if col is None and tipo == "data_hora":
            # Coluna do carimbo: compara como instante.
            from datetime import datetime

            return datetime.fromisoformat(tipos.normalizar(
                {"tipo": "data_hora"}, valor, tamanho_texto_longo=tamanho
            ).replace("Z", "+00:00"))
        if col is None:
            return str(valor)
        return tipos.normalizar(col, valor, tamanho_texto_longo=tamanho)
    except (ValorInvalido, ValueError) as e:
        nome = col["nome"] if col else "carimbo"
        raise FiltroInvalido(f"no filtro da coluna “{nome}”: {e}") from None


def _comparavel(tipo: str, v):
    """O valor normalizado na mesma forma da expressão SQL."""
    if tipo == "sim_nao":
        return "true" if v else "false"
    if tipo in tipos.TIPOS_NUMERICOS:
        return v
    return v


def condicao(quadro: Quadro, filtro: dict, tamanho: int) -> ColumnElement:
    if not isinstance(filtro, dict):
        raise FiltroInvalido(
            "cada filtro é um objeto {\"coluna\": …, \"operador\": …, \"valor\": …}"
        )
    tipo, expr, col = _alvo(quadro, filtro.get("coluna"))
    op = _operador(filtro.get("operador"))
    nome = col["nome"] if col else str(filtro.get("coluna"))

    if op == "vazio":
        return expr.is_(None)
    if op == "nao_vazio":
        return expr.is_not(None)
    valor = filtro.get("valor")
    if op == "em":
        if not isinstance(valor, list) or not valor:
            raise FiltroInvalido(f"o operador “em” na coluna “{nome}” espera uma lista de valores")
        vs = [_valor_normalizado(tipo, col, v, tamanho) for v in valor]
        vs = [_comparavel(tipo, v) for v in vs if v is not None]
        if tipo in ("texto", "opcao"):
            return func.lower(expr).in_([str(v).lower() for v in vs])
        return expr.in_(vs)
    if op == "contem":
        if tipo not in ("texto", "texto_longo", "opcao"):
            raise FiltroInvalido(f"“contém” só vale para colunas de texto; “{nome}” não é")
        termo = str(valor or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return expr.ilike(f"%{termo}%", escape="\\")

    v = _valor_normalizado(tipo, col, valor, tamanho)
    if v is None:
        return expr.is_(None) if op == "=" else expr.is_not(None)
    v = _comparavel(tipo, v)
    if op in ("=", "!="):
        if tipo in ("texto", "opcao", "texto_longo"):
            igual = func.lower(expr) == str(v).lower()
        elif tipo == "uuid":
            igual = expr == v
        else:
            igual = expr == v
        return igual if op == "=" else or_(~igual, expr.is_(None))
    if tipo not in tipos.TIPOS_ORDENAVEIS and tipo != "data_hora":
        raise FiltroInvalido(f"“{op}” não vale para a coluna “{nome}” (tipo {tipos.TIPOS.get(tipo, tipo)})")
    return {
        ">": expr > v, ">=": expr >= v, "<": expr < v, "<=": expr <= v,
    }[op]


def condicoes(quadro: Quadro, filtros, tamanho: int) -> list[ColumnElement]:
    if filtros in (None, []):
        return []
    if isinstance(filtros, dict):
        filtros = [filtros]
    if not isinstance(filtros, list):
        raise FiltroInvalido("os filtros são uma lista de {\"coluna\", \"operador\", \"valor\"}")
    return [condicao(quadro, f, tamanho) for f in filtros]


def expressao_de_ordem(quadro: Quadro, item) -> ColumnElement:
    """Um item de ordem: "coluna", "-coluna" (decrescente) ou
    {"coluna": …, "direcao": "asc"|"desc"}. Vazios vão sempre para o fim."""
    if isinstance(item, str):
        desc = item.strip().startswith("-")
        ref = item.strip().lstrip("-")
    elif isinstance(item, dict):
        ref = item.get("coluna")
        direcao = str(item.get("direcao") or "asc").strip().lower()
        if direcao not in ("asc", "desc", "crescente", "decrescente"):
            raise FiltroInvalido("a direção da ordem é “asc” (crescente) ou “desc” (decrescente)")
        desc = direcao in ("desc", "decrescente")
    else:
        raise FiltroInvalido("cada item da ordem é o nome da coluna (com “-” na frente para decrescente)")
    _tipo, expr, _col = _alvo(quadro, ref)
    return (expr.desc() if desc else expr.asc()).nulls_last()


def expressao_do_mais_recente(quadro: Quadro, ref) -> ColumnElement:
    """A expressão da coluna usada em "só a mais recente de" (precisa ser ordenável)."""
    tipo, expr, col = _alvo(quadro, ref)
    if tipo not in tipos.TIPOS_ORDENAVEIS and tipo != "data_hora":
        nome = col["nome"] if col else str(ref)
        raise FiltroInvalido(
            f"“só a mais recente de” precisa de uma coluna de data, número ou texto; “{nome}” não é"
        )
    return expr


