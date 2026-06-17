# SPEC — Construtor de Automações (grafo) · referência técnica

Complemento estruturado do `README.md`. Aqui: **formato do `cadeia` JSONB**, contratos TypeScript, specs de componente, matriz de estados, endpoints e checklist de aceite. O `LANGGRAPH.md` cobre o lado do motor.

> Premissa: app real = Next.js 16 + TS + Tailwind + shadcn/ui + lucide-react, consumindo o cérebro (FastAPI). Canvas = **React Flow (`@xyflow/react`)**. Os `.jsx` deste bundle são referência visual, não código de produção.

---

## 1. Conceito central

Uma automação é um **grafo dirigido**: nós (gatilho, agentes, roteadores, fim) ligados por **arestas rotuladas**. Cada aresta = uma **saída** de um nó com uma **condição** (rótulo) e um **destino**. Vários destinos saindo de um nó = **bifurcação**. Destino apontando para um nó anterior = **loop**.

Isto é exatamente o modelo de **arestas condicionais do LangGraph** — ver `LANGGRAPH.md`.

---

## 2. Formato do `cadeia` (JSONB) — a fonte da verdade

Estende o `automacoes.cadeia` que já existe (`BUILD-PLAN.md` Fase 1/4.3). **Aditivo**: a cadeia linear antiga vira um caso particular (todo nó com 1 saída).

```jsonc
{
  "inicial": "cacador",            // id do nó que recebe a entrada do gatilho
  "nos": [
    {
      "id": "gatilho",             // id estável (string)
      "tipo": "gatilho",           // "gatilho" | "agente" | "roteador" | "fim"
      "x": 60, "y": 238,           // posição no canvas (UI-only; o motor ignora)
      "gatilho": "manual",         // só p/ tipo "gatilho": "manual"|"agendamento"|"webhook"
      "saidas": [
        { "id": "g0", "rotulo": "inicia o fluxo", "destino": "cacador", "tone": "normal" }
      ]
    },
    {
      "id": "cacador",
      "tipo": "agente",
      "ref": "cacador",            // FK p/ agentes.id (só tipo "agente")
      "inicial": true,             // marca visual do agente inicial
      "x": 352, "y": 226,
      "saidas": [
        { "id": "c0", "rotulo": "tema escolhido", "destino": "validador", "tone": "normal" }
      ]
    },
    {
      "id": "validador", "tipo": "agente", "ref": "validador", "x": 668, "y": 226,
      "saidas": [
        { "id": "v0", "rotulo": "pauta aprovada",       "destino": "redator",  "tone": "ok"   },
        { "id": "v1", "rotulo": "pauta fraca, refazer",  "destino": "cacador",  "tone": "loop" }   // ← loop
      ]
    },
    {
      "id": "revisor", "tipo": "agente", "ref": "revisor", "gate": true, "x": 1300, "y": 226,
      "saidas": [
        { "id": "rv0", "rotulo": "aprovado",            "destino": "publicador", "tone": "ok"   },
        { "id": "rv1", "rotulo": "reprovado, ajustar",  "destino": "redator",    "tone": "loop" }   // ← portão decide
      ]
    },
    { "id": "publicador", "tipo": "agente", "ref": "publicador", "x": 1616, "y": 226,
      "saidas": [ { "id": "p0", "rotulo": "publicado", "destino": "fim", "tone": "ok" } ] },
    { "id": "fim", "tipo": "fim", "x": 1908, "y": 240, "saidas": [] }
  ]
}
```

