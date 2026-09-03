"""Execução de uma cadeia — o motor caminha o GRAFO por ONDAS (fan-out).

A cadeia é um GRAFO dirigido (PRODUTO §14). A forma canônica (lista de nós tipados)
e suas transformações vivem em `orquestracao.grafo`:

    {"inicial": "<id do nó-agente inicial>",
     "nos": [
       {"id","tipo":"gatilho|agente|roteador|fim","ref":<agente_id>,
        "saidas":[{"rotulo","quando","destino","tipo","tone"}]},
       ...
     ]}

O motor NORMALIZA a cadeia na leitura (`grafo.normalizar`, idempotente): lê tanto a
forma canônica nova quanto o formato antigo (dict-por-agente) sem migração de dados.

## O grafo se comporta como grafo (2026-08-31)

Até aqui o motor tinha um PONTEIRO ÚNICO: um nó com várias saídas seguia UMA delas e
as outras eram descartadas em silêncio — quem desenhava "aprovado → Carrossel" e
"aprovado → Story" via só um dos dois rodar. Agora o motor caminha por **ondas**:

- Cada nó, ao terminar, pode liberar **VÁRIAS** saídas — todas cujas condições foram
  atendidas (o agente as declara pela ferramenta `seguir_para`, que aceita lista).
- Os destinos liberados formam a **próxima onda**. Se dois ramos reencontram o mesmo
  nó na mesma onda, ele roda **UMA vez** com os textos dos dois juntos (junção
  implícita — sem isso, um fluxo em Y publicaria em dobro).
- Cada saída tem um PAPEL (`grafo.TIPOS_SAIDA`): `condicional` (o caso normal),
  `erro` (percorrida quando o nó falha — o passo falho fica gravado e o fluxo segue
  por ela em vez de a execução morrer) e `senao` (rede de segurança, percorrida só
  quando nenhuma condicional foi atendida).
- **Nunca mais escolha silenciosa:** se nada casa e não há `senao`, aquele ramo
  termina com o motivo gravado no rastro. Antes caía calado na primeira saída.
- O teto de passos (`max_passos`) vale por EXECUÇÃO (soma as retomadas), não por
  trecho.

## A ficha da execução (2026-09-01)

Entre os nós trafegava **só texto**, e por isso a entrada do gatilho morria no primeiro
nó: se o agente não repetisse o dado no texto final dele, o dado sumia. Agora cada
execução carrega uma **ficha** (`orquestracao.ficha`) — valores nomeados que:

- nascem com o que o gatilho trouxe e chegam ao prompt de **todos** os nós;
- crescem quando um agente chama `anotar` (a variável de fluxo);
- podem ser comparados pelo MOTOR, via **regra exata** na seta — a IA lê a frase, mas
  quem confere `total entre 1 e 10` é o código, que não erra a borda 10×11.

A ficha é um dicionário único da execução, mutado no lugar conforme os nós rodam. O
motor é serial, então a ordem é determinística: um nó enxerga tudo o que os nós
anteriores (inclusive os da mesma onda, rodados antes dele) anotaram.

## A espera por uma pessoa é do AGENTE (2026-08-31)

Não há mais "portão" (um interruptor no nó) nem "parede" (uma trava da organização).
Quem decide que um momento precisa de gente é o AGENTE, chamando o instrumento
`pedir_aprovacao` porque o markdown dele manda. O motor só reage: se o turno terminou
num pedido de aprovação, a execução vira `aguardando_humano` e devolve as
**pendências** — os ramos da onda que ainda não rodaram —, para a retomada continuar
de onde parou sem perder trabalho.
"""

import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import precos
import segredos_instrumento
from modelos import Agente, AgenteInstrumento, Instrumento
from orquestracao import ficha as ficha_mod
from orquestracao import grafo
from orquestracao import prazo
from orquestracao.agente import executar_agente
from orquestracao.llm import MODELO_PADRAO, construir_modelo

# Guarda contra laço infinito: nº máximo de passos (agentes executados) POR EXECUÇÃO
# — a contagem soma as retomadas (o `ordem_inicial` carrega o que já rodou).
MAX_PASSOS = 25

# Como os textos de vários ramos que reencontram o mesmo nó são juntados na entrada.
SEPARADOR_JUNCAO = "\n\n---\n\n"

# Teste de um nó cujo agente pediu aprovação: o pedido REALMENTE foi enviado (o
# instrumento é real), mas o teste acaba ali. Quem lê o rastro precisa saber das duas
# coisas — senão fica esperando um fluxo que não vai continuar.
AVISO_TESTE_PEDIU_APROVACAO = (
    "Este agente pediu aprovação — e o pedido foi enviado de verdade. Como isto é um "
    "teste de um passo só, o fluxo não ficou esperando resposta: num fluxo de verdade, "
    "ele pararia aqui até alguém responder."
)

# "Para cada item" (Onda 2): teto de itens de UMA lista. Acima disso, os excedentes
# NÃO rodam e o rastro diz quantos ficaram de fora — corte silencioso é proibido.
MAX_ITENS_CADA = 20
# Quanto o teto de passos cresce por item repetido. Repetir é trabalho PLANEJADO, não
# laço: sem esta folga, um for-each de 8 itens morreria no teto de 25 como se fosse um
# bug. O teto de laço segue valendo dentro de cada repetição.
PASSOS_POR_ITEM = 5

# Destinos que encerram a cadeia (mantido para retrocompatibilidade de imports).
_DESTINOS_FIM = grafo.DESTINOS_FIM


class TetoDeTempoExcedido(RuntimeError):
    """A execução passou do teto de TEMPO do fluxo (Onda 3, fatia 2).

    O tempo contado é o de TRABALHO — a soma da duração dos passos —, não o do
    relógio. A diferença não é detalhe: uma execução que espera três dias por uma
    aprovação humana não gastou três dias de trabalho, e matá-la na retomada por causa
    da espera puniria justamente o comportamento que o produto pede."""


