# LANGGRAPH.md — do grafo visual ao motor LangGraph

⭐ Este é o documento técnico que conecta **a tela** (o construtor de grafo) ao **motor** (LangGraph) que já vive em `cerebro/orquestracao/`. Objetivo: o Claude Code olhar um nó/aresta na UI e saber **exatamente** que construção LangGraph ele vira — e perceber que o motor **já faz quase tudo** (Fase 4 do `BUILD-PLAN.md`), então isto é mais "ligar a UI ao que existe" do que "construir o motor".

> Versões alvo (do `BUILD-PLAN.md`): LangGraph sobre `langchain-anthropic`/`-openai`/`-google-genai`; motor **síncrono**; chave resolvida por contexto (`usar_chaves`). Arquivos atuais: `orquestracao/{llm,agente,cadeia,disparo,modelos_ia}.py`, `rotas/{automacoes,execucao,webhooks}.py`.

---

## 1. Mapa de equivalências (a tabela mestra)

| Na tela (construtor) | No `cadeia` JSONB | No LangGraph |
|---|---|---|
| Nó **Agente** | `{tipo:"agente", ref}` | um **node** do `StateGraph` (o `create_react_agent` montado dos 4 markdowns + cinto — `agente.py`) |
| Nó **Roteador** | `{tipo:"roteador"}` | um node de roteamento (classificador barato) **ou** só a função condicional |
| Nó **Gatilho** | `{tipo:"gatilho", gatilho}` | o **ponto de entrada** + o disparo (`disparo.executar_automacao`); não é node de trabalho |
| Nó **Fim** | `{tipo:"fim"}` | `END` |
| Saída **única** (`normal`) | `saidas:[1]` | `graph.add_edge(no, destino)` |
| **Bifurcação** (`saidas:[N]`) | várias saídas | `graph.add_conditional_edges(no, roteador, {rotulo→destino})` |
| `destino` = nó anterior | aresta "pra trás" | aresta normal — LangGraph permite ciclo; guarda = `recursion_limit` |
| `destino` = `"fim"` | — | `END` |
| **Portão de aprovação** (`gate:true`) | `gate:true` | `interrupt()` no node → pausa; retoma com `Command(resume=…)` |
| `rotulo` da saída | string | **a chave de roteamento** que a função condicional devolve |
| `tone`, `x`, `y` | cosmético | **ignorados** pelo motor |

---

## 2. Montando o grafo a partir do JSONB (esboço)

O `cadeia.py` já faz isto; o esboço abaixo é a forma canônica e deve casar com o JSONB do `SPEC.md §2`.

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint... import <checkpointer>   # p/ persistir pausa (já existe)

def montar_grafo(automacao, agentes_por_id):
    g = StateGraph(EstadoExecucao)          # estado = entrada/saída acumulada + contexto

    nos = {n["id"]: n for n in automacao["nos"]}

    # 1) nodes (só agentes e roteadores viram node; gatilho/fim não)
    for n in automacao["nos"]:
        if n["tipo"] == "agente":
            g.add_node(n["id"], fazer_node_agente(agentes_por_id[n["ref"]], gate=n.get("gate")))
        elif n["tipo"] == "roteador":
            g.add_node(n["id"], fazer_node_roteador(n))

    # 2) ponto de entrada
    g.set_entry_point(automacao["inicial"])

    # 3) arestas a partir das saídas
    for n in automacao["nos"]:
        saidas = n.get("saidas", [])
        if n["tipo"] in ("gatilho", "fim"):
            continue
        if len(saidas) == 0:
            g.add_edge(n["id"], END)                     # nó sem saída encerra
        elif len(saidas) == 1:
            g.add_edge(n["id"], destino_para(saidas[0]))  # caminho único
        else:
            mapa = {s["rotulo"]: destino_para(s) for s in saidas}
            g.add_conditional_edges(n["id"], fazer_roteador(n, saidas), mapa)  # ← bifurcação

    return g.compile(checkpointer=<checkpointer>)         # checkpointer = retomar pausa

