# Handoff: Página do Time com abas (workspace unificado)

> Documento de design para o Claude Code. Descreve a refatoração da **página do time** — de links que navegam para páginas separadas → para uma **experiência única com abas**, onde o usuário gerencia o time inteiro sem sair da página.

Arquivo de design (referência viva, abrir no navegador): **`Batuta — Página do Time.html`**
Time de exemplo nos dados: **Conteúdo Controladoria (Teste)** (Lure Consultoria) — os mesmos agentes/instrumentos/automação/execuções dos screenshots de produção.

## Como este pacote está organizado
- **`README.md`** (este) — o "porquê" e o "o quê": estrutura, cada aba, editores, melhorias de UX, mapa de dados.
- **`SPEC.md`** — o "como verificar": rotas, contratos de dados (TypeScript), specs de componente (props/estados), cores por estado, matriz de estados, permissões por papel e **checklist de aceite**.
- **`screenshots/`** — verdade visual do alvo, uma imagem por aba/estado (`01-inicio` … `08-conversas`).
- **arquivos `.jsx` + `.html`** — protótipo executável (referência de comportamento; abrir o HTML no navegador).
- **`assets/`** — mascote e símbolo.

---

## 1. O problema que isto resolve

Hoje, a página inicial do time tem **links no topo** ("Gerenciar agentes", "Instrumentos", "Automações", "Conversas") que levam o usuário para **outras páginas/rotas**. Para configurar o time inteiro, ele fica indo e voltando, perdendo contexto a cada salto.

**A mudança:** transformar esses links em **abas** dentro da própria página do time. O cabeçalho do time (nome, status, ações) fica **persistente** no topo; abaixo dele, uma **barra de abas**; abaixo, o conteúdo da aba ativa. O usuário nunca "sai" do time.

---

## 2. Estrutura: cabeçalho persistente + abas

```
┌── Sidebar global (inalterada) ──┬── Área do time ───────────────────────────┐
│  Batuta                         │  ┌─ CABEÇALHO PERSISTENTE ──────────────┐ │
│  + Criar com a IA               │  │ Conteúdo Controladoria (Teste) ·ativo│ │
│  Início                         │  │ <resumo>      [Conversar] [Rodar ▸]  │ │
│  Times ▾                        │  │ ┌ BARRA DE ABAS ────────────────────┐│ │
│    · Conteúdo Controladoria ←   │  │ │ Início · Agentes 5 · Instrum. 2 · ││ │
│  Execuções / Biblioteca / ...   │  │ │ Automações · Execuções 3 · Conv. 6││ │
│  Acesso / Chaves / Config.      │  │ └───────────────────────────────────┘│ │
│  [Org: Lure Consultoria]        │  └──────────────────────────────────────┘ │
│  [user]                         │  ┌─ CONTEÚDO DA ABA ATIVA ──────────────┐ │
│                                 │  │ …                                    │ │
└─────────────────────────────────┴──┴──────────────────────────────────────┘─┘
```

### Cabeçalho persistente (sempre visível, em todas as abas)
- **Nome do time** (Bricolage Grotesque 23px) + **badge de status** (`ativo` verde / `rascunho` laranja).
- **Resumo** do time (1 linha, cinza `#6B6880`).
- Ações à direita: **"Conversar sobre o projeto"** (ghost, abre a IA companheira) e **"Rodar agora"** (primário roxo).
- Fundo branco, borda inferior `#E8E6F0`. Padding lateral 32px.

### Barra de abas
- 6 abas: **Início · Agentes · Instrumentos · Automações · Execuções · Conversas**.
- Cada aba: ícone lucide 16px + label. Abas com coleção mostram **contador** (pílula): Agentes `5`, Instrumentos `2`, Execuções `3`, Conversas `6`.
- Aba ativa: texto roxo `#6D4AFF` + **underline** roxo (`inset 0 -2px 0`); contador em pílula `#EFEAFF`. Inativa: cinza `#6B6880`, contador `#F0EEF6`.
- **Indicador de atenção:** se houver conversa em andamento (ou item que pede ação), um ponto roxo aparece ao lado do label da aba.
- Em viewport estreito a barra rola horizontalmente (`overflow-x:auto`).

### Roteamento e deep-link
- Cada aba deve ser uma **rota real** para deep-link e botão voltar do navegador: `/times/{id}` (Início), `/times/{id}/agentes`, `/instrumentos`, `/automacoes`, `/execucoes`, `/conversas`.
- Sub-detalhes também são rotas: `/times/{id}/execucoes/{execId}`, `/times/{id}/conversas/{convId}`.
- No protótipo, a aba/execução aberta é persistida em `localStorage` (`batuta_team_nav`) só para sobreviver a refresh durante a iteração de design — **no app real use a URL**, não localStorage.

---

## 3. As abas, uma a uma

