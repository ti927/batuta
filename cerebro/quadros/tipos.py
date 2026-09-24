"""Os tipos de coluna de um quadro e a normalização de cada valor.

Quem valida é o Batuta, não o agente: data que não é data, número que não é número e
opção fora da lista são RECUSADOS com o motivo em português. Isso tira do markdown do
agente as regras que hoje moram lá ("descarte a linha 'teste'", "número sem separador
de milhar") — cada uma era um lugar onde a IA errava calada.

Formas aceitas são generosas (a IA e a pessoa escrevem "21/09/2026", "1.234,56",
"sim"); a forma GUARDADA é uma só, para que ordem, filtro e total funcionem:

| tipo        | guardado como                         |
|-------------|---------------------------------------|
| texto       | texto (até 500 caracteres)            |
| texto_longo | texto (até o limite do quadro)        |
| numero      | número                                |
| dinheiro    | número com 2 casas                    |
| data        | "AAAA-MM-DD"                          |
| data_hora   | "AAAA-MM-DDTHH:MM:SSZ" (UTC)          |
| sim_nao     | verdadeiro/falso                      |
| opcao       | o texto da opção, como foi cadastrada |
"""

import math
import re
import unicodedata
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

TIPOS: dict[str, str] = {
    "texto": "Texto curto",
    "texto_longo": "Texto longo",
    "numero": "Número",
    "dinheiro": "Dinheiro",
    "data": "Data",
    "data_hora": "Data e hora",
    "sim_nao": "Sim ou não",
    "opcao": "Opção de uma lista",
}

# Tipos que podem compor a CHAVE de uma linha (texto longo não identifica nada).
TIPOS_DE_CHAVE = {"texto", "numero", "dinheiro", "data", "data_hora", "sim_nao", "opcao"}
# Tipos que comparam por ordem (>, <, mais recente, mínimo/máximo).
TIPOS_ORDENAVEIS = {"numero", "dinheiro", "data", "data_hora", "texto", "opcao"}
TIPOS_NUMERICOS = {"numero", "dinheiro"}

TAMANHO_TEXTO = 500
FUSO_PADRAO = ZoneInfo("America/Sao_Paulo")

_SIM = {"sim", "s", "true", "verdadeiro", "1", "yes", "y", "x", "v"}
_NAO = {"nao", "não", "n", "false", "falso", "0", "no", "f"}


class ValorInvalido(ValueError):
    """O valor não serve para o tipo da coluna. `str(e)` é o motivo, para a pessoa."""


def sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _numero(valor) -> int | float:
    if isinstance(valor, bool):
        raise ValorInvalido("é sim/não, não um número")
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        if not math.isfinite(valor):
            raise ValorInvalido("não é um número válido")
        return int(valor) if valor.is_integer() and abs(valor) < 2**53 else valor
    if not isinstance(valor, str):
        raise ValorInvalido("não é um número")
    s = valor.strip().replace("R$", "").replace(" ", "").replace(" ", "")
    if s.endswith("%"):
        s = s[:-1]
    # "1.000" e "1,000" são AMBÍGUOS (mil em português, um em inglês — ou o contrário).
    # Chutar seria o erro calado que o quadro existe para evitar: recusa e pede clareza.
    if re.fullmatch(r"[-+]?\d{1,3}[.,]\d{3}", s):
        raise ValorInvalido(
            f"“{valor}” é ambíguo (mil ou um?). Escreva sem separador de milhar "
            "(1000) e com vírgula ou ponto só para decimais (1,5 ou 1.5)"
        )
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    if re.fullmatch(r"[-+]?\d+\.\d+", s):
        return _numero(float(s))
    if re.fullmatch(r"[-+]?\d+,\d+", s):
        return _numero(float(s.replace(",", ".")))
    if re.fullmatch(r"[-+]?\d{1,3}(\.\d{3})+(,\d+)?", s):  # 1.234.567,89
        return _numero(float(s.replace(".", "").replace(",", ".")))
    if re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+(\.\d+)?", s):  # 1,234,567.89
        return _numero(float(s.replace(",", "")))
    raise ValorInvalido(f"“{valor}” não é um número")