class TetoDeCustoExcedido(RuntimeError):
    """A execução passou do teto de custo do fluxo (Onda 4, fatia 4).

    Exceção PRÓPRIA, e não um `RuntimeError` genérico, porque a mensagem precisa
    chegar inteira a quem opera: "passou do teto" é uma decisão do Batuta cumprindo
    uma regra que o consultor escolheu, não um defeito. Quem trata a falha mostra
    este texto, e ele diz quanto gastou, qual era o teto e o que fazer."""


class _Escolha(BaseModel):
    """Saída estruturada do passo de roteamento (fallback, quando o agente não
    declarou o caminho). Devolve TODOS os rótulos cuja condição se aplica."""

    rotulos: list[str] = Field(
        description="Os rótulos EXATOS de TODAS as opções cuja condição foi atendida. "
        "Pode ser mais de uma. Lista vazia se nenhuma se aplica."
    )


def validar_cadeia(
    cadeia: dict, ids_agentes_validos: set[str], *, exigir_condicao: bool = True
) -> None:
    """Valida a estrutura do grafo: tipos de nó, um inicial executável, cada nó
    `agente` apontando para um agente real do time, rótulos de saída únicos por nó,
    destinos que existem e — quando o nó bifurca — a CONDIÇÃO de cada saída
    preenchida. Levanta ValueError com mensagem clara. Cadeia vazia é permitida
    (rascunho). Aceita tanto a forma nova quanto a antiga (normaliza antes).

    `exigir_condicao=False` afrouxa SÓ a exigência da condição — para COPIAR uma
    cadeia que já existia (duplicar time/automação). Automações criadas antes de
    2026-08-31 têm todas as condições vazias; recusar a cópia puniria o usuário por
    um dado legado que ele não escreveu. Ele preenche ao editar."""
    if cadeia is None:
        return
    if not isinstance(cadeia, dict):
        raise ValueError("A cadeia precisa ser um objeto.")
    if grafo.vazia(cadeia):
        return  # rascunho ainda sem cadeia montada

    cadeia = grafo.normalizar(cadeia)
    nos = cadeia.get("nos") or []
    ids_nos = {n["id"] for n in nos}

    # Rascunho permitido: só gatilho/fim, sem nada que rode ainda. Sem nó executável,
    # não há "início" a exigir — o usuário ainda está montando.
    executaveis = [n for n in nos if n.get("tipo") in ("agente", "roteador")]
    if not executaveis:
        return

    inicial = cadeia.get("inicial")
    no_inicial = next((n for n in nos if n["id"] == inicial), None)
    if no_inicial is None or no_inicial.get("tipo") not in ("agente", "roteador"):
        raise ValueError(
            "Esta automação não tem um início que possa rodar. Abra o nó do gatilho "
            "e escolha em 'Começa em' por qual agente o fluxo começa."
        )

    for no in nos:
        tipo = no.get("tipo")
        if tipo not in grafo.TIPOS_VALIDOS:
            raise ValueError(f"Tipo de nó inválido no nó {no['id']}: {tipo}")
        if tipo == "agente":
            ref = no.get("ref")
            if not ref or str(ref) not in ids_agentes_validos:
                raise ValueError(
                    f"O nó {no['id']} aponta para um agente que não é deste time."
                )
        if tipo == "cada":
            # "Para cada item" sem lista não repetiria nada — e falharia só ao rodar.
            if not ficha_mod.normalizar_nome(no.get("lista") or ""):
                nome = no.get("nome") or no["id"]
                raise ValueError(
                    f"O passo '{nome}' repete uma lista, mas não diz QUAL. Abra-o e "
                    "escreva o nome do campo da ficha que contém a lista (o mesmo nome "
                    "que o passo anterior guarda com 'anotar')."
                )
        rotulos: set[str] = set()
        for saida in no.get("saidas") or []:
            rotulo = saida.get("rotulo")
            if not rotulo:
                raise ValueError(f"Há uma saída sem 'rotulo' no nó {no['id']}.")
            if rotulo in rotulos:
                raise ValueError(f"Rótulo de saída repetido no nó {no['id']}: {rotulo}")
            rotulos.add(rotulo)
            destino = saida.get("destino")
            if destino not in ids_nos:
                raise ValueError(
                    f"Destino inválido no nó {no['id']} (saída {rotulo}): {destino}"
                )

        # A CONDIÇÃO é obrigatória quando o nó bifurca. Era o buraco que fazia o
        # motor escolher no escuro: o editor só tinha caixa para o `rotulo`, então
        # todo `quando` ficava vazio e o agente recebia nomes sem significado.
        # Nós estruturais (gatilho) e saídas de erro/"senão" não têm condição.
        condicionais, _, _ = grafo.separar_saidas(no.get("saidas"))
        if exigir_condicao and tipo in ("agente", "roteador") and len(condicionais) >= 2:
            sem_condicao = [
                s["rotulo"] for s in condicionais if not (s.get("quando") or "").strip()
            ]
            if sem_condicao:
                nome = no.get("nome") or no["id"]
                raise ValueError(
                    f"O passo '{nome}' bifurca em {len(condicionais)} caminhos, mas "
                    f"{'a saída' if len(sem_condicao) == 1 else 'as saídas'} "
                    + ", ".join(f"'{r}'" for r in sem_condicao)
                    + " não diz quando seguir por ela. Preencha 'Siga por aqui "
                    "quando…' em cada saída — é por essa frase que o agente decide."
                )