### 3.1 Início (visão geral)
Resumo de saúde do time — **leitura, não configuração**.
- **Stat cards** (4, flex): **Gatilho** (Manual / Agendamento / Webhook), **Aguardando você** (`Nada pendente` verde, ou `N pendente` laranja + clicável → aba Execuções), **Custo acumulado**, **Taxa de sucesso**.
- **Cadeia · o caminho da tarefa**: a cadeia visual horizontal (Gatilho → agentes → Aprovação → Publicador → Fim), com link "Editar a automação" → aba Automações.
- **Execuções recentes** (3 últimas): linha com badge de estado, id, entrada, data → clica e abre a aba Execuções já no detalhe.
- **Agentes**: grid 2-col dos cards (mesmo card da aba Agentes) → clica e abre o editor.

### 3.2 Agentes
- Cabeçalho da aba: título + subtítulo + **"+ Novo agente"** (primário).
- Grid 2-col de **cards de agente**: RobotFace colorido + nome + badge (`inicial` / `portão`) + resumo (2 linhas) + modelo + chips de instrumentos. Ícone de lápis indica "clique para editar".
- Clique no card → **Editor de Agente** (drawer à direita, 560px) — ver §4.1.

### 3.3 Instrumentos
- Cabeçalho + **"+ Novo instrumento"**.
- Lista de instrumentos: ícone + nome + badge **`exige aprovação`** (laranja, quando aplicável) + slug mono + "usado por {agentes}".
- Clique → **Editor de Instrumento** (drawer 480px) — ver §4.2.

### 3.4 Automações
- O **construtor da cadeia**, inline (sem navegar):
  - Nome da automação + **"Salvar"**.
  - **Gatilho** — 3 cards selecionáveis (Manual / Agendamento / Webhook), cada um com ícone + descrição. O selecionado fica roxo.
  - **A cadeia — saídas de cada agente**: um bloco por agente. Cada saída = rótulo (input) + destino (outro agente ou "fim"). O bloco do agente com **portão de aprovação** mostra um aviso âmbar ("ao terminar, pausa e espera sua decisão"). Botão "+ saída" por agente.
- Espelha exatamente o formulário "Editar automação" de produção, mas vive dentro da aba.

### 3.5 Execuções (master-detail dentro da aba)
- **Lista**: cabeçalho + "Rodar agora"; 4 **stat cards** (Total, Taxa de sucesso, Duração média, Custo total); **filtros** em pílula (Todas / Concluídas / Aguardando você / Falhou, com contagem); lista de execuções (badge de estado, id mono, entrada, data, duração).
- **Detalhe** (substitui a lista na mesma aba, com "← Todas as execuções"):
  - Cabeçalho: "Execução #id" + badge; meta (data, custo, entrada).
  - **Portão de aprovação** (se `aguardando_humano`): painel âmbar com o rascunho do artigo + **"Aprovar e publicar"** (vira "Publicando…" → conclui) e "Pedir ajuste". Esta é a **espera-por-humano** acontecendo dentro da execução.
  - **Passo a passo**: timeline vertical com dot por estado (ok=verde, aguardando=âmbar, pendente=cinza, falhou=vermelho), RobotFace, tokens, duração; expansível mostra o que o passo **produziu** e, no portão, quem aprovou. Passo de **falha** mostra a mensagem de erro em vermelho (ex.: o erro real do WordPress sem protocolo).
  - Rodapé: **uso estimado** (tokens entrada/saída, custo, origem da chave) — "apenas informativo, não é cobrança".

### 3.6 Conversas (master-detail two-pane)
- Cabeçalho + 5 **stat cards** (Conversas, Em andamento, Foram p/ humano + %, 1ª resposta média, Custo de IA) + **filtros** (Em andamento / Com humano / Fechadas / Todas).
- **Two-pane**: lista à esquerda (avatar, contato, badge de estado/`com humano`, turnos, data) + **thread** à direita (bolhas: contato à esquerda branco, IA à direita lavanda; eventos de sistema centralizados, ex. "transferida para humano"). Rodapé do thread: campo "responder como humano" (se aberta) ou "conversa encerrada", e **"Assumir atendimento"**.

---

## 4. Editores (drawers — não navegam)

Padrão: drawer da direita com backdrop, `Esc` fecha, animação `drawer-in`. Mantém o usuário na aba.

### 4.1 Editor de Agente (560px)
- Header: RobotFace + nome + badge.
- **Modelo de IA**: 3 botões segmentados (haiku / sonnet / opus).
- **Cinto de instrumentos**: chips dos instrumentos + "Adicionar".
- **Abas dos 4 markdowns**: `agent.md` (Quem é) · `skill.md` (Habilidades) · `tools.md` (Cinto) · `soul.md` (Personalidade). Cada uma = textarea editável + **"Melhorar este texto com a IA"**.
- Rodapé: **Salvar alterações** (habilita só quando há mudança) · Cancelar · Remover.

### 4.2 Editor de Instrumento (480px)
- Header: ícone + nome + slug.
- Tipo, "o que faz", **toggle "Exigir aprovação humana"** (com explicação), "usado por".
- Rodapé: Salvar · Cancelar.

