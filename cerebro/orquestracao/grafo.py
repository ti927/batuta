"""Forma canônica do `cadeia` (grafo) e suas transformações puras.

A automação é um GRAFO dirigido (decisão do maestro; PRODUTO §14). Até aqui o
`automacoes.cadeia` guardava o grafo como **dict por agente**:

    {"inicio": "<agente_id>",
     "nos": {"<agente_id>": {"pausa_humano": bool,
                              "saidas": [{"rotulo", "quando", "destino"}]}}}

O construtor visual (handoff `docs/design_handoff_automacoes_grafo/SPEC.md §2`) pede
uma **lista de nós tipados**, separando o `id` do nó do `ref` (agente) — assim o
mesmo agente pode aparecer em vários nós, e há nós que não são agentes (gatilho,
fim, roteador):

    {"inicial": "<id do nó-agente inicial>",
     "nos": [
       {"id","tipo","ref","gate","inicial","gatilho","x","y",
        "saidas": [{"id","rotulo","quando","destino","tone"}]},
       ...
     ]}

Este módulo é **puro** (não toca o banco) e é reusado pelo motor, pela IA criadora
e pela migração de dados:

- `normalizar(cadeia)`   → completa um grafo (canônico, simplificado da IA, ou no
  formato antigo) para a forma canônica acima. Idempotente.
- `converter_linear_para_grafo(antiga)` → traduz o dict-por-agente antigo.
- `indexar(cadeia)`      → índice `{id: nó}` + helpers de travessia para o motor.

Princípio (SPEC §2): `tone`, `x`, `y` são **cosméticos** — o motor nunca depende
deles. O que o motor lê: `inicial`, `nos[].id/tipo/ref/gate`, `saidas[].rotulo/destino`.
"""

import json
from dataclasses import dataclass, field

# Tipos de nó (SPEC §2). gatilho/fim/cada são ESTRUTURAIS (não rodam IA e não contam
# como passo); o motor só roda agente/roteador.
# `cada` é o "Para cada item" (Onda 2): lê uma lista da ficha da execução e repete o
# trecho seguinte uma vez por item, cada repetição como um ramo próprio do grafo.
# `esperar` (Onda 3) é o nó que SEGURA o fluxo por um tempo e o solta depois, sem
# perder a ficha nem o ponto do grafo — o que antes só era possível agendando OUTRA
# execução, que começava do zero e sem contexto nenhum.
# `chamar` (Onda 3) é o sub-fluxo SÍNCRONO: roda outra automação inteira e espera o
# resultado dela para seguir. Diferente do instrumento `agendar_automacao`, que é
# fogo-e-esquece — dispara e nunca fica sabendo o que aconteceu.
TIPOS_VALIDOS = {"gatilho", "agente", "roteador", "fim", "cada", "esperar", "chamar"}
# Tipos que não executam nada por si (nem agente, nem IA). `esperar` entra aqui: ele
# não produz trabalho — só adia. `chamar` também: o trabalho é da automação chamada,
# que tem execução e rastro PRÓPRIOS. (Os dois DEIXAM passo no rastro mesmo assim,
# porque uma pausa de dois dias — ou oito minutos rodando outro time — precisa
# aparecer na linha do tempo; ver `cadeia`.)
TIPOS_ESTRUTURAIS = {"gatilho", "fim", "cada", "esperar", "chamar"}

# Unidades de espera aceitas pelo nó `esperar`, e quanto vale cada uma em minutos.
UNIDADES_ESPERA = {"minutos": 1, "horas": 60, "dias": 60 * 24}
UNIDADE_ESPERA_PADRAO = "minutos"
# Teto de sanidade: 60 dias. Não é limitação técnica — é para um zero a mais não
# transformar "espere 3 dias" numa execução parada até o ano que vem, em silêncio.
MAX_ESPERA_MIN = 60 * 24 * 60


def minutos_de_espera(no: dict | None) -> int:
    """Quantos minutos este nó `esperar` segura o fluxo. Zero quando não há espera
    configurada — e aí o motor apenas segue adiante, em vez de parar para sempre."""
    espera = (no or {}).get("espera") or {}
    try:
        quanto = float(espera.get("quanto") or 0)
    except (TypeError, ValueError):
        return 0
    fator = UNIDADES_ESPERA.get(espera.get("unidade") or UNIDADE_ESPERA_PADRAO, 1)
    return max(0, min(int(quanto * fator), MAX_ESPERA_MIN))


