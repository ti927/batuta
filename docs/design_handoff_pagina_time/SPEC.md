# SPEC — Página do Time (abas) · referência técnica para implementação

Complemento estruturado do `README.md`. Aqui estão **rotas, contratos de dados, specs de componente, matriz de estados e critérios de aceite** — o material que o agente de implementação copia direto. O README dá o "porquê"; este arquivo dá o "o quê/como verificar".

> Premissa: implementar no app real (Next.js + TS + Tailwind + shadcn/ui + lucide-react), consumindo o cérebro (FastAPI) pelos clients já existentes. Os `.jsx` deste bundle são **referência visual**, não código de produção.

---

## 1. Rotas (deep-link por aba e por item)

| Rota | Tela | Observações |
|---|---|---|
| `/times/[id]` | Aba **Início** | default ao abrir o time |
| `/times/[id]/agentes` | Aba **Agentes** | |
| `/times/[id]/agentes/[agenteId]` | Editor de agente (drawer sobre a aba) | drawer = rota aninhada; fechar volta a `/agentes` |
| `/times/[id]/instrumentos` | Aba **Instrumentos** | |
| `/times/[id]/instrumentos/[instrId]` | Editor de instrumento (drawer) | |
| `/times/[id]/automacoes` | Aba **Automações** | |
| `/times/[id]/execucoes` | Aba **Execuções** (lista) | |
| `/times/[id]/execucoes/[execId]` | Detalhe da execução (mesma aba) | |
| `/times/[id]/conversas` | Aba **Conversas** (two-pane) | |
| `/times/[id]/conversas/[convId]` | Conversa selecionada | pane direito |

- A aba ativa vem da URL — **não** de `localStorage` (o protótipo usa localStorage só pra sobreviver a refresh durante o design).
- Cabeçalho persistente e barra de abas são **layout** (`app/times/[id]/layout.tsx`); cada aba é uma `page.tsx`.
- Botão "voltar" do navegador deve alternar abas/itens corretamente.

---

## 2. Contratos de dados (TypeScript)

Ajustar nomes aos do cérebro real; estes refletem o que cada tela consome.

```ts
type Papel = 'inicial' | 'agente';
type EstadoExecucao = 'em_andamento' | 'aguardando_humano' | 'concluida' | 'falhou';
type EstadoPasso = 'ok' | 'aguardando' | 'pendente' | 'falhou';
type TipoGatilho = 'manual' | 'agendamento' | 'webhook';

interface Time {
  id: string;
  nome: string;
  resumo: string;
  estado: 'ativo' | 'rascunho';
  // agregados para a aba Início (podem vir de endpoint /resumo):
  custoAcumulado?: string;     // ex. "~US$ 0.74"
  taxaSucesso?: number;        // 0..1
  pendencias?: number;         // execuções aguardando humano
}

interface Agente {
  id: string;
  nome: string;
  papel: Papel;
  cor: string;                 // cor do RobotFace (do tema do agente)
  modelo: string;              // ex. "claude-sonnet-4-6"
  resumo: string;
  gate?: boolean;              // tem portão de aprovação na cadeia
  instrumentos: { id: string; nome: string; icon: string }[];
  docs: { agent: string; skill: string; tools: string; soul: string }; // os 4 markdowns
}

interface Instrumento {
  id: string;
  nome: string;
  slug: string;                // ex. "publicar_wordpress"
  tipo: string;                // "WordPress" | "Busca" | ...
  icon: string;
  exigeAprovacao: boolean;
  descricao: string;
  usadoPor: string[];          // nomes de agentes
}

interface SaidaAgente {
  agente: string;
  inicial?: boolean;
  gate: boolean;               // portão de aprovação neste agente
  rotulo: string;              // ex. "tema escolhido"
  destino: string;             // nome de agente | "fim"
}
interface Automacao {
  id: string;
  nome: string;
  gatilho: TipoGatilho;
  gatilhoConfig?: Record<string, unknown>; // cron, url do webhook, etc.
  inicial: string;             // agente inicial
  saidas: SaidaAgente[];       // a cadeia
}

interface PassoExecucao {
  ref?: string;                // id do agente (ausente em passo de falha/gatilho)
  tipo?: 'falha';
  estado: EstadoPasso;
  dur?: string;                // "9.2s"
  tokens?: string;             // "2.905"
  saida?: string;
  erro?: string;               // passo de falha
  gate?: { resolvido: boolean; decisao?: string; por?: string };
}
interface Execucao {
  id: string;
  estado: EstadoExecucao;
  quando: string;
  dur: string;
  custo: string;
  entrada: string;
  passos: PassoExecucao[];
  artigo?: { titulo: string; meta: string; palavras: number; categoria: string }; // p/ portão
  uso?: string;                // linha de uso estimado
}

interface Mensagem { de: 'contato' | 'ia' | 'sistema'; txt: string; hora: string; }
interface Conversa {
  id: string;
  contato: string;
  canal: string;               // "Telegram" | "WhatsApp" | ...
  estado: 'andamento' | 'fechada';
  humano: boolean;             // foi assumida por humano
  turnos: number;
  quando: string;
  thread: Mensagem[];
}
```