def _carregar_cinto(sessao: Session, agente_id: uuid.UUID) -> list[Instrumento]:
    cinto = list(
        sessao.scalars(
            select(Instrumento)
            .join(
                AgenteInstrumento,
                AgenteInstrumento.instrumento_id == Instrumento.id,
            )
            .where(AgenteInstrumento.agente_id == agente_id)
        )
    )
    # Fase 7-B: decifra e anexa os segredos de cada instrumento (em memória), para
    # a execução mesclá-los na config sem que eles fiquem em claro no banco.
    segredos_instrumento.anexar_aos_instrumentos(sessao, cinto)
    return cinto


def _rotear_por_llm(saida_texto: str, saidas: list[dict]) -> tuple[list[dict], dict]:
    """Fallback de roteamento: quando o agente NÃO declarou o caminho (automação
    antiga, modelo que ignorou a ferramenta), uma LLM lê a condição de cada saída e
    devolve TODAS as que se aplicam ao texto produzido.

    Devolve (saídas escolhidas, uso). **Lista vazia é uma resposta legítima** — não
    existe mais "cai na primeira": quando nada casa, quem decide é a saída `senão`,
    e na falta dela o ramo termina com o motivo gravado no rastro."""
    opcoes = "\n".join(
        f'- "{s["rotulo"]}": {s.get("quando") or "(sem condição escrita)"}'
        for s in saidas
    )
    prompt = (
        "Você é um roteador de fluxo. Dada a SAÍDA de um agente e as OPÇÕES de "
        "caminho, devolva os rótulos de TODAS as opções cuja condição foi atendida "
        "(pode ser mais de uma; pode ser nenhuma).\n\n"
        f"SAÍDA DO AGENTE:\n{saida_texto}\n\n"
        f"OPÇÕES:\n{opcoes}\n\n"
        "Responda apenas com os rótulos exatos das opções atendidas."
    )
    modelo = construir_modelo(None).with_structured_output(_Escolha, include_raw=True)
    resposta = modelo.invoke(prompt)
    escolha = resposta["parsed"]
    u = getattr(resposta["raw"], "usage_metadata", None) or {}
    uso = {
        "modelo": MODELO_PADRAO,  # o roteamento usa sempre o modelo padrão
        "tokens_entrada": u.get("input_tokens", 0),
        "tokens_saida": u.get("output_tokens", 0),
    }
    por_rotulo = {s["rotulo"]: s for s in saidas}
    escolhidas = [
        por_rotulo[r] for r in (getattr(escolha, "rotulos", None) or []) if r in por_rotulo
    ]
    return escolhidas, uso


def _escolher_saida(saida_texto: str, saidas: list[dict]) -> tuple[dict, dict]:
    """Escolhe UMA saída (usado pela retomada mecânica de portão, onde a resposta do
    humano decide um caminho só). Mantido sobre `_rotear_por_llm`."""
    escolhidas, uso = _rotear_por_llm(saida_texto, saidas)
    return (escolhidas[0] if escolhidas else saidas[0]), uso


def _decidir_por_regra(
    condicionais: list[dict], ficha: dict
) -> tuple[list[dict], list[dict], list[dict]]:
    """Separa as saídas condicionais entre as que o MOTOR decide (regra exata sobre a
    ficha) e as que ficam com o AGENTE.

    Devolve `(escolhidas_pela_regra, para_o_agente, rastro)`. O `rastro` guarda cada
    regra avaliada e o resultado — sem ele, um ramo descartado por comparação numérica
    seria invisível para quem depois pergunta "por que não seguiu por ali?".

    Uma regra que **não pode ser decidida** (campo ausente do tipo errado, valor que não
    é número) não vira "não": volta para o agente, com o motivo no rastro. Silenciar um
    "não sei" como "não" é o tipo de escolha muda que esta frente existe para acabar."""
    pela_regra: list[dict] = []
    para_o_agente: list[dict] = []
    rastro: list[dict] = []
    for s in condicionais:
        regra = s.get("regra")
        if not ficha_mod.regra_valida(regra):
            para_o_agente.append(s)
            continue
        resultado = ficha_mod.avaliar_regra(regra, ficha)
        rastro.append({
            "rotulo": s.get("rotulo"),
            "regra": ficha_mod.descrever_regra(regra),
            "resultado": resultado,
        })
        if resultado is True:
            pela_regra.append(s)
        elif resultado is None:
            para_o_agente.append(s)
    return pela_regra, para_o_agente, rastro