def destino_para(saida):
    return END if saida["destino"] == "fim" else saida["destino"]
```

---

## 3. A bifurcação: `add_conditional_edges` (a condicional)

Para um nó com N saídas, a **função de roteamento** decide qual `rotulo` se aplica e o LangGraph segue o `destino` mapeado. Há dois casos:

**(a) Agente comum que classifica** — o roteador faz uma chamada de LLM estruturada (o `cadeia.py` atual já faz "roteamento por LLM estruturado"): dada a saída do agente, escolhe **um dos `rotulo`s** disponíveis.

```python
def fazer_roteador(no, saidas):
    rotulos = [s["rotulo"] for s in saidas]
    def roteador(estado) -> str:
        escolha = classificar_com_llm(estado["ultimo_resultado"], rotulos)  # devolve um rótulo
        return escolha if escolha in rotulos else rotulos[0]
    return roteador
```

> O `rotulo` **é a chave**. Por isso na UI o rótulo é a "condição" ("pauta aprovada", "pauta fraca, refazer"): ele vira literalmente o valor que a função condicional retorna e a chave do `mapa` em `add_conditional_edges`.

**(b) Nó Roteador dedicado** — mesma ideia, mas o node não produz conteúdo; só classifica (modelo barato) e devolve o rótulo. Útil quando a decisão não pertence a um agente de trabalho (ex.: cenário 6 do PRODUTO — "é sobre agenda ou exame?").

---

## 4. Loops (voltar a um agente anterior)

Uma saída cujo `destino` é um nó **anterior** é uma aresta normal no LangGraph — ciclos são permitidos. A única proteção necessária é **limite de passos**, contra laço infinito:

```python
grafo.invoke(entrada, config={"recursion_limit": 40})   # guarda; já previsto no BUILD-PLAN 4.3
```

Exemplos no time de teste:
- `validador --(pauta fraca, refazer)--> cacador` — refaz a pauta.
- `revisor --(reprovado, ajustar)--> redator` — reescreve.

Na UI essas arestas são `tone:"loop"` (âmbar, ↺) e desenham curva de volta — puramente visual; o motor só vê "destino = id anterior".

---

## 5. Portão de aprovação = human-in-the-loop (`interrupt`)

Quando o nó tem `gate:true`, ele **pausa** e espera a resposta humana, que **escolhe a saída** (fix `941ee8e` do `BUILD-PLAN.md`: o nó com pausa **não roteia sozinho**; quem roteia é a resposta).

```python
from langgraph.types import interrupt, Command

def fazer_node_agente(agente, gate=False):
    def node(estado):
        resultado = rodar_agente(agente, estado)        # create_react_agent (agente.py)
        if gate:
            decisao = interrupt({                        # PAUSA — persiste no checkpointer
                "tipo": "portao",
                "trabalho": resultado,
                "opcoes": [s["rotulo"] for s in estado["saidas_deste_no"]],
            })
            estado["decisao_humana"] = decisao           # vira a chave de roteamento
        estado["ultimo_resultado"] = resultado
        return estado
    return node
```

E o **roteador do nó com gate** casa a resposta humana com o `rotulo` da saída (em vez de classificar por LLM):

```python
def fazer_roteador_gate(saidas):
    def roteador(estado) -> str:
        return casar_decisao(estado["decisao_humana"], [s["rotulo"] for s in saidas])
    return roteador