### Endpoints (reuso do cérebro)
- `GET /times/{id}` · `GET /times/{id}/resumo` (agregados do Início)
- `GET/POST/PATCH/DELETE /times/{id}/agentes` · idem `/instrumentos`
- `GET/PATCH /times/{id}/automacao`
- `GET /times/{id}/execucoes` · `GET /execucoes/{id}` · `POST /execucoes/{id}/disparar` · **`POST /execucoes/{id}/responder`** (resolve portão/pergunta)
- `GET /times/{id}/conversas` · `GET /conversas/{id}` · `POST /conversas/{id}/assumir` · `POST /conversas/{id}/responder`
- "Melhorar texto com a IA" (no editor de agente) → endpoint da IA criadora/companheira (tool use).

---

## 3. Componentes (props e estados)

| Componente | shadcn base | Props principais | Estados |
|---|---|---|---|
| `TeamLayout` | — | `time`, `children` | cabeçalho persistente + `TabBar` + slot |
| `TabBar` | `Tabs` ou nav+rota | `tabs[{key,label,icon,count,alerta}]`, `active` | ativa (underline roxo + count `#EFEAFF`), inativa, alerta (ponto roxo) |
| `TabInicio` | — | `time`, agregados | loading / pronto / pendência (card âmbar clicável) |
| `AgentCard` | `Card` | `agente`, `onEdit` | default / hover (eleva) |
| `AgentEditor` | `Sheet` (560px) | `agente`, `onSave`, `onClose`, `onDelete` | aba md (agent/skill/tools/soul), dirty (Salvar habilita), salvando |
| `InstrumentEditor` | `Sheet` (480px) | `instrumento`, `onSave`, `onClose` | toggle aprovação on/off |
| `AutomacaoBuilder` | `Card`+`ToggleGroup` | `automacao`, `onSave` | gatilho selecionado, saída com/sem portão |
| `ExecucoesList` | `Card`+pills | `execucoes`, `filtro` | loading / vazio / filtrado |
| `ExecucaoDetail` | — | `execucao`, `onBack`, `onResponder` | normal / **aguardando_humano** (portão) / publicando / concluída / falha |
| `ConversasPane` | two-pane | `conversas`, `selId` | lista + thread; aberta (input) / fechada (rodapé encerrado) / com humano |
| `RobotFace` | custom | `cor`, `size`, `lider?` | — (avatar do agente) |
| `ExecBadge` / `StatusBadge` | `Badge` | `estado` | cores por estado (§4) |

---

## 4. Cores por estado (badges)