def _abrir_repeticoes(
    no: dict, no_id: str, idx, proxima: dict, ficha_do_ramo: dict, ramo: str,
    extra: dict, *, entrada: str, avisos: list[str], acumuladores: dict[str, str],
    ao_terminar,
) -> int:
    """O nó "Para cada item": lê uma lista da ficha e abre UM RAMO POR ITEM.

    Cada repetição percorre o mesmo trecho do grafo, mas como ramo próprio (chave
    distinta na onda), então elas não se fundem na junção implícita. Cada uma enxerga o
    seu item na ficha (`item`, `item_numero`, `item_total`), e o que produzir volta,
    opcionalmente, para um campo acumulador — a agregação.

    Devolve quanto o teto de passos da execução deve CRESCER. Repetir 8 itens é
    trabalho planejado, não laço: contar cada repetição contra o mesmo teto de 25
    faria o for-each morrer como se fosse um bug. O teto de laço continua valendo
    DENTRO de cada repetição.

    Nada aqui é silencioso: lista vazia, campo ausente ou itens acima do teto viram
    aviso no rastro (§12-A)."""
    nome = no.get("nome") or "Para cada item"
    campo_lista = ficha_mod.normalizar_nome(no.get("lista") or "")
    saidas = no.get("saidas") or []
    destino = saidas[0].get("destino") if saidas else None

    if not campo_lista:
        avisos.append(
            f"O passo '{nome}' não diz QUAL lista percorrer. Abra a automação e "
            "escolha, nesse passo, o campo da ficha que contém a lista."
        )
        return 0
    if campo_lista not in ficha_do_ramo:
        avisos.append(
            f"O passo '{nome}' ia percorrer a lista '{campo_lista}', mas esse campo "
            "não está na ficha desta execução. Garanta que um passo anterior o guarde "
            "com a ferramenta `anotar`."
        )
        return 0

    itens = ficha_mod.como_lista(ficha_do_ramo.get(campo_lista))
    if not itens:
        avisos.append(
            f"O passo '{nome}' percorreria a lista '{campo_lista}', que veio vazia — "
            "nada a repetir."
        )
        return 0
    if len(itens) > MAX_ITENS_CADA:
        # NUNCA cortar em silêncio: quem lê o rastro precisa saber que sobrou fila.
        avisos.append(
            f"O passo '{nome}' recebeu {len(itens)} itens em '{campo_lista}' e o "
            f"limite é {MAX_ITENS_CADA}. Os {len(itens) - MAX_ITENS_CADA} últimos NÃO "
            "foram processados."
        )
        itens = itens[:MAX_ITENS_CADA]

    if destino is None or idx.eh_fim(destino):
        # Não há trecho a repetir: cada item vira, ele mesmo, um resultado.
        for item_texto in itens:
            ao_terminar([item_texto], ramo)
        return 0

    campo_item = ficha_mod.normalizar_nome(no.get("item_em") or "") or "item"
    campo_acumulo = ficha_mod.normalizar_nome(no.get("acumular_em") or "")
    for i, item_texto in enumerate(itens, start=1):
        ramo_item = f"{ramo}/{no_id}#{i}" if ramo else f"{no_id}#{i}"
        if campo_acumulo:
            acumuladores[ramo_item] = campo_acumulo
        _empilhar(
            proxima, destino, [entrada], ramo=ramo_item,
            extra={
                **extra,
                campo_item: item_texto,
                "item_numero": str(i),
                "item_total": str(len(itens)),
            },
        )
    return (len(itens) - 1) * PASSOS_POR_ITEM


def _empilhar(
    proxima: dict, destino: str, textos: list[str], *, ramo: str = "", extra: dict | None = None
) -> None:
    """Enfileira textos para um destino na PRÓXIMA onda.

    A chave é o par **(ramo, destino)**, não só o destino. Dois caminhos do MESMO ramo
    que reencontram o mesmo nó fazem a junção implícita (o nó roda uma vez, com os
    textos juntos — sem isso, um Y publicaria em dobro). Já dois ramos DIFERENTES no
    mesmo nó são trabalhos distintos e rodam separados: é assim que o "Para cada item"
    repete o trecho por item sem que as repetições se fundam numa só."""
    chave = (ramo, destino)
    slot = proxima.setdefault(chave, {"entradas": [], "extra": dict(extra or {})})
    slot["entradas"].extend(textos)
    slot["extra"].update(extra or {})


def _como_itens(mapa: dict) -> list[dict]:
    """A onda como lista de itens serializáveis (é também o formato das pendências
    guardadas quando a execução pausa). `ramo`/`extra` só aparecem quando existem, para
    as pendências de um fluxo comum ficarem byte-idênticas às de antes da Onda 2."""
    itens = []
    for (ramo, nid), slot in mapa.items():
        item = {"no": nid, "entradas": list(slot["entradas"])}
        if ramo:
            item["ramo"] = ramo
        if slot["extra"]:
            item["extra"] = dict(slot["extra"])
        itens.append(item)
    return itens


