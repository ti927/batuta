# Handoff: Automações como **grafo** (construtor visual estilo LangGraph)

> Documento de design para o Claude Code. Substitui a aba **Automações** — que hoje é uma lista vertical "em linha reta" (um agente → o próximo) — por um **construtor de grafo**: nós arrastáveis, arestas condicionais rotuladas, bifurcações, loops (voltar a um agente anterior) e portão de aprovação humano. É a forma visual de desenhar o que o motor (LangGraph) já sabe executar.

Arquivo de design (abrir no navegador): **`Batuta - Construtor de Automacoes.html`** → aba **Automações**.
Harness isolado (só o construtor, tela cheia): **`_screenshot.html`**.
Time de exemplo: **Conteúdo Controladoria (Teste)** — agora com **2 bifurcações** que provam o conceito.

## Leia também
- **`SPEC.md`** — contratos de dados (TypeScript), **o formato exato do `cadeia` JSONB**, specs de componente, estados, endpoints e checklist de aceite.
- **`LANGGRAPH.md`** — ⭐ o mapa **visual → LangGraph**: como cada nó/aresta vira `StateGraph`, `add_conditional_edges`, `interrupt` (human-in-the-loop), loops + `recursion_limit`, e o alinhamento com o código que já existe em `cerebro/orquestracao/`.
- **`screenshots/`** — verdade visual: `01-inspector-bifurcacao` · `02-topologia` · `03-portao-aprovacao` · `04-adicionar-no`.

---

## 1. O problema que isto resolve

A aba Automações antiga (`app-team-editors.jsx`, versão anterior) era uma **lista de cartões**, um por agente, cada um com **uma** saída (rótulo → destino). Visualmente isso comunica **linha reta**: A → B → C → fim. Não dá pra enxergar nem montar com confiança:

- **Bifurcação por intenção** (`PRODUTO.md §14`): "se o resultado for X vai pro agente Y; se for Z vai pro agente 2".
- **Loops / voltar atrás**: "se a pauta for fraca, volta pro Caçador refazer".
- **Portão de aprovação** onde a **resposta do humano escolhe o ramo** (aprovado → publica / reprovado → ajusta).

O motor da Etapa 1 (`BUILD-PLAN.md` Fase 4) **já executa** grafo com bifurcação, loops e human-in-the-loop. O que faltava era a **tela** para desenhar isso. É o que este handoff entrega.

> **Enquadramento para a implementação:** o trabalho novo é majoritariamente **front-end** (o construtor visual) + **persistir um `cadeia` JSONB mais rico** (nós com várias saídas + posição). O `cerebro` **não precisa ser reescrito** — ele já roteia por saída e pausa no portão. Veja `LANGGRAPH.md §6` ("o que muda no cérebro": pouco).

---

## 2. Anatomia da tela

```
┌─ TOOLBAR ───────────────────────────────────────────────────────────────────┐
│ Automação de Conteúdo… · [5 agentes · 2 bifurcações]      [+ Adicionar nó] [Salvar]│
├──────────────────────────────────────────────┬────────────────────────────────┤
│  CANVAS (pan / zoom / arrastar nós)           │  INSPECTOR (nó selecionado)    │
│                                               │  ─ cabeçalho do nó             │
│   ◇ Gatilho → ▢ Caçador → ▢ Validador ─┐      │  ─ Portão de aprovação (toggle)│
│                          │  └─aprovada→▢ Redator → ▢ Revisor(⏸)─aprovado→▢ Pub │  ─ Saídas (bifurcação):        │
│                          └─↺ pauta fraca (volta)         └─↺ reprovado (volta) │     • Saída 1: rótulo + destino│
│                                               │     • Saída 2: rótulo + destino│
│   [legenda]                         [zoom +/–/⌂]│     [+ Adicionar saída]        │
│                                               │  ─ Remover nó                  │
└──────────────────────────────────────────────┴────────────────────────────────┘
```

