"""A ficha da execução — os valores nomeados que atravessam o grafo inteiro.

## Por que ela existe

Até 2026-09-01 entre um nó e outro trafegava **só texto**: a saída do agente anterior
virava a entrada do seguinte, e nada mais. Disso vinha a lacuna-raiz do motor — **a
entrada do gatilho morria no primeiro nó**. Se o agente do nó 1 não *repetisse* o dado
no texto final dele, o dado sumia; o nó 2 recebia uma frase solta e travava.

Aconteceu ao vivo em 2026-09-01 (execução `f1e23565`): o gatilho trouxe título,
subtítulo, legenda e URL do artigo; o primeiro agente pediu aprovação, voltou dizendo só
*"Aprovado. Seguindo para publicação"* — e o Gerador Carrossel recebeu essa frase em vez
dos dados, respondendo o óbvio: *"não recebi título, subtítulo e URL"*.

A ficha fecha esse buraco. Cada execução carrega **um punhado de valores nomeados** que:

- nasce com o que o gatilho trouxe (`entrada`), e isso **nunca** se perde;
- fica visível no prompt de **todos** os nós, do primeiro ao último;
- cresce quando um agente chama `anotar` (é a "variável de fluxo": ele guarda `total`,
  `cliente`, `url_da_capa`, e quem vier depois lê);
- pode ser comparada pelo MOTOR, com regra exata na seta (a IA lê a frase, mas quem
  compara `total entre 1 e 10` é o código — a IA erra a borda 10×11, o código não).

## O que ela deliberadamente NÃO é

Não é dado estruturado tipado com mapeamento de campos (estilo n8n). Aqui quem conduz
são agentes que leem texto; a ficha é um punhado de valores nomeados em prosa, não um
pipeline com esquema. Foi decisão explícita do maestro — ver o plano da Onda 2.

## Concorrência

O grafo caminha em ondas e vários ramos podem anotar o mesmo campo na mesma onda. Não há
merge inteligente: **o último a escrever vence**, e a ordem é a da onda. Para valor que
não pode ser sobrescrito, use nomes distintos por ramo (`capa_1x1`, `capa_9x16`).

Módulo **puro**: não toca o banco, não importa nada da borda. É reusado pelo motor
(`cadeia.py`), pelo agente (`agente.py`), pela validação e pela tela.
"""

import re
import unicodedata

# O que o gatilho trouxe. Sempre presente, escrito uma vez no nascimento da execução.
CAMPO_ENTRADA = "entrada"

# Tetos de sanidade — a ficha é um punhado de valores, não um banco de dados. Estourar
# não é erro do usuário: cortamos e seguimos (a ficha nunca pode derrubar a execução).
MAX_CAMPOS = 40
MAX_TEXTO = 4000  # por valor, em caracteres
MAX_NOME = 60

# --- Regra exata na seta ---------------------------------------------------------
# O papel de cada operador está em `DESCRICAO_OPERADOR` (é o texto que a tela e o
# prompt mostram). Manter os dois dicionários com as MESMAS chaves.
OPERADORES = (
    "igual", "diferente", "contem", "nao_contem",
    "maior", "maior_ou_igual", "menor", "menor_ou_igual",
    "entre", "preenchido", "vazio",
)
DESCRICAO_OPERADOR = {
    "igual": "é igual a",
    "diferente": "é diferente de",
    "contem": "contém",
    "nao_contem": "não contém",
    "maior": "é maior que",
    "maior_ou_igual": "é maior ou igual a",
    "menor": "é menor que",
    "menor_ou_igual": "é menor ou igual a",
    "entre": "está entre",
    "preenchido": "está preenchido",
    "vazio": "está vazio",
}
# Operadores que não usam `valor` (a comparação é sobre a existência do campo).
OPERADORES_SEM_VALOR = ("preenchido", "vazio")
# Operadores que exigem número dos dois lados.
OPERADORES_NUMERICOS = ("maior", "maior_ou_igual", "menor", "menor_ou_igual", "entre")


def normalizar_nome(nome: str) -> str:
    """O nome canônico de um campo: minúsculo, sem acento, espaços viram `_`.

    Existe para `Total do Pedido`, `total do pedido` e `total_do_pedido` serem o MESMO
    campo. Sem isso, o agente anota com um nome e a seta compara com outro — e o bug
    fica invisível, porque o campo "não existe" em vez de dar erro."""
    base = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_").lower()
    return base[:MAX_NOME]