def executar_cadeia(
    sessao: Session,
    cadeia: dict,
    entrada: str,
    *,
    no_inicial: str | None = None,
    frente_inicial: list[dict] | None = None,
    ficha: dict | None = None,
    ordem_inicial: int = 0,
    max_passos: int = MAX_PASSOS,
    teto_usd: float = 0.0,
    custo_inicial: float = 0.0,
    teto_min_passo: int = 0,
    teto_min_execucao: int = 0,
    tempo_inicial_s: float = 0.0,
    so_um_passo: bool = False,
    registrar_passo: Callable[[dict, int], None] | None = None,
    cancelado: Callable[[], bool] | None = None,
) -> dict:
    """Caminha o grafo por ondas, até acabarem os ramos OU uma pausa para humano.

    Devolve um dicionário com `estado`:
    - "concluida": todos os ramos terminaram. `resultado` tem o texto final (os
      textos dos ramos que chegaram ao fim, juntos); `avisos` lista os ramos que
      terminaram sem caminho.
    - "aguardando_humano": o agente pediu aprovação. `pergunta` é o que ele
      apresentou à pessoa;
      `pendentes` são os ramos da onda que ainda não rodaram (a retomada os leva
      adiante para nenhum trabalho se perder).
    - "cancelada": o operador cancelou entre passos.
    `ordem` é o número do último passo; `passos`, o rastro deste trecho.

    `no_inicial` começa de um nó só (retomada simples); `frente_inicial` começa de
    vários ramos ao mesmo tempo (retomada com pendências), no formato
    `[{"no": <id>, "entradas": [<texto>, ...]}, ...]`.

    `ficha` é a ficha da execução (`orquestracao.ficha`), MUTADA no lugar: quem chama
    passa a ficha persistida (retomada) e a lê de volta ao fim. Omitida, nasce da
    própria entrada — assim todo caminho tem ficha, inclusive os testes."""
    idx = grafo.indexar(grafo.normalizar(cadeia or {}))
    ficha_exec = ficha if ficha is not None else ficha_mod.nova(entrada)

    if frente_inicial:
        onda = [
            {
                "no": i["no"], "entradas": list(i.get("entradas") or []),
                "ramo": i.get("ramo") or "", "extra": dict(i.get("extra") or {}),
            }
            for i in frente_inicial
            if i.get("no")
        ]
    else:
        onda = [{"no": no_inicial or idx.inicial, "entradas": [entrada],
                 "ramo": "", "extra": {}}]
    if not onda or idx.no(onda[0]["no"]) is None:
        raise ValueError("Cadeia inválida: nó inicial ausente ou fora do grafo.")

    passos: list[dict] = []
    avisos: list[str] = []
    resultados: list[str] = []
    ordem = ordem_inicial
    # Teto de custo POR EXECUÇÃO (Onda 4, fatia 4). `custo_inicial` traz o que já foi
    # gasto antes desta rodada — como o `ordem_inicial` faz com os passos —, então o
    # teto atravessa a espera de uma aprovação em vez de zerar a cada retomada.
    custo_usd = custo_inicial
    # Tempo de TRABALHO já gasto (segundos), somando as retomadas — como o custo. Não
    # é tempo de relógio: a espera por uma aprovação não conta.
    tempo_s = tempo_inicial_s
    # Campo da ficha onde cada ramo de "Para cada item" deposita o que produziu
    # (`{ramo: campo}`). É a AGREGAÇÃO: as repetições terminam em momentos diferentes e
    # cada uma soma o seu resultado no mesmo campo, na ordem em que terminam.
    acumuladores: dict[str, str] = {}

    def _terminou(textos: list[str], ramo: str) -> None:
        """Um ramo chegou ao fim: o texto vira resultado e, se este ramo pertence a um
        "Para cada item" com acúmulo, também entra no campo acumulador da ficha."""
        resultados.extend(textos)
        campo = acumuladores.get(ramo)
        if campo:
            anterior = (ficha_exec.get(campo) or "").strip()
            juntos = [t for t in ([anterior] if anterior else []) + list(textos) if t]
            ficha_mod.anotar(ficha_exec, campo, SEPARADOR_JUNCAO.join(juntos))

    while onda:
        proxima: dict = {}
        for pos, item in enumerate(onda):
            # Cancelamento cooperativo (Tarefa 5.5): entre passos, se o operador
            # cancelou, paramos aqui — os passos já feitos ficam registrados.
            if cancelado is not None and cancelado():
                return {
                    "estado": "cancelada", "ordem": ordem, "passos": passos,
                    "ficha": ficha_exec,
                }

            no_atual = item["no"]
            entradas = item["entradas"] or [""]
            ramo = item.get("ramo") or ""
            extra = dict(item.get("extra") or {})
            no = idx.no(no_atual)
            if no is None:
                raise ValueError(f"Nó da cadeia não encontrado: {no_atual}")
            tipo = no.get("tipo", "agente")

            # A ficha que ESTE ramo enxerga: a da execução, coberta pelos valores
            # próprios da repetição ("Para cada item"). Fora de um for-each, `extra` é
            # vazio e isto é exatamente a ficha da execução.
            ficha_do_ramo = {**ficha_exec, **extra} if extra else ficha_exec

            # Nós estruturais: o `fim` encerra aquele ramo; o `gatilho` apenas
            # repassa para a sua saída; o `cada` abre um ramo por item. Nenhum dos três
            # conta como passo (não roda IA).
            if tipo == "fim":
                _terminou(entradas, ramo)
                continue
            if tipo == "gatilho":
                saidas_g = no.get("saidas") or []
                destino = saidas_g[0].get("destino") if saidas_g else None
                if not destino or idx.eh_fim(destino):
                    _terminou(entradas, ramo)
                else:
                    _empilhar(proxima, destino, entradas, ramo=ramo, extra=extra)
                continue
            if tipo == "cada":
                entrada_cada = (
                    entradas[0] if len(entradas) == 1
                    else SEPARADOR_JUNCAO.join(entradas)
                )
                max_passos += _abrir_repeticoes(
                    no, no_atual, idx, proxima, ficha_do_ramo, ramo, extra,
                    entrada=entrada_cada, avisos=avisos, acumuladores=acumuladores,
                    ao_terminar=_terminou,
                )
                continue

            ordem += 1
            # Teto POR EXECUÇÃO: `ordem_inicial` traz o que já rodou antes da
            # retomada, então um laço que atravessa portões também é contido.
            if ordem > max_passos:
                raise RuntimeError(
                    f"Máximo de passos ({max_passos}) excedido — possível laço infinito."
                )

            entrada_atual = (
                entradas[0] if len(entradas) == 1 else SEPARADOR_JUNCAO.join(entradas)
            )
            saidas = no.get("saidas") or []
            condicionais, saidas_erro, saidas_senao = grafo.separar_saidas(saidas)
            iniciado_em = datetime.now(timezone.utc)
            # Identidade do nó resolvida ANTES de rodar: se ele falhar, o passo falho
            # precisa dizer QUEM falhou (é o nome que aparece na timeline e no aviso
            # da falha). Sem isto o passo falho saía anônimo, justo quando importa.
            id_agente, nome_do_no = _identidade_do_no(sessao, no, tipo)

            # Prazo DESTE passo (Onda 3, fatia 2): o ajuste do nó vence o do fluxo —
            # mesma cascata do resto do comportamento. O agente pergunta por ele antes
            # de cada ação; o limite de rede de cada instrumento segue valendo por
            # dentro, para UMA chamada.
            minutos_do_passo = (no.get("config") or {}).get("teto_min_passo")
            if minutos_do_passo is None:
                minutos_do_passo = teto_min_passo
            try:
                with prazo.usar_prazo(minutos_do_passo):
                    executado = _rodar_no(
                        sessao, no, no_atual, tipo, entrada_atual,
                        condicionais=condicionais, ficha=ficha_do_ramo,
                    )
            except Exception as e:
                # O nó falhou. O passo falho é GRAVADO (antes a timeline pulava do
                # último passo bom direto para "falhou", sem dizer onde) e, se o nó
                # tem uma saída de ERRO desenhada, o fluxo segue por ela levando a
                # mensagem — a falha vira um caminho, não o fim da execução.
                finalizado_em = datetime.now(timezone.utc)
                passo_falho = _montar_passo(
                    no_atual, tipo, agente_id=id_agente,
                    agente_nome=nome_do_no,
                    entrada=entrada_atual, saida=f"Falhou: {e}",
                    instrumentos=[], erros_instrumentos=[], uso=[],
                    escolhidas=[], motivo=None, iniciado_em=iniciado_em,
                    finalizado_em=finalizado_em, estado="falhou", erro=str(e),
                    ficha=dict(ficha_do_ramo),
                )
                passos.append(passo_falho)
                if registrar_passo is not None:
                    registrar_passo(passo_falho, ordem)
                if not saidas_erro:
                    raise
                texto_erro = (
                    f"O passo anterior ('{passo_falho['agente_nome']}') falhou.\n"
                    f"Erro: {e}\n\nEntrada que ele recebeu:\n{entrada_atual}"
                )
                for s in saidas_erro:
                    _seguir(
                        idx, proxima, s, [texto_erro],
                        ramo=ramo, extra=extra, ao_terminar=_terminou,
                    )
                continue

            finalizado_em = datetime.now(timezone.utc)
            saida_texto = executado["saida"]
            uso_passo = executado["uso"]

            # O que este nó guardou na FICHA entra ANTES de decidir o caminho: é assim
            # que "anote o total" e a seta "total entre 1 e 10" funcionam no mesmo passo.
            # Guardamos o nome CANÔNICO devolvido por `anotar` (não o que o agente
            # digitou): é esse que a regra da seta compara, e é ele que precisa aparecer
            # no rastro — senão quem depurar procura por um campo que não existe.
            anotou: list[str] = []
            for campo, valor in (executado.get("anotacoes") or {}).items():
                nome, _ = ficha_mod.anotar(ficha_exec, campo, valor)
                if nome:
                    anotou.append(nome)
            if anotou and extra:
                # Dentro de um "Para cada item", o que o nó anotou entra na visão DESTE
                # ramo também — senão a regra da seta logo abaixo leria a ficha antiga.
                ficha_do_ramo = {**ficha_exec, **extra}

            # --- A decisão de caminho -------------------------------------------
            # Esperando uma pessoa: quem escolhe o caminho é a resposta dela, na
            # retomada — aqui não se decide nada.
            escolhidas: list[dict] = []
            motivo = executado["motivo"]
            aviso: str | None = None
            regras_avaliadas: list[dict] = []
            pausa = executado["pausa"]
            if not pausa:
                # Regra exata (Onda 2): a saída que tem regra é decidida pelo CÓDIGO,
                # contra a ficha. As demais seguem com o agente. Enquanto nenhuma saída
                # tiver regra, tudo se comporta exatamente como antes — é o caso de
                # todas as automações existentes.
                pela_regra, do_agente, regras_avaliadas = _decidir_por_regra(
                    condicionais, ficha_do_ramo
                )
                escolhidas = list(pela_regra)
                tem_regra = bool(regras_avaliadas)
                if do_agente and len(do_agente) == 1 and not tem_regra:
                    # Saída única e sem regra: segue, como sempre seguiu.
                    escolhidas += do_agente
                elif do_agente:
                    por_rotulo = {s["rotulo"]: s for s in do_agente if s.get("rotulo")}
                    declarados = [r for r in executado["ramos"] if r in por_rotulo]
                    if declarados:
                        escolhidas += [por_rotulo[r] for r in declarados]
                    elif len(do_agente) >= 2 or tem_regra:
                        # O agente não declarou (ou declarou rótulo inexistente):
                        # a LLM roteadora lê as condições. Pode devolver várias — e
                        # pode devolver nenhuma, que agora é resposta legítima.
                        escolhidas_llm, uso_rot = _rotear_por_llm(saida_texto, do_agente)
                        escolhidas += escolhidas_llm
                        uso_passo.append(uso_rot)
                if not escolhidas and saidas_senao:
                    escolhidas = list(saidas_senao)
                    motivo = motivo or "nenhuma condição foi atendida"
                if not escolhidas:
                    # NUNCA mais escolha silenciosa: o ramo termina aqui e o motivo
                    # fica no rastro (antes caía calado na primeira saída). O aviso diz
                    # o nome do AGENTE e o que fazer — quem lê isto está tentando
                    # entender por que "não aconteceu nada".
                    sem_condicao = [
                        s["rotulo"] for s in condicionais
                        if not (s.get("quando") or "").strip()
                        and not ficha_mod.regra_valida(s.get("regra"))
                    ]
                    nao_bateram = [
                        f"{r['rotulo']} ({r['regra']})"
                        for r in regras_avaliadas if r["resultado"] is False
                    ]
                    indecisas = [
                        f"{r['rotulo']} ({r['regra']})"
                        for r in regras_avaliadas if r["resultado"] is None
                    ]
                    if not condicionais:
                        porque = "ele não tem saída ligada — o fluxo acaba aqui."
                    elif indecisas:
                        # §12-A: um "não sei" que vira "não" em silêncio é o pior caso.
                        # Diz qual regra não deu para conferir e por quê.
                        porque = (
                            "não foi possível conferir a regra exata de "
                            + ", ".join(indecisas)
                            + " — o campo não está na ficha desta execução ou o valor "
                            "não é um número. Confira se algum passo anterior anota "
                            "esse campo (ferramenta `anotar`)."
                        )
                    elif nao_bateram and len(nao_bateram) == len(condicionais):
                        porque = (
                            "a regra exata de cada saída não bateu com a ficha: "
                            + ", ".join(nao_bateram)
                            + ". Não há saída 'se nenhuma das outras' para pegar o resto."
                        )
                    elif len(sem_condicao) == len(condicionais):
                        porque = (
                            "nenhuma das saídas diz QUANDO seguir por ela, então não "
                            "havia como decidir. Abra a automação e preencha 'Siga por "
                            f"aqui quando…' em cada saída ({', '.join(sem_condicao)})."
                        )
                    else:
                        porque = (
                            "nenhuma das condições das saídas foi atendida e não há "
                            "saída 'se nenhuma das outras'."
                        )
                    aviso = (
                        f"O passo '{nome_do_no}' terminou sem seguir por nenhum "
                        f"caminho: {porque}"
                    )
                    avisos.append(aviso)

            passo = _montar_passo(
                no_atual, tipo, espera=bool(pausa), aprovacao=pausa or None,
                agente_id=executado["agente_id"], agente_nome=executado["agente_nome"],
                entrada=entrada_atual, saida=saida_texto,
                instrumentos=executado["instrumentos"],
                erros_instrumentos=executado["erros_instrumentos"],
                uso=uso_passo, escolhidas=escolhidas, motivo=motivo,
                iniciado_em=iniciado_em, finalizado_em=finalizado_em,
                aviso=aviso, regras=regras_avaliadas, anotou=sorted(anotou),
                ficha=dict(ficha_do_ramo),
            )
            passos.append(passo)
            if registrar_passo is not None:
                registrar_passo(passo, ordem)

            # Teto de custo (Onda 4, fatia 4): a conta é fechada DEPOIS de gravar o
            # passo — o trabalho já foi pago e precisa aparecer no rastro — e ANTES de
            # abrir o próximo, que é o gasto que ainda dá para evitar. Soma tudo o que
            # o passo consumiu, inclusive a chamada da IA roteadora.
            # Teto de TEMPO da execução — irmão do de custo, e conferido no mesmo
            # ponto. Soma a duração dos passos (tempo de TRABALHO), nunca o relógio:
            # a espera por uma aprovação não é trabalho e não pode consumir o teto.
            tempo_s += max(0.0, (finalizado_em - iniciado_em).total_seconds())
            if teto_min_execucao and tempo_s > teto_min_execucao * 60:
                raise TetoDeTempoExcedido(
                    f"A execução passou do tempo máximo do fluxo: já trabalhou "
                    f"{int(tempo_s // 60)} min, e o teto é {teto_min_execucao} min. Os "
                    f"passos já feitos ficam no rastro. Se o fluxo é demorado por "
                    f"natureza, aumente o teto em Fluxo › Limites da execução."
                )

            custo_usd += sum(precos.custo_de_entrada(e) for e in uso_passo)
            if teto_usd and custo_usd > teto_usd:
                # Mensagem CURTA de propósito: ela viaja no aviso pelo canal do time,
                # que corta o motivo em 300 caracteres — e o que não pode ser cortado
                # é o "o que fazer" do fim. Por isso não repete o nome do passo, que o
                # aviso já diz numa linha própria.
                raise TetoDeCustoExcedido(
                    f"A execução passou do teto de custo do fluxo: gastou "
                    f"US$ {custo_usd:.2f}, e o teto é US$ {teto_usd:.2f}. Os passos já "
                    f"feitos ficam no rastro. Se o fluxo é caro por natureza, aumente "
                    f"o teto em Fluxo › Limites da execução; se não, veja na aba Uso "
                    f"qual passo gastou mais."
                )

            # "Testar este nó" (Onda 4, fatia 5): rodou o nó pedido, acabou. Não segue
            # as setas nem espera aprovação — inclusive quando o agente CHAMOU
            # `pedir_aprovacao`: a mensagem já saiu (não dá para desenviar), mas deixar
            # uma aprovação pendente nascida de um teste seria pedir ao aprovador que
            # decidisse sobre algo que não vai a lugar nenhum. O rastro diz o que houve.
            if so_um_passo:
                return {
                    "estado": "concluida",
                    "resultado": saida_texto,
                    "ordem": ordem,
                    "passos": passos,
                    "avisos": avisos + ([AVISO_TESTE_PEDIU_APROVACAO] if pausa else []),
                    "ficha": ficha_exec,
                }

            # O agente PEDIU APROVAÇÃO (instrumento `pedir_aprovacao`): a execução
            # para aqui, e o que segue é decidido quando a pessoa responder. As
            # PENDÊNCIAS (ramos desta onda que ainda não rodaram + os já liberados)
            # vão junto, para a retomada continuar sem perder trabalho.
            if pausa:
                pendentes = [
                    {
                        "no": i["no"], "entradas": list(i["entradas"]),
                        **({"ramo": i["ramo"]} if i.get("ramo") else {}),
                        **({"extra": dict(i["extra"])} if i.get("extra") else {}),
                    }
                    for i in onda[pos + 1 :]
                ] + _como_itens(proxima)
                return {
                    "estado": "aguardando_humano",
                    "pergunta": saida_texto,
                    "no_pausado": no_atual,
                    "pendentes": pendentes,
                    "ordem": ordem,
                    "passos": passos,
                    "avisos": avisos,
                    "ficha": ficha_exec,
                }

            if not escolhidas:
                _terminou([saida_texto], ramo)
                continue
            for s in escolhidas:
                _seguir(
                    idx, proxima, s, [saida_texto],
                    ramo=ramo, extra=extra, ao_terminar=_terminou,
                )

        onda = _como_itens(proxima)

    return {
        "estado": "concluida",
        "resultado": SEPARADOR_JUNCAO.join(resultados) if resultados else "",
        "avisos": avisos,
        "ordem": ordem,
        "passos": passos,
        "ficha": ficha_exec,
    }