# Quantos níveis de sub-fluxo o motor aceita (A chama B chama C). Não é limitação
# técnica: é o freio de mão contra a recursão. Uma automação que se chama — direta ou
# indiretamente — rodaria para sempre, gastando dinheiro de verdade a cada volta. O
# ciclo em si já é barrado (`sub_fluxo.pode_chamar`); a profundidade barra a árvore
# que cresce sem ciclo nenhum, A→B→C→D→…, que dá no mesmo prejuízo.
MAX_PROFUNDIDADE_CHAMADA = 3


def automacao_chamada(no: dict | None) -> str | None:
    """Qual automação este nó `chamar` roda. `None` quando ainda não foi escolhida —
    e aí o nó FALHA ao ser alcançado, em vez de seguir adiante calado.

    A diferença de tratamento em relação ao `esperar` sem tempo (que segue avisando)
    é deliberada: uma espera sem tempo é inofensiva — o fluxo continua correto, só não
    espera. Um `chamar` sem alvo é trabalho que NÃO foi feito, e seguir adiante
    entregaria ao próximo nó uma entrada vazia como se estivesse tudo certo."""
    alvo = ((no or {}).get("chamar") or {}).get("automacao_id")
    alvo = str(alvo or "").strip()
    return alvo or None
# Cor da aresta na UI (cosmético).
TONES_VALIDOS = {"normal", "ok", "loop", "erro"}

# PAPEL de uma saída (Onda 1 — o grafo vira grafo de verdade). Diferente de `tone`,
# que é cosmético: isto o MOTOR lê.
# - `condicional` (padrão): tem um "quando"; o agente avalia e segue TODAS as atendidas.
# - `erro`: só percorrida se o nó FALHAR (o passo falho fica gravado e o fluxo segue
#   por aqui levando a mensagem do erro, em vez de matar a execução).
# - `senao`: rede de segurança — percorrida só quando NENHUMA condicional foi atendida.
TIPOS_SAIDA = {"condicional", "erro", "senao"}
TIPO_SAIDA_PADRAO = "condicional"


def tipo_da_saida(saida: dict) -> str:
    """O papel de uma saída, com o padrão `condicional` (saídas antigas não o têm)."""
    t = (saida or {}).get("tipo")
    return t if t in TIPOS_SAIDA else TIPO_SAIDA_PADRAO


def separar_saidas(saidas: list[dict] | None) -> tuple[list[dict], list[dict], list[dict]]:
    """Separa as saídas de um nó por papel: (condicionais, de erro, "senão").

    Fonte única desta separação — motor, validação e UI leem o mesmo critério."""
    condicionais, erro, senao = [], [], []
    for s in saidas or []:
        alvo = {"condicional": condicionais, "erro": erro, "senao": senao}[tipo_da_saida(s)]
        alvo.append(s)
    return condicionais, erro, senao
# Tipos de gatilho (espelham `automacoes.tipo_gatilho` e `criacao.ferramentas`).
TIPOS_GATILHO = {"manual", "agendamento", "webhook", "comentario_instagram"}

# Sentinelas de "encerrar a cadeia" aceitas num `destino` (retrocompat com o
# formato antigo, onde destino null/"" significava fim).
DESTINOS_FIM = {None, "", "fim", "FIM"}

# Ids estáveis dos nós estruturais criados na normalização.
ID_GATILHO = "gatilho"
ID_FIM = "fim"


def vazia(cadeia: dict | None) -> bool:
    """True para um rascunho ainda sem grafo montado (cadeia permitida vazia)."""
    if not cadeia:
        return True
    return not cadeia.get("nos") and not cadeia.get("inicio") and not cadeia.get("inicial")


def eh_formato_antigo(cadeia: dict) -> bool:
    """Detecta o formato dict-por-agente (antigo). No novo, `nos` é uma LISTA."""
    nos = cadeia.get("nos")
    if isinstance(nos, dict):
        return True
    # `inicio` (antigo) sem `inicial` (novo) também denuncia o formato antigo.
    return "inicio" in cadeia and "inicial" not in cadeia