A aba é **full-bleed** (ocupa 100% da largura útil): some o `max-width` de container; o canvas cresce (`flex:1`) e o inspector fica fixo à direita (348px).

---

## 3. Tipos de nó

| Nó | O que é | Aparência | Saídas |
|---|---|---|---|
| **Gatilho** | o que inicia o fluxo (Manual / Agendamento / Webhook) | cartão roxo, ícone `zap` | exatamente 1 (→ agente inicial) |
| **Agente** | uma peça da cadeia (os agentes do time) | cartão branco: RobotFace + nome + modelo + 1º instrumento; badge `início` / `espera você` | 1 (caminho) ou **N (bifurca)** |
| **Roteador / condição** | nó dedicado só pra decidir o caminho (sem produzir conteúdo) | cartão lilás, ícone `layers` | N (uma por caso) |
| **Fim** | entrega o resultado a quem disparou | pílula verde, `check-circle` | 0 |

> **Decisão de produto:** a bifurcação vive **nas saídas do próprio agente** (modelo principal, igual ao LangGraph: o agente classifica e o roteador escolhe a chave). O **Roteador** é um nó opcional para quando a decisão não pertence a nenhum agente de trabalho. Ambos usam o mesmo editor de saídas.

---

## 4. Arestas (as condicionais)

Cada **saída** de um nó é uma aresta rotulada até um destino. O rótulo é **a condição** ("quando o resultado for X"). Três tipos visuais (cor + legenda), guardados em `tone`:

| `tone` | Cor da linha | Significado | Quando usar |
|---|---|---|---|
| `ok` | verde | aprova / segue adiante | caminho de sucesso, "aprovado" |
| `loop` | âmbar (com ↺) | volta atrás | reprovou, refazer — destino é um agente **anterior** |
| `normal` | cinza | caminho normal | passo único sem decisão |

- O destino pode ser **qualquer nó** — inclusive um **anterior** (loop permitido). Guarda contra laço infinito = limite de passos no motor (`recursion_limit`, ver `LANGGRAPH.md §4`).
- A **pílula no meio da aresta** mostra o rótulo e é clicável (seleciona o nó de origem para editar aquela saída).
- Setas sempre entram pelo **handle de entrada** (lado esquerdo) do destino; cada saída sai por um **handle** próprio (lado direito), então "duas saídas" = dois pontos distintos saindo do nó — a bifurcação fica óbvia.

---

## 5. O inspector (onde a bifurcação nasce)

Clicou num nó → o painel à direita abre. Para um **agente**:

- **Cabeçalho**: RobotFace + nome + resumo.
- **Portão de aprovação** (toggle): liga o human-in-the-loop. Quando ligado, o nó ganha o badge `espera você` e o texto das saídas muda de *"Quando o resultado for…"* para *"Decisão (o que você responde)"* — porque, no portão, **a resposta do humano é que escolhe a saída**.
- **Saídas** (lista): cada saída = rótulo (input) + **destino** (select de nós) + **tipo** (`normal`/`ok`/`loop`). **`+ Adicionar saída (bifurcar)`** cria uma nova aresta na hora → o grafo se redesenha. Remover saída idem.
- **Remover nó**.

Para **Gatilho**: escolha Manual / Agendamento / Webhook. Para **Roteador**: nome da decisão + saídas. Para **Fim**: só leitura.

Nada de seleção → o inspector mostra a **legenda dos tipos de saída** + dica de uso.

---

## 6. Interações do canvas

| Ação | Como |
|---|---|
| Selecionar nó | clique |
| Mover nó | arrastar o cartão |
| Pan | arrastar o fundo |
| Zoom | roda do mouse (centrado no cursor) ou botões **+ / –** |
| Enquadrar | botão **⌂** (volta ao zoom/pan padrão) |
| Editar uma aresta | clicar na pílula do rótulo (seleciona a origem) |
| Adicionar nó | **+ Adicionar nó** → agente do time ou Roteador (cai no centro do viewport) |