### Campos
| Campo | Onde | Lido pelo motor? | Notas |
|---|---|---|---|
| `inicial` | raiz | ✅ | id do 1º nó-agente |
| `nos[].id` | nó | ✅ | id estável (não é o nome) |
| `nos[].tipo` | nó | ✅ | gatilho/agente/roteador/fim |
| `nos[].ref` | nó agente | ✅ | id do agente em `agentes` |
| `nos[].gate` | nó agente | ✅ | liga o portão (interrupt) |
| `nos[].gatilho` | nó gatilho | ✅ | tipo de gatilho |
| `nos[].saidas[].id` | saída | — | id estável da aresta |
| `nos[].saidas[].rotulo` | saída | ✅ | **a chave de roteamento** (ver LANGGRAPH §3) |
| `nos[].saidas[].destino` | saída | ✅ | id de outro nó (pode ser anterior = loop) |
| `nos[].saidas[].tone` | saída | ❌ | só cor na UI (`normal`/`ok`/`loop`) |
| `nos[].x`,`y` | nó | ❌ | layout do canvas (UI-only) |

> **Regra:** `tone`, `x`, `y` são **cosméticos** — o motor nunca depende deles. Assim a equipe pode mudar o visual sem tocar a execução.

---

## 3. Contratos TypeScript (front-end)

```ts
type NodeTipo = 'gatilho' | 'agente' | 'roteador' | 'fim';
type Tone = 'normal' | 'ok' | 'loop';
type TipoGatilho = 'manual' | 'agendamento' | 'webhook';

interface Saida {
  id: string;
  rotulo: string;        // condição / decisão
  destino: string;       // id de nó (inclui o próprio "fim")
  tone: Tone;            // cor da aresta (UI)
  lane?: 'above' | 'below'; // dica de roteamento da curva p/ loops (UI)
}

interface GrafoNode {
  id: string;
  tipo: NodeTipo;
  x: number; y: number;          // posição no canvas
  ref?: string;                  // agente (tipo 'agente')
  nome?: string;                 // roteador
  inicial?: boolean;             // agente inicial
  gate?: boolean;                // portão de aprovação (agente)
  gatilho?: TipoGatilho;         // tipo 'gatilho'
  saidas: Saida[];
}

interface Automacao {
  id: string;
  nome: string;
  inicial: string;               // id do nó inicial
  nos: GrafoNode[];
  ativa: boolean;
}
```

`Agente` / `Instrumento` etc.: ver `design_handoff_pagina_time/SPEC.md §2` (inalterados).

### Endpoints
- `GET /times/{id}/automacao` → `Automacao` (com `nos[]`).
- `PUT /times/{id}/automacao` ← grava o grafo inteiro (nós + saídas + posições).
- `POST /execucoes/{id}/disparar` · `POST /execucoes/{id}/responder` (resolve o portão; a resposta escolhe a saída — ver LANGGRAPH §5).
- Lista de agentes do time p/ o menu "Adicionar nó": `GET /times/{id}/agentes`.

---

## 4. Componentes (props e estados)

| Componente | Base (real) | Props | Estados |
|---|---|---|---|
| `AutomacaoBuilder` | `ReactFlow` wrapper | `automacao`, `agentes`, `onSave` | editando / salvando |
| `GatilhoNode` | custom node | `data{gatilho}` | selecionado |
| `AgenteNode` | custom node | `data{agente, inicial, gate, saidas}` | selecionado / gate-on (badge `espera você`) |
| `RoteadorNode` | custom node | `data{nome}` | selecionado |
| `FimNode` | custom node | — | — |
| `CondEdge` | custom edge | `data{rotulo, tone}` | normal / selecionada (roxo) |
| `Inspector` | painel (`Sheet` fixo) | `node`, `nodes`, `onPatch*` | vazio / gatilho / agente / roteador / fim |
| `SaidaRow` | linha do inspector | `saida`, `onChange`, `onRemove` | — |
| `RobotFace` | custom | `cor`, `size`, `lider?` | — |

**Handles (React Flow):** cada nó-agente tem 1 handle de **entrada** (`target`, esquerda) e **N handles de saída** (`source`, direita, um por `saida`). O id do handle de saída = `saida.id` → conecta-se naturalmente às arestas.

---