---

## 5. Melhorias de UX aplicadas (além do pedido)
1. **Cabeçalho + ações persistentes** — "Rodar agora" e "Conversar sobre o projeto" acessíveis de qualquer aba.
2. **Contadores nas abas** — o usuário vê quantos agentes/execuções/conversas sem entrar.
3. **Editores em drawer** — editar agente/instrumento sem perder a aba/lista de fundo.
4. **Master-detail sem navegação** — Execuções (lista↔detalhe) e Conversas (two-pane) resolvem detalhe sem sair.
5. **Cross-links inteligentes** — "Aguardando você" e "Execuções recentes" no Início levam direto ao item certo; "Editar automação" salta pra aba.
6. **Indicador de atenção** na aba quando algo pede ação.
7. **Deep-link por aba e por item** — compartilhável e com voltar do navegador.
8. **Estado de espera-por-humano** vivido dentro da execução (aprovar/ajustar inline).

### Sugestões para uma próxima rodada (não implementadas)
- **Busca/atalho global** (Cmd-K) para pular entre agentes/execuções.
- **Abas adaptativas por tipo de time**: um time sem canal não mostra "Conversas" (ou mostra empty state); um time só de automação destaca "Execuções".
- **Edição inline com IA companheira** integrada ao drawer (o "Melhorar com a IA" abrindo um mini-chat).
- **Comparar execuções** lado a lado.

---

## 6. Dados (mapa para o cérebro)
Mesma base do handoff anterior (`design_handoff_batuta_ai_first/README.md` §9). Resumo do que cada aba lê:
- **Início**: `times`, `automacoes` (gatilho, cadeia), agregados de `execucoes` (custo, taxa de sucesso).
- **Agentes**: `agentes` (`agent_md`, `skill_md`, `tools_md`, `soul_md`, `modelo_ia`), `agente_instrumentos`.
- **Instrumentos**: `instrumentos` (`slug`, `tipo`, `exige_aprovacao`), relação com agentes.
- **Automações**: `automacoes` (`tipo_gatilho`, `config_gatilho`, `cadeia` JSONB com nós/saídas/portões).
- **Execuções**: `execucoes` + `passos_execucao` (estado, entrada, saída, tokens, datas); retomar portão via `POST /execucoes/{id}/responder`.
- **Conversas**: `conversas` + mensagens por canal; "assumir atendimento" muda o dono da conversa para humano.
- **Gating por papel** (`lib/permissoes.ts`): Observador responde portões; Operador edita/dispara; Admin remove/troca chaves.

Os textos dos agentes (agent/skill/tools/soul) e a cadeia no arquivo de design são os **reais** do time Conteúdo Controladoria — bons como dados de teste.

---

## 7. Tokens, componentes e arquivos
- **Visual:** segue o `DESIGN-SYSTEM.md` (já resumido em `design_handoff_batuta_ai_first/README.md` §11). Sentence case; Inter 400/500; Bricolage nos títulos; roxo `#6D4AFF` precioso; off-white `#FAFAF7`; flat.
- **Componentes shadcn:** abas = `Tabs` (ou nav + rota); drawers = `Sheet side="right"`; cards = `Card`; badges = `Badge`; filtros = `ToggleGroup`/`Button` pill; toasts = `sonner`. RobotFace = componente custom (ver §6.1 do handoff anterior).
- **Arquivos de design desta entrega** (referência):
  - `Batuta — Página do Time.html` — entrada; renderiza `TeamApp`.
  - `app-data-team.jsx` — dados reais (time, agentes, instrumentos, automação, execuções, conversas).
  - `app-team-workspace.jsx` — cabeçalho persistente + barra de abas + roteamento + toasts.
  - `app-team.jsx` — sidebar real + abas Início/Agentes/Instrumentos + cards + cadeia.
  - `app-team-editors.jsx` — editores de agente e instrumento (drawers) + aba Automações.
  - `app-team-runs.jsx` — aba Execuções (lista + detalhe passo a passo + portão).
  - `app-team-convos.jsx` — aba Conversas (two-pane).
  - Reusa: `app-icons.jsx` (lucide), e de `app-creation.jsx`/`app-dashboard.jsx` os primitivos `RobotFace`, `StatusBadge`, `ExecBadge`, `SectionLabel`.

---

## 8. Ordem de implementação sugerida
1. **Cabeçalho persistente + barra de abas + roteamento** (rotas por aba, deep-link).
2. Migrar conteúdo das páginas atuais para as abas **Agentes / Instrumentos / Automações** (mover, não recriar — a lógica já existe).
3. **Editores em drawer** (agente, instrumento) substituindo as páginas de edição.
4. **Execuções** como master-detail dentro da aba (reaproveita a tela de inspeção da Etapa 1).
5. **Conversas** two-pane.
6. **Início** com os agregados e cross-links.
7. Indicadores de atenção + Cmd-K (próxima rodada).