def normalizar(cadeia: dict | None) -> dict:
    """Completa qualquer entrada para a forma canônica (lista de nós tipados).

    Aceita: o formato antigo (converte), um grafo "simplificado" da IA (só nós-
    agente + saídas + `gate` + qual é o inicial — o resto é preenchido aqui) ou o
    canônico já pronto (caso em que apenas garante campos faltantes). Idempotente:
    re-normalizar o resultado devolve a mesma estrutura. Rascunho vazio → {}."""
    cadeia = cadeia or {}
    if vazia(cadeia):
        return {}
    if eh_formato_antigo(cadeia):
        return converter_linear_para_grafo(cadeia)
    return _completar(cadeia)


def converter_linear_para_grafo(antiga: dict | None) -> dict:
    """Traduz o dict-por-agente antigo para a forma canônica. O id de cada nó passa
    a ser o próprio `agente_id` (no formato antigo cada agente aparecia uma vez), o
    que mantém os `destino`s existentes válidos. `inicio`→`inicial`,
    `pausa_humano`→`gate`, destino sentinela→nó `fim`."""
    antiga = antiga or {}
    nos_antigos = antiga.get("nos") or {}
    inicio = antiga.get("inicio")
    if not nos_antigos and not inicio:
        return {}
    nos = []
    for agente_id, no in nos_antigos.items():
        no = no or {}
        nos.append(
            {
                "id": agente_id,
                "tipo": "agente",
                "ref": agente_id,
                "gate": bool(no.get("pausa_humano")),
                "saidas": [
                    {
                        "rotulo": s.get("rotulo"),
                        "quando": s.get("quando"),
                        "destino": s.get("destino"),
                        "tipo": s.get("tipo"),
                    }
                    for s in (no.get("saidas") or [])
                ],
            }
        )
    return _completar({"inicial": inicio, "nos": nos})


def _completar(cadeia: dict) -> dict:
    """Núcleo da normalização de um grafo já em lista de nós: garante ids únicos,
    tipos, nó `gatilho` e nó `fim`, ids/tone das saídas, mapeia destino sentinela
    para o nó `fim`, deriva `inicial` e faz um auto-layout das posições faltantes."""
    nos = [dict(n) for n in (cadeia.get("nos") or [])]

    # 1) ids de nó únicos e tipo/saidas garantidos.
    usados: set[str] = set()
    for i, n in enumerate(nos):
        nid = n.get("id") or n.get("ref") or f"no{i}"
        base, k = nid, 1
        while nid in usados:
            nid = f"{base}_{k}"
            k += 1
        n["id"] = nid
        usados.add(nid)
        n.setdefault("tipo", "agente")
        n["saidas"] = [dict(s) for s in (n.get("saidas") or [])]

    # 2) nó inicial: explícito > nó marcado `inicial` > primeiro agente.
    inicial = cadeia.get("inicial")
    if not inicial or inicial not in usados:
        marcados = [n["id"] for n in nos if n.get("inicial")]
        agentes = [n["id"] for n in nos if n.get("tipo") == "agente"]
        inicial = marcados[0] if marcados else (agentes[0] if agentes else None)

    # 3) garante um nó `fim`.
    if not any(n["tipo"] == "fim" for n in nos):
        fid = ID_FIM
        base, k = fid, 1
        while fid in usados:
            fid = f"{base}_{k}"
            k += 1
        nos.append({"id": fid, "tipo": "fim", "saidas": []})
        usados.add(fid)
    id_fim = next(n["id"] for n in nos if n["tipo"] == "fim")

    # 4) garante um nó `gatilho` apontando para o inicial (se há inicial). A saída do
    #    gatilho é DERIVADA do `inicial` (fonte da verdade): re-aponta SEMPRE para ele,
    #    curando gatilhos soltos (sem saída) ou com destino velho/inválido — assim a
    #    seta gatilho→início nunca some e o usuário troca o início mexendo só no `inicial`.
    gatilho = next((n for n in nos if n["tipo"] == "gatilho"), None)
    if inicial and gatilho is None:
        gid = ID_GATILHO
        base, k = gid, 1
        while gid in usados:
            gid = f"{base}_{k}"
            k += 1
        nos.insert(
            0,
            {
                "id": gid,
                "tipo": "gatilho",
                "gatilho": "manual",
                "saidas": [{"rotulo": "inicia o fluxo", "destino": inicial}],
            },
        )
        usados.add(gid)
    elif inicial and gatilho is not None:
        anterior = (gatilho.get("saidas") or [{}])[0]
        nova = {"rotulo": anterior.get("rotulo") or "inicia o fluxo", "destino": inicial}
        if anterior.get("id"):
            nova["id"] = anterior["id"]
        gatilho["saidas"] = [nova]

    # 5) completa saídas (id estável, tone, destino sentinela → nó fim) e marca o
    #    nó inicial.
    for n in nos:
        for j, s in enumerate(n["saidas"]):
            s.setdefault("id", f"{n['id']}-{j}")
            # Papel da saída (o motor lê): condicional (padrão) | erro | senao.
            if s.get("tipo") not in TIPOS_SAIDA:
                s["tipo"] = TIPO_SAIDA_PADRAO
            if s.get("tone") not in TONES_VALIDOS:
                s["tone"] = "normal"
            # A seta de erro é vermelha por definição (cosmético derivado do papel,
            # para o desenho não poder mentir sobre o que o motor vai fazer).
            if s["tipo"] == "erro":
                s["tone"] = "erro"
            if s.get("destino") in DESTINOS_FIM:
                s["destino"] = id_fim
        n["inicial"] = n["id"] == inicial
        n["saidas"] = n["saidas"]

    # 6) auto-layout das posições faltantes (cosmético; preserva o que o usuário moveu).
    _auto_layout(nos, inicial, id_fim)

    return {"inicial": inicial, "nos": nos}