def _data(valor) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if not isinstance(valor, str):
        raise ValorInvalido("não é uma data")
    s = valor.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    try:
        if m:
            return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ].*)?", s):
            return date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        raise ValorInvalido(f"“{valor}” não é uma data que exista") from None
    raise ValorInvalido(
        f"“{valor}” não é uma data (use AAAA-MM-DD, como 2026-09-21, ou DD/MM/AAAA)"
    )


def _data_hora(valor) -> str:
    if isinstance(valor, datetime):
        dt = valor
    elif isinstance(valor, date):
        dt = datetime.combine(valor, time())
    elif isinstance(valor, str):
        s = valor.strip()
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?", s)
        try:
            if m:
                dt = datetime(
                    int(m[3]), int(m[2]), int(m[1]),
                    int(m[4] or 0), int(m[5] or 0), int(m[6] or 0),
                )
            else:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            raise ValorInvalido(
                f"“{valor}” não é uma data e hora (use AAAA-MM-DDTHH:MM, como "
                "2026-09-21T14:30, ou DD/MM/AAAA HH:MM)"
            ) from None
    else:
        raise ValorInvalido("não é uma data e hora")
    if dt.tzinfo is None:
        # Sem fuso = hora de Brasília (é como a pessoa e o agente falam).
        dt = dt.replace(tzinfo=FUSO_PADRAO)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sim_nao(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int) and valor in (0, 1):
        return bool(valor)
    if isinstance(valor, str):
        s = sem_acento(valor.strip().lower())
        if s in _SIM:
            return True
        if s in {sem_acento(n) for n in _NAO}:
            return False
    raise ValorInvalido(f"“{valor}” não é sim ou não")


def _opcao(valor, opcoes: list[str]) -> str:
    if not isinstance(valor, (str, int, float)) or isinstance(valor, bool):
        raise ValorInvalido("não é uma das opções")
    s = sem_acento(str(valor).strip().lower())
    for o in opcoes:
        if sem_acento(o.lower()) == s:
            return o
    raise ValorInvalido(
        f"“{valor}” não é uma das opções ({', '.join(opcoes)})"
    )


def _texto(valor, maximo: int, tipo: str) -> str:
    if isinstance(valor, (dict, list)):
        raise ValorInvalido("é uma lista ou objeto, não um texto")
    if isinstance(valor, bool):
        valor = "sim" if valor else "não"
    s = str(valor).strip()
    if len(s) > maximo:
        dica = (
            "; para textos maiores, use uma coluna de texto longo"
            if tipo == "texto"
            else ""
        )
        raise ValorInvalido(
            f"o texto tem {len(s)} caracteres e esta coluna aceita até {maximo}{dica}"
        )
    return s


def normalizar(coluna: dict, valor, *, tamanho_texto_longo: int):
    """O valor na forma GUARDADA, ou None para vazio. Levanta `ValorInvalido`."""
    if _vazio(valor):
        return None
    tipo = coluna["tipo"]
    if tipo == "texto":
        return _texto(valor, TAMANHO_TEXTO, tipo)
    if tipo == "texto_longo":
        return _texto(valor, tamanho_texto_longo, tipo)
    if tipo == "numero":
        return _numero(valor)
    if tipo == "dinheiro":
        n = round(float(_numero(valor)), 2)
        return int(n) if n.is_integer() else n
    if tipo == "data":
        return _data(valor)
    if tipo == "data_hora":
        return _data_hora(valor)
    if tipo == "sim_nao":
        return _sim_nao(valor)
    if tipo == "opcao":
        return _opcao(valor, coluna.get("opcoes") or [])
    raise ValorInvalido(f"tipo de coluna desconhecido: {tipo}")


def texto_da_chave(valor) -> str:
    """Forma canônica em texto de um valor JÁ normalizado, para compor a chave da linha."""
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, str):
        return sem_acento(valor.strip().lower())
    return str(valor)


def id_de_coluna(nome: str, existentes: set[str]) -> str:
    """Identificador estável da coluna, derivado do nome no nascimento. Renomear a coluna
    depois NÃO muda o id — é por ele que os valores das linhas são guardados."""
    base = re.sub(r"[^a-z0-9]+", "_", sem_acento(nome.lower())).strip("_")[:40] or "coluna"
    if base[0].isdigit():
        base = "c_" + base
    candidato, n = base, 2
    while candidato in existentes:
        candidato = f"{base}_{n}"
        n += 1
    return candidato