## 5. Matriz de estados
- **Sem nós / automação nova:** estado vazio "Comece pelo gatilho" + botão.
- **Nó sem saída** (que não seja `fim`): aviso — encerra o fluxo ali (válido, mas sinalizar).
- **Destino vago/quebrado:** aresta pendente realçada; bloquear salvar até resolver.
- **Loop sem porta de saída:** aviso (risco de laço) — o motor corta por `recursion_limit`, mas a UI deve alertar.
- **Portão ligado:** badge `espera você` no nó; rótulos das saídas viram "Decisão…".
- **Salvando / salvo:** toast "Automação salva".

---

## 6. Cores (tokens — `DESIGN-SYSTEM.md`)

| Uso | Valor |
|---|---|
| Aresta `ok` / verde | linha `#79C295`, pílula `#E6F4EA` / `#2F7D45` |
| Aresta `loop` / âmbar | linha `#E3BB7C`, pílula `#FDF1E3` / `#A9681A` |
| Aresta `normal` / cinza | linha `#C3BFD6`, pílula `#FFFFFF` / `#6B6880` |
| Nó selecionado | borda `#6D4AFF` + ring `rgba(109,74,255,.14)` |
| Gatilho | ícone em `#6D4AFF` sobre `#EFEAFF` |
| Fim | verde `#3DAA5C` / `#E6F4EA` |
| Badge `espera você` (gate) | `#A9681A` sobre `#FDF1E3`, ícone `shield` |
| Fundo do canvas | `#FAFAF7` + grade pontilhada `#E0DDF0` |

Tipografia: Inter 400/500, sentence case, sem bold. Bordas 1px `#E8E6F0`, raios 8–12px, flat (sem sombra pesada).

---

## 7. Critérios de aceite (checklist)

**Modelo / persistência**
- [ ] `cadeia` JSONB no formato §2; `tone`/`x`/`y` não afetam execução.
- [ ] `PUT /times/{id}/automacao` grava nós + saídas + posições; reler reconstrói o grafo idêntico.
- [ ] Cadeia linear antiga abre como grafo (cada nó 1 saída).

**Canvas**
- [ ] Nós custom por tipo; arrastar move e as arestas seguem.
- [ ] Pan (fundo) + zoom (roda/botões) + enquadrar.
- [ ] Aresta com rótulo no meio + cor por `tone`; seta entra pela esquerda do destino.
- [ ] Bifurcação visível: 2+ saídas saem de handles distintos; loop desenha curva de volta.

**Inspector**
- [ ] Selecionar nó abre o painel certo (gatilho/agente/roteador/fim).
- [ ] Editar rótulo/destino/tone de uma saída redesenha a aresta na hora.
- [ ] `+ Adicionar saída` cria aresta; remover saída remove aresta.
- [ ] Toggle do portão: liga `gate`, mostra badge no nó, troca o texto das saídas p/ "Decisão…".

**Motor (conferência)**
- [ ] Disparar uma automação com bifurcação segue o ramo certo nos dois casos.
- [ ] Loop (validador→caçador) executa com guarda de passos.
- [ ] Portão pausa; `responder` com "aprovado"/"reprovado" escolhe a saída e retoma.

**Transversais**
- [ ] Gating por papel (operador edita; observador responde portão; admin remove) — `lib/permissoes.ts`.
- [ ] Sentence case; Inter 400/500; roxo só em CTA/seleção/marca; flat.

---

## 8. Como ler os arquivos de design
- Abrir `Batuta - Construtor de Automacoes.html` → aba **Automações** = comportamento real (arrastar, zoom, selecionar, adicionar saída/nó). `_screenshot.html` mostra só o construtor em tela cheia.
- Valores exatos (paddings, cores, geometria das curvas) estão em `app-team-automacoes.jsx` como estilos inline — **traduzir** para Tailwind/tokens + React Flow, não copiar inline.
- `app-data-team.jsx` = fixture real (use como dados de teste).
- Nas screenshots, o `<select>` de destino pode aparecer mostrando a 1ª opção — é artefato do capturador (html-to-image); no HTML ao vivo o valor está correto.