| Estado | Texto | Fundo | Ícone lucide |
|---|---|---|---|
| ativo / concluída / ok | `#3DAA5C` | `#E6F4EA` | check-circle / check |
| aguardando você / portão | `#E89638` | `#FDF1E3` | clock / message |
| em andamento / rascunho | `#6D4AFF` / `#E89638` | `#EFEAFF` / `#FDF1E3` | loader (spin) / pencil |
| falhou | `#E5484D` | `#FDECEC` | alert / x |
| neutro (fechada) | `#6B6880` | `#F0EEF6` | — |

Tokens completos de cor/tipo/espaçamento: ver `DESIGN-SYSTEM.md` e `design_handoff_batuta_ai_first/README.md` §11.

---

## 5. Matriz de estados por aba (loading / vazio / erro / especial)

- **Início:** loading (skeletons nos cards) · sem execuções ainda (empty com mascote + "rode pela primeira vez") · pendência (card "Aguardando você" âmbar).
- **Agentes:** vazio = empty com "+ Novo agente"; erro de save no drawer = inline.
- **Instrumentos:** vazio = empty; badge `exige aprovação` quando aplicável.
- **Automações:** sem cadeia = estado "monte a cadeia"; validação (agente sem destino = encerra cadeia, avisar).
- **Execuções:** loading (linhas skeleton) · vazio ("nenhuma execução — Rodar agora") · detalhe `aguardando_humano` = painel de portão · `falhou` = passo vermelho com erro.
- **Conversas:** vazio (time sem canal = empty explicando que precisa conectar um canal) · andamento (input ativo) · com humano (badge).

---

## 6. Permissões por papel (gating de UI)
- **Observador:** vê tudo; pode responder portões/perguntas (aprovar/reprovar) e assumir conversa; **não** edita agentes/instrumentos/automação.
- **Operador:** tudo do observador + criar/editar/remover agentes, instrumentos, automação; disparar execução.
- **Admin:** tudo + remover time, trocar chaves.
- Esconder/desabilitar botões ("Novo agente", "Salvar", "Remover", "Rodar agora") conforme `lib/permissoes.ts`.

---

## 7. Critérios de aceite (checklist)

**Estrutura**
- [ ] Cabeçalho do time (nome, status, "Conversar", "Rodar agora") fixo em todas as abas.
- [ ] 6 abas com contadores corretos; aba ativa com underline roxo; ponto de alerta quando há conversa em andamento.
- [ ] Cada aba é rota real; deep-link e voltar do navegador funcionam.

**Agentes / Instrumentos**
- [ ] Card → drawer abre sobre a aba (fundo preservado); `Esc` fecha.
- [ ] Editor de agente: 4 markdowns editáveis, seletor de modelo, cinto; "Salvar" só habilita com mudança.
- [ ] Editor de instrumento: toggle "exige aprovação" persiste.

**Automações**
- [ ] Trocar gatilho (Manual/Agendamento/Webhook) reflete config; cadeia com rótulo+destino por agente; portão marcado.

**Execuções**
- [ ] Lista com filtros e contagens; abrir = detalhe na mesma aba ("← Todas as execuções").
- [ ] `aguardando_humano`: portão com "Aprovar e publicar" → publica → conclui; passo do publisher atualiza.
- [ ] `falhou`: passo vermelho com a mensagem de erro real; uso estimado no rodapé.

**Conversas**
- [ ] Two-pane; selecionar atualiza thread; "assumir atendimento" muda o dono; fechada mostra rodapé encerrado.

**Transversais**
- [ ] Gating por papel aplicado.
- [ ] Estados de loading/vazio/erro por aba.
- [ ] Sentence case; Inter 400/500; sem bold na UI; roxo só em CTA/links/marca.

---

## 8. Como ler os arquivos de design
- Abrir `Batuta — Página do Time.html` no navegador = ver o comportamento real (clicar abas, abrir editores, aprovar portão, navegar conversas).
- Os valores exatos (paddings, tamanhos, cores) estão nos `.jsx` como estilos inline — traduzir para classes Tailwind/tokens, **não** copiar estilo inline.
- `app-data-team.jsx` = dados de teste reais (use como fixture).
- Screenshots por aba/estado em `screenshots/` (verdade visual do alvo).