def desenho_que_roda(desenho: dict | None, cadeia_viva: dict | None) -> dict:
    """O grafo que UMA execução roda: a foto tirada no disparo (`execucoes.desenho`),
    caindo para a cadeia VIVA da automação quando não há foto.

    FONTE ÚNICA desta escolha — motor, retomada, aprovação e diagnóstico leem daqui
    (Onda 4, lacunas 28 e 29). Antes, todos liam a cadeia viva: editar a automação com
    uma aprovação em aberto mudava o caminho no meio da corrida, e inspecionar uma
    execução antiga mostrava o fluxo de hoje. A queda existe para as execuções
    anteriores a esta onda, que não têm foto — nelas o comportamento é o de antes."""
    return normalizar(desenho or cadeia_viva or {})


def mesmo_desenho(a: dict | None, b: dict | None) -> bool:
    """Dois desenhos são o MESMO fluxo? Compara só o que o motor lê — nó, tipo, ref e
    saídas (rótulo/quando/regra/destino/tipo) — ignorando o que é cosmético (`x`, `y`,
    `tone`). Mover uma caixa na tela não é "editar o fluxo", e dizer que é encheria a
    inspeção de aviso falso."""
    return _essencia(a) == _essencia(b)


# Campos de um nó/saída que existem só para a tela desenhar. Tirar por EXCLUSÃO (e não
# listar o que interessa) é de propósito: campo novo do motor entra na comparação
# sozinho, em vez de ficar de fora até alguém lembrar de acrescentá-lo aqui.
_COSMETICOS = {"x", "y", "tone"}


def _essencia(cadeia: dict | None) -> str:
    """A parte do grafo que o motor lê, em forma comparável (ordem estável, sem
    cosmético)."""
    c = normalizar(cadeia or {})
    nos = [
        {
            **{k: v for k, v in n.items() if k not in _COSMETICOS and k != "saidas"},
            "saidas": [
                {k: v for k, v in (s or {}).items() if k not in _COSMETICOS}
                for s in (n.get("saidas") or [])
            ],
        }
        for n in sorted(c.get("nos") or [], key=lambda n: str(n.get("id")))
    ]
    return json.dumps(
        {"inicial": c.get("inicial"), "nos": nos},
        sort_keys=True, ensure_ascii=False, default=str,
    )