def _seguir(
    idx, proxima: dict, saida: dict, textos: list[str], *,
    ramo: str = "", extra: dict | None = None, ao_terminar,
) -> None:
    """Encaminha os textos pela saída: destino que encerra fecha o ramo (`ao_terminar`,
    que também alimenta o acumulador do "Para cada item"); senão, entra na próxima
    onda, preservando o ramo e os valores próprios dele."""
    destino = saida.get("destino")
    if destino is None or idx.eh_fim(destino):
        ao_terminar(textos, ramo)
    else:
        _empilhar(proxima, destino, textos, ramo=ramo, extra=extra)


def _identidade_do_no(sessao: Session, no: dict, tipo: str) -> tuple[str | None, str]:
    """(id do agente, nome legível) de um nó, resolvidos SEM rodar nada. Um nó de
    agente cujo `ref` não existe mais devolve o id mesmo assim: o passo falho aponta
    para o agente que sumiu, que é exatamente a informação útil."""
    if tipo != "agente":
        return None, (no.get("nome") or "roteador")
    ref = no.get("ref")
    if not ref:
        return None, (no.get("nome") or "passo sem agente")
    agente = sessao.get(Agente, uuid.UUID(str(ref)))
    return str(ref), (agente.nome if agente else "(agente removido)")