Fundo com **grade pontilhada** que acompanha o pan/zoom (afinada para leitura, estilo editor de fluxo).

---

## 7. Por que essas decisões (racional de design)

1. **Grafo, não lista** — a topologia é a informação. Ver as setas (incl. as que voltam) comunica "isto não é linha reta" em 1 segundo.
2. **Bifurcação na saída do agente** — espelha 1:1 a **aresta condicional do LangGraph** (o agente decide, o roteador mapeia a decisão → destino). Não inventa um conceito novo; desenha o que o motor já faz.
3. **Portão = a resposta humana escolhe o ramo** — alinhado ao fix `941ee8e` do `BUILD-PLAN.md` (o nó com pausa não roteia sozinho; o `responder` casa a decisão com o `quando` da saída).
4. **Cores semânticas** — verde/âmbar/cinza dão leitura imediata de "sucesso / volta / normal" sem depender só de cor (há ícone ↺ e legenda — `DESIGN-SYSTEM.md §11`).
5. **Inspector à direita, canvas full-bleed** — densidade controlada: o canvas respira, a edição mora num lugar fixo.

### Sugestões para a próxima rodada (não implementadas)
- **Minimapa** (canto) para navegar grafos grandes.
- **Auto-layout** (botão "organizar") com dagre/elk — recalcula posições.
- **Validação visual**: nó sem saída (encerra), nó inalcançável, loop sem condição de parada → realce âmbar/vermelho.
- **Custo estimado por caminho** sobreposto (PRODUTO §21).
- **Desfazer/refazer** no canvas.

---

## 8. Arquivos desta entrega

| Arquivo | Papel |
|---|---|
| `Batuta - Construtor de Automacoes.html` | entrada; renderiza a página do time com a aba Automações = grafo |
| **`app-team-automacoes.jsx`** | ⭐ o construtor de grafo inteiro (nós, arestas, pan/zoom, inspector). Exporta `window.TabAutomacoes`. |
| `app-team-workspace.jsx` | casca da página do time; renderiza a aba `automacoes` **full-bleed** (sem `max-width`) |
| `app-team-editors.jsx` | editores de agente/instrumento (a `TabAutomacoes` antiga foi removida daqui) |
| `app-data-team.jsx` | dados reais do time (agentes, instrumentos) — fixture |
| `app-icons.jsx` | ícones lucide |
| `app-creation.jsx` | primitivos reusados: `RobotFace`, `StatusBadge`, `SectionLabel` |
| `_screenshot.html` | harness que monta **só** o construtor em tela cheia (usado p/ os screenshots) |

Os `.jsx` são **referência visual** — estilos inline. No app real (Next.js + TS + Tailwind + shadcn/ui), traduzir para componentes/tokens e usar **React Flow** no canvas (ver `LANGGRAPH.md §7`).

---

## 9. Ordem de implementação sugerida

1. **Modelo de dados** — estender `automacoes.cadeia` (JSONB) para o formato de grafo (nós com `saidas[]` + posição). Ver `SPEC.md §2`. Aditivo; converter a cadeia linear antiga é trivial.
2. **Canvas com React Flow** — nós custom (Gatilho/Agente/Roteador/Fim), handles de saída, arestas com label + cor por `tone`, `Controls`/`MiniMap`. Ver `LANGGRAPH.md §7`.
3. **Inspector** — editor de saídas (rótulo + destino + tone), toggle de portão, gatilho. `+ Adicionar saída` cria aresta.
4. **Persistência** — `GET/PUT /times/{id}/automacao` lê/grava o grafo; posição dos nós faz parte do JSONB (UI-only para o motor).
5. **Conferir o motor** — confirmar que `orquestracao/cadeia.py` consome o grafo (saídas → `add_conditional_edges`; `gate` → `interrupt`; `fim` → `END`). Ajuste mínimo se preciso (ver `LANGGRAPH.md §6`).
6. **Próxima rodada** — minimapa, auto-layout, validação visual.