def sincronizar_gatilho(cadeia: dict | None, tipo_gatilho: str | None) -> dict | None:
    """Espelha no nó `gatilho` do grafo o tipo definido na automação.

    A verdade é o campo de topo `automacoes.tipo_gatilho` — é dele que o motor e o
    agendador disparam. O nó `gatilho` do grafo é a PROJEÇÃO que a tela desenha, e
    até 26/08 ninguém o atualizava ao mudar o gatilho: definir 'agendamento' deixava
    o topo certo e o nó dizendo 'manual' para sempre, duas fontes divergentes para o
    mesmo dado. Puro (não toca o banco), como o resto deste módulo; cadeia vazia ou
    sem nó de gatilho volta intacta."""
    if not cadeia or tipo_gatilho not in TIPOS_GATILHO:
        return cadeia
    nos = cadeia.get("nos")
    if not isinstance(nos, list):
        return cadeia
    for n in nos:
        if isinstance(n, dict) and n.get("tipo") == "gatilho":
            n["gatilho"] = tipo_gatilho
    return cadeia


def _auto_layout(nos: list[dict], inicial: str | None, id_fim: str) -> None:
    """Preenche `x`/`y` só onde faltam, em colunas por profundidade (BFS) a partir
    do gatilho/inicial. Puramente visual: o motor ignora x/y."""
    por_id = {n["id"]: n for n in nos}
    coluna: dict[str, int] = {}

    # raiz da travessia: o nó gatilho, senão o inicial.
    raiz = next((n["id"] for n in nos if n.get("tipo") == "gatilho"), inicial)
    if raiz:
        fila = [(raiz, 0)]
        visto = set()
        while fila:
            nid, c = fila.pop(0)
            if nid in visto or nid not in por_id:
                continue
            visto.add(nid)
            coluna[nid] = min(coluna.get(nid, c), c) if nid in coluna else c
            for s in por_id[nid].get("saidas") or []:
                d = s.get("destino")
                if d in por_id and d not in visto:
                    fila.append((d, c + 1))

    # o nó fim fica numa coluna além de todos.
    max_col = max(coluna.values(), default=0)
    coluna.setdefault(id_fim, max_col + 1)

    # empilhamento vertical por coluna (para nós no mesmo nível não se sobreporem).
    ocupacao: dict[int, int] = {}
    LARGURA, ALTURA, BASE_Y = 300, 150, 240
    for n in nos:
        c = coluna.get(n["id"], 0)
        linha = ocupacao.get(c, 0)
        ocupacao[c] = linha + 1
        if "x" not in n or n.get("x") is None:
            n["x"] = 60 + c * LARGURA
        if "y" not in n or n.get("y") is None:
            n["y"] = BASE_Y + linha * ALTURA


@dataclass
class GrafoIndex:
    """Índice de travessia do grafo para o motor (Fase 2). Não toca o banco."""

    inicial: str | None
    nos: dict[str, dict] = field(default_factory=dict)

    def no(self, nid: str | None) -> dict | None:
        return self.nos.get(nid) if nid is not None else None

    def saidas(self, nid: str | None) -> list[dict]:
        return list((self.no(nid) or {}).get("saidas") or [])

    def eh_fim(self, destino: str | None) -> bool:
        """True se o destino encerra a cadeia: sentinela antiga ou nó `tipo:fim`."""
        if destino in DESTINOS_FIM:
            return True
        n = self.nos.get(destino)
        return bool(n) and n.get("tipo") == "fim"

    def id_fim(self) -> str | None:
        """O id do nó `fim` deste grafo (a normalização sempre cria um).

        Serve a quem precisa PARAR num ponto do grafo em vez de simplesmente sumir:
        o nó `chamar`, ao pausar sem saída desenhada, deixa o ramo apontado para o
        `fim` — assim ele volta do sub-fluxo, encerra e entrega o resultado, em vez
        de virar uma pendência para um nó inexistente."""
        return next((nid for nid, n in self.nos.items() if n.get("tipo") == "fim"), None)


def indexar(cadeia: dict | None) -> GrafoIndex:
    """Constrói o índice `{id: nó}` + `inicial` para o motor percorrer o grafo."""
    cadeia = cadeia or {}
    nos = {n["id"]: n for n in (cadeia.get("nos") or []) if n.get("id")}
    return GrafoIndex(inicial=cadeia.get("inicial"), nos=nos)