def _rodar_no(
    sessao: Session,
    no: dict,
    no_id: str,
    tipo: str,
    entrada_atual: str,
    *,
    condicionais: list[dict],
    ficha: dict | None = None,
) -> dict:
    """Roda UM nó (agente ou roteador) e devolve o que ele produziu, já num formato
    uniforme. Não decide caminho — isso é do chamador."""
    if tipo == "roteador":
        # Roteador: não roda agente nem produz conteúdo — só classifica a entrada
        # sobre as suas saídas e segue. A entrada passa adiante intacta. Com regra
        # exata nas saídas ele vira uma chave puramente determinística (nenhuma IA).
        return {
            "saida": entrada_atual, "agente_id": None,
            "agente_nome": no.get("nome") or "roteador",
            "instrumentos": [], "erros_instrumentos": [], "uso": [],
            "mensagens_enviadas": {}, "ramos": [], "motivo": None, "pausa": None,
            "anotacoes": {},
        }

    ref = no.get("ref")
    agente = sessao.get(Agente, uuid.UUID(str(ref))) if ref else None
    if agente is None:
        raise ValueError(
            f"O nó '{no_id}' aponta para um agente que não existe mais "
            f"(ref {ref}). Edite a automação e troque ou remova esse passo."
        )
    cinto = _carregar_cinto(sessao, agente.id)
    # O agente enxerga as saídas CONDICIONAIS (não as de erro/"senão", que são do
    # motor) e DECLARA por quais o fluxo segue — podendo declarar VÁRIAS.
    resultado = executar_agente(
        agente, cinto, entrada_atual, saidas=condicionais, ficha=ficha
    )
    return {
        "saida": resultado["saida"],
        "agente_id": str(agente.id),
        "agente_nome": agente.nome,
        "instrumentos": resultado["instrumentos_acionados"],
        "erros_instrumentos": resultado.get("erros_instrumentos") or [],
        "uso": list(resultado.get("uso") or []),
        "mensagens_enviadas": resultado.get("mensagens_enviadas") or {},
        # Preenchido = o agente chamou `pedir_aprovacao` e está esperando uma pessoa.
        "pausa": (resultado.get("aprovacao") or None) if resultado.get("pausado") else None,
        # `ramos_escolhidos` é a lista (fan-out); `ramo_escolhido` (singular) segue
        # aceito para quem ainda devolve um caminho só.
        "ramos": list(resultado.get("ramos_escolhidos") or [])
        or ([resultado["ramo_escolhido"]] if resultado.get("ramo_escolhido") else []),
        "motivo": resultado.get("motivo_ramo"),
        # O que ele guardou na ficha neste turno (ferramenta `anotar`).
        "anotacoes": dict(resultado.get("anotacoes") or {}),
    }