```

Retomada (a tela de execução já tem a caixa de resposta): `rotas/automacoes.py` → `POST /execucoes/{id}/responder` reidrata o checkpoint e faz `grafo.invoke(Command(resume=decisao), config={thread_id})`. As três formas do PRODUTO §14 (pergunta pontual, portão de aprovação, confirmação de baixa confiança) são o mesmo mecanismo `interrupt`/`resume`.

---

## 6. O que muda no cérebro (pouco)

O motor da Etapa 1 **já** executa grafo com bifurcação, loops e portão (`BUILD-PLAN.md` Fase 4 ✅). Então:

- ✅ **Já existe:** `StateGraph`, `add_conditional_edges`, roteamento por LLM estruturado, `interrupt`/`resume`, guarda de passos, registro de `execucoes`/`passos_execucao`, resolução de chave por provedor.
- 🔧 **Conferir/ajustar (provável que mínimo):**
  1. O parser do `cadeia` JSONB aceitar o formato de **lista de `nos` com `saidas[]`** do `SPEC.md §2` (se hoje o shape for diferente, é um adaptador — **não** um motor novo).
  2. Garantir que o **`rotulo`** da UI é a chave usada no `mapa` de `add_conditional_edges` (consistência UI↔motor).
  3. Persistir/ignorar os campos cosméticos (`tone`, `x`, `y`) sem quebrar.
  4. Nó **Roteador** como tipo de node de classificação (se ainda não existe como tipo explícito).
- ❌ **Não fazer:** reescrever a orquestração, trocar de lib, mexer no laço react do agente.

---

## 7. Implementação do canvas no app real — **React Flow**

O protótipo desenha tudo à mão (SVG + drag) só pra não depender de lib no HTML. No Next.js, use **`@xyflow/react`** (React Flow) — é o padrão e cobre tudo de graça:

| Conceito do protótipo | React Flow |
|---|---|
| nó arrastável | `nodes` + `nodeTypes` (custom: Gatilho/Agente/Roteador/Fim) |
| handle de entrada / saídas | `<Handle type="target"/>` (1) + `<Handle type="source" id={saida.id}/>` (N) |
| aresta curva + rótulo + cor | `edges` + `edgeTypes` (custom `CondEdge` com `label` e `style` por `tone`) |
| pan / zoom / enquadrar | `<Controls/>` + `fitView` |
| grade pontilhada | `<Background variant="dots"/>` |
| minimapa (próxima rodada) | `<MiniMap/>` |
| mover nó → salvar posição | `onNodesChange` → grava `x,y` no JSONB |
| ligar/editar saída | `onConnect` / inspector → muta `saidas[]` |

Mapeamento de dados: `Automacao.nos` → `nodes` (`{id, type, position:{x,y}, data}`); cada `saida` → uma `edge` (`{id, source, sourceHandle:saida.id, target:destino, type:'cond', data:{rotulo,tone}}`). O `destino:"fim"` aponta para o node `fim`.

O inspector continua sendo o lugar de criar/editar saídas (não obrigar o usuário a arrastar conexões — arrastar é atalho; o painel é a forma garantida e acessível).

---

## 8. Exemplo completo — o time "Conteúdo Controladoria"

Grafo de teste (no `app-data-team.jsx` e no JSONB do `SPEC.md §2`):

```
gatilho(manual)
   └─ inicia → cacador
cacador (Caçador de Pauta, sonnet)
   └─ tema escolhido → validador
validador (Validador de Pauta, sonnet)         ← BIFURCA
   ├─ pauta aprovada → redator                  (ok)
   └─ pauta fraca, refazer → cacador             (loop)   ↺
redator (Redator, opus)
   └─ artigo escrito → revisor
revisor (Revisor de SEO, sonnet) [PORTÃO]      ← BIFURCA pela resposta humana
   ├─ aprovado → publicador                     (ok)
   └─ reprovado, ajustar → redator               (loop)   ↺
publicador (Publicador, haiku · WordPress)
   └─ publicado → fim
fim
```

Em LangGraph isso é: 5 nodes-agente + entry `cacador`; `add_edge` nos passos únicos; `add_conditional_edges` em `validador` (roteador por LLM) e em `revisor` (roteador pela `decisao_humana` do `interrupt`); duas arestas de volta (loops) cortadas por `recursion_limit`. É **a mesma topologia** que a tela desenha — e é o que prova que "linha reta" ficou para trás.