def _texto(valor) -> str:
    """Qualquer valor como texto enxuto (a ficha guarda texto — é o que o agente lê)."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if isinstance(valor, (int, float)):
        return str(valor)
    return str(valor)[:MAX_TEXTO]


def nova(entrada: str | None) -> dict:
    """A ficha no nascimento da execução: só o que o gatilho trouxe.

    É este único valor que mata a lacuna nº 15 — a partir daqui, `entrada` chega a
    TODOS os nós, sem depender de nenhum agente lembrar de repeti-la."""
    texto = _texto(entrada)
    return {CAMPO_ENTRADA: texto} if texto else {}


def anotar(ficha: dict, campo: str, valor) -> tuple[str, bool]:
    """Escreve um valor na ficha (no lugar, como o agente pediu).

    Devolve `(nome canônico, substituiu?)`. Recusa nome vazio e respeita os tetos —
    silenciosamente, porque a ficha jamais pode derrubar uma execução: um nome
    esquisito ou um valor gigante viram um campo cortado, não uma falha."""
    nome = normalizar_nome(campo)
    if not nome:
        return "", False
    if nome not in ficha and len(ficha) >= MAX_CAMPOS:
        return "", False
    substituiu = nome in ficha
    ficha[nome] = _texto(valor)
    return nome, substituiu


def como_lista(valor) -> list[str]:
    """O valor de um campo lido como LISTA de itens, para o nó "Para cada item".

    Duas grafias, nesta ordem: um **array JSON** (`["a","b"]`, que é o que um agente
    produz quando o markdown pede uma lista), ou **uma linha por item** — que é como
    uma pessoa escreve. Marcadores comuns (`- `, `* `, `1. `) são retirados, porque o
    agente os escreve por hábito e eles não fazem parte do item.

    Lista vazia é resposta legítima: quem chama decide o que fazer com ela (e o motor
    avisa, em vez de seguir em silêncio)."""
    import json

    if isinstance(valor, (list, tuple)):
        return [_texto(v).strip() for v in valor if _texto(v).strip()]
    texto = _texto(valor).strip()
    if not texto:
        return []
    if texto.startswith("["):
        try:
            dados = json.loads(texto)
            if isinstance(dados, list):
                return [_texto(v).strip() for v in dados if _texto(v).strip()]
        except ValueError:
            pass  # não era JSON — cai para uma linha por item
    itens = []
    for linha in texto.splitlines():
        limpa = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", linha).strip()
        if limpa:
            itens.append(limpa)
    return itens


def para_o_prompt(ficha: dict | None, *, pode_anotar: bool = True) -> str:
    """O bloco que o agente lê. Vazio quando não há ficha (nada a dizer).

    A redação é deliberada: diz que os valores **atravessam a automação inteira**, para
    o agente parar de achar que precisa repetir tudo no texto final — e diz como
    guardar um valor novo, que é a variável de fluxo."""
    ficha = ficha or {}
    if not ficha and not pode_anotar:
        return ""
    linhas = []
    for nome, valor in ficha.items():
        v = _texto(valor)
        rotulo = "o que o gatilho trouxe" if nome == CAMPO_ENTRADA else None
        cabeca = f"- **{nome}**" + (f" ({rotulo})" if rotulo else "") + ":"
        linhas.append(f"{cabeca}\n{v}" if "\n" in v else f"{cabeca} {v}")
    corpo = "\n".join(linhas) if linhas else "_(a ficha ainda está vazia)_"
    bloco = (
        "## A ficha desta execução\n"
        "Estes valores atravessam a automação INTEIRA e chegam a todos os passos, "
        "inclusive aos que rodarem depois de você. Leia-os daqui — são a fonte, mais "
        "confiável que o texto que você recebeu.\n\n"
        f"{corpo}"
    )
    if pode_anotar:
        bloco += (
            "\n\nPara guardar um valor novo (ou corrigir um existente), chame a "
            "ferramenta `anotar`. O que você guardar chega aos passos seguintes **sem** "
            "você precisar repeti-lo no seu texto final — é assim que um dado viaja "
            "pela automação. Guarde o que o próximo passo vai precisar (uma URL "
            "gerada, um total apurado, o nome do cliente), com um nome curto e claro."
        )
    return bloco


# --- Avaliação da regra exata ----------------------------------------------------


def _numero(texto: str) -> float | None:
    """Um número a partir de texto humano: aceita `1.234,56` (pt-BR), `1234.56`,
    `R$ 1.234,56` e `10%`. Devolve None se não for número."""
    t = re.sub(r"[^\d,.\-]", "", str(texto or "")).strip()
    if not t or t in ("-", ".", ","):
        return None
    # pt-BR: vírgula é decimal. Se há os dois separadores, o ÚLTIMO é o decimal.
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") \
            else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _comparavel(texto: str) -> str:
    """Texto para comparação frouxa: sem acento, minúsculo, espaços colapsados."""
    base = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", base).strip().lower()


def regra_valida(regra: dict | None) -> bool:
    """True se a regra tem os campos mínimos para ser avaliada."""
    if not isinstance(regra, dict):
        return False
    if not normalizar_nome(regra.get("campo") or ""):
        return False
    op = regra.get("operador")
    if op not in OPERADORES:
        return False
    if op in OPERADORES_SEM_VALOR:
        return True
    if not str(regra.get("valor") or "").strip():
        return False
    if op == "entre" and not str(regra.get("valor2") or "").strip():
        return False
    return True


def avaliar_regra(regra: dict | None, ficha: dict | None) -> bool | None:
    """Avalia a regra exata de uma saída contra a ficha.

    Devolve True/False, ou **None** quando a regra não pode ser decidida (mal formada,
    ou comparação numérica sobre um valor que não é número). None é uma resposta de
    primeira classe: o motor NÃO trata "não sei" como "não" — ele registra o porquê no
    rastro e deixa a decisão com o agente, em vez de descartar um ramo em silêncio."""
    if not regra_valida(regra):
        return None
    ficha = ficha or {}
    campo = normalizar_nome(regra["campo"])
    op = regra["operador"]
    bruto = ficha.get(campo)
    existe = bruto is not None and str(bruto).strip() != ""

    if op == "preenchido":
        return existe
    if op == "vazio":
        return not existe
    if not existe:
        return False  # comparar com um campo ausente é sempre falso (e é decidível)

    atual = _texto(bruto)
    alvo = str(regra.get("valor") or "")

    if op in OPERADORES_NUMERICOS:
        a = _numero(atual)
        b = _numero(alvo)
        if a is None or b is None:
            return None
        if op == "maior":
            return a > b
        if op == "maior_ou_igual":
            return a >= b
        if op == "menor":
            return a < b
        if op == "menor_ou_igual":
            return a <= b
        c = _numero(str(regra.get("valor2") or ""))
        if c is None:
            return None
        menor, maior = (b, c) if b <= c else (c, b)
        return menor <= a <= maior  # `entre` é INCLUSIVO nas duas pontas

    # Comparação textual: números iguais em grafias diferentes ("10" e "10,00") batem.
    a_num, b_num = _numero(atual), _numero(alvo)
    if op in ("igual", "diferente") and a_num is not None and b_num is not None:
        igual = a_num == b_num
        return igual if op == "igual" else not igual
    a_txt, b_txt = _comparavel(atual), _comparavel(alvo)
    if op == "igual":
        return a_txt == b_txt
    if op == "diferente":
        return a_txt != b_txt
    if op == "contem":
        return b_txt in a_txt
    if op == "nao_contem":
        return b_txt not in a_txt
    return None


def descrever_regra(regra: dict | None) -> str:
    """A regra em português, para o rastro, a tela e o prompt do agente."""
    if not regra_valida(regra):
        return ""
    campo = normalizar_nome(regra["campo"])
    op = regra["operador"]
    verbo = DESCRICAO_OPERADOR[op]
    if op in OPERADORES_SEM_VALOR:
        return f"{campo} {verbo}"
    if op == "entre":
        return f"{campo} {verbo} {regra.get('valor')} e {regra.get('valor2')}"
    return f"{campo} {verbo} {regra.get('valor')}"


def campos_citados(cadeia: dict | None) -> list[str]:
    """Os campos de ficha que as regras exatas do grafo mencionam — para a tela avisar
    'este campo nunca é anotado por ninguém' antes de a automação rodar errado."""
    vistos: list[str] = []
    for no in (cadeia or {}).get("nos") or []:
        for saida in no.get("saidas") or []:
            regra = saida.get("regra")
            if regra_valida(regra):
                nome = normalizar_nome(regra["campo"])
                if nome not in vistos:
                    vistos.append(nome)
    return vistos