def _montar_passo(
    no_id: str, tipo: str, *, agente_id, agente_nome, entrada, saida,
    instrumentos, erros_instrumentos, uso, escolhidas: list[dict], motivo,
    iniciado_em, finalizado_em, estado: str = "concluido", erro: str | None = None,
    aviso: str | None = None, espera: bool = False, aprovacao: dict | None = None,
    regras: list[dict] | None = None, anotou: list[str] | None = None,
    ficha: dict | None = None,
) -> dict:
    """O registro de um passo, no formato que `disparo._fazer_registrador` grava."""
    return {
        "no_id": no_id,
        # Tipo do passo na timeline (Fatia 4.1): o passo em que o agente PEDIU
        # aprovação é uma espera por humano; os demais, agente ou roteador.
        "tipo": "espera_humano" if espera else ("roteador" if tipo == "roteador" else "agente"),
        # Por onde o pedido foi apresentado e de quem se espera a resposta — é o que
        # a borda usa para amarrar a conversa de quem aprova a esta execução. Antes
        # isso vinha do NÓ (`no.aprovacao`); agora vem de quem realmente pediu.
        "aprovacao": aprovacao,
        "agente_id": agente_id,
        "agente_nome": agente_nome,
        "entrada": entrada,
        "saida": saida,
        "instrumentos_acionados": instrumentos,
        "erros_instrumentos": erros_instrumentos,
        # Retrocompat: `saida_escolhida` (singular) segue sendo o primeiro caminho.
        # `saidas_escolhidas` é a verdade nova — o fluxo pode seguir por vários.
        "saida_escolhida": escolhidas[0]["rotulo"] if escolhidas else None,
        "saidas_escolhidas": [s["rotulo"] for s in escolhidas],
        "motivo_ramo": motivo,
        # Onda 2: as regras exatas conferidas pelo MOTOR neste passo (com o resultado
        # de cada uma), os campos que o agente anotou, e a ficha como ficou depois
        # dele. É o que responde "por que não seguiu por ali?" sem adivinhação.
        "regras": regras or [],
        "anotou": anotou or [],
        "ficha": ficha or {},
        "aviso": aviso,
        "estado": estado,
        "erro": erro,
        "uso": uso,
        "iniciado_em": iniciado_em,
        "finalizado_em": finalizado_em,
    }
