# Handoff: Criação AI-first, Dashboard, Inspeção de execução e IA companheira

> Pacote de handoff de design para o Claude Code. Cobre as telas desenhadas no protótipo de alta fidelidade do Batuta e como recriá-las no sistema real.

> **⚠️ [Atualizado 2026-07-26] Dois pontos deste handoff foram SUPERADOS pela evolução do produto — não os siga:**
> **(1)** O fluxo de **"rascunho + aprovar e criar time"** (a criação que "só vira definitiva ao ser aprovada", item 1 do Overview) foi **revertido**: hoje a IA criadora opera numa **conversa única e eterna sobre o time real** (`MIGRACAO.md` Fase 9), sem ritual de aprovar-e-criar. **(2)** A navegação com **"Execuções" no topo / rota global `/execucoes`** foi **removida**: tudo de um time vive em `/times/[id]` (abas). O restante do handoff (dashboard, inspeção, IA companheira, shell sidebar) segue válido.

---

## 1. Overview

Este pacote contém o design de quatro áreas centrais do Batuta, todas dentro do shell de navegação padrão (sidebar escura + área de conteúdo clara):

1. **Criação AI-first** — o consultor monta um time conversando com a **IA criadora**; o time se materializa em rascunho do lado direito, peça por peça, e só vira definitivo ao ser aprovado. (Corresponde à **Fase 9** do `BUILD-PLAN.md` / `MIGRACAO.md`.)
2. **Dashboard do time** — visão geral de um time já ativo (Time de Blog SEO): próxima execução, aprovações pendentes, custo do mês, a cadeia visual, execuções recentes e os agentes.
3. **Inspeção de execução** — a orquestração passo a passo (o que cada agente recebeu/produziu, tokens, duração) + a **espera-por-humano** nas três formas (pergunta pontual, portão de aprovação, confirmação de baixa confiança). O portão de aprovação é interativo. (Refina a tela de inspeção já existente da Etapa 1 com o `DESIGN-SYSTEM.md`.)
4. **IA companheira** — conversa viva sobre um projeto existente, com painel de memória (estado atual, histórico, decisões lembradas). (Corresponde à **Fase 10**.)

A metáfora condutora (PRODUTO §2) e o princípio "compor peças prontas, sem programar" (PRODUTO §3) guiam cada decisão visual.

---

## 2. Sobre os arquivos de design (LEIA PRIMEIRO)

Os arquivos `.html`/`.jsx` deste bundle são **referências de design** — protótipos em HTML+React (via Babel no navegador) que mostram **aparência e comportamento pretendidos**. **Não são código de produção pra copiar e colar.**

A tarefa é **recriar estas telas no ambiente já existente do Batuta**, seguindo os padrões dele:

- **Interface:** Next.js 16 + TypeScript + Tailwind + **shadcn/ui** (já instalado), ícones **lucide-react**.
- **Cérebro:** FastAPI (Python), consumido pela interface via `lib/api.ts` (navegador) e `lib/cerebro-servidor.ts` (Server Components), com o token do Supabase encaminhado.
- **Padrão de tela:** Server Component (busca) + ilha cliente (mutação) + `router.refresh()`, como já estabelecido nas Fases 2–7.

Onde o protótipo usa estilos inline e dados fake (o time de Blog SEO hardcoded), o sistema real usa **classes Tailwind/tokens do `DESIGN-SYSTEM.md`** e **dados reais do cérebro**. A seção 9 mapeia os dados.

---

## 3. Fidelidade

**Alta fidelidade (hi-fi).** Cores, tipografia, espaçamento, raios, estados e microinterações são finais e seguem o `DESIGN-SYSTEM.md` v1.1. Recriar pixel-a-pixel usando os componentes shadcn existentes. Onde um valor não estiver no design system, os valores exatos estão aqui.

**Vocabulário (decisão do `DESIGN-SYSTEM.md`, Estado de implementação Fase 8):** nas telas de operador vale **Agente / Instrumento / Automação** — NÃO a tradução "Assistente/Habilidade" do tom de voz, que fica reservada à futura camada do cliente final. **Sentence case sempre.** Pesos de fonte só 400 e 500 (bold proibido na UI).

---

## 4. Mapa: componente do protótipo → shadcn/ui

| No protótipo | No sistema (shadcn/Tailwind) |
|---|---|
| `btn-primary` (roxo) | `<Button>` (variant default, cor primária = Roxo Batuta) |
| `btn-ghost` (outline) | `<Button variant="outline">` |
| `chip-btn` (sugestão de resposta) | `<Button variant="outline" size="sm">` arredondado (`rounded-full`) |
| Cards (`#fff`, borda `#E8E6F0`, `rounded-lg`, sem sombra) | `<Card>` |
| Badges de status | `<Badge>` com as variações de cor do DS §9 |
| Drawer do agente | `<Sheet side="right">` |
| Painel de aprovação / proposta | `<Card>` com fundo de destaque (gradiente sutil) |
| Campo de texto / textarea | `<Input>` / `<Textarea>` |
| Toasts | `sonner` (já no shadcn) |
| Robozinho do agente (`RobotFace`) | componente novo — ver §6.1 |
| Mascote / símbolo | imagens em `public/` — ver §10 |

---

## 5. Shell de navegação (comum a todas as telas)

- **Sidebar fixa à esquerda, 246px, fundo `#1A1730` (Roxo Escuro), texto claro.** É a única superfície escura do app — escolha deliberada de marca.
  - Topo: logotipo = `simbolo.png` (28–30px) + "Batuta" em **Bricolage Grotesque 600**, off-white.
  - Botão primário roxo **"Criar com a IA"** (ícone `sparkles`) → leva ao fluxo de criação.
  - Nav primária (ícones lucide 18px): Início (`home`), **Times** (`users`, expansível, lista os times), Execuções (`activity`), Biblioteca (`library`), Uso e custos (`gauge`).
  - Item ativo: fundo `#6D4AFF`, texto branco, `rounded-md`. Hover: `rgba(255,255,255,.07)`.
  - Sub-itens de time recuados, com borda-guia à esquerda `rgba(255,255,255,.1)`.
  - Divisor, depois nav da organização: Acesso e papéis (`shield`), Chaves de IA (`key`), Configurações (`settings`).
  - Rodapé: seletor de organização (avatar quadrado + nome + `chevron-down`) e chip do usuário (avatar circular com iniciais + nome + papel).
- **Header da área de conteúdo:** 56px, fundo branco, borda inferior `#E8E6F0`. Breadcrumb à esquerda (cinza `#A09DB8` → último item `#1A1730` peso 500), "Como funciona" (`circle-help`) à direita.
- **Área de conteúdo:** fundo Off-white `#FAFAF7`.

> O protótipo também contém duas variações de navegação exploradas antes (Chat hub, Contexto do time) em `app-shell.jsx` — **NÃO implementar**. A decisão do maestro foi **Sidebar**. Estão no arquivo apenas como histórico.

---

## 6. Telas

### 6.0 Padrões visuais transversais
- **Container de conteúdo:** centralizado, `max-width` ~1000px (dashboard), ~820px (execução). Padding 28–36px.
- **Section label:** ícone roxo 15px + texto peso 500 + contagem opcional cinza + linha-régua `#E8E6F0` preenchendo o resto. Margem 24px acima / 12px abaixo.
- **Animação de entrada (`rise`):** translateY(9px)→0 em 420ms `cubic-bezier(.2,.7,.3,1)`. **Regra crítica:** o estado de repouso é sempre visível (`opacity:1`); a animação NÃO anima opacity. Nunca deixar conteúdo dependente da animação pra aparecer (em `prefers-reduced-motion`, sem animação). Use Framer Motion no sistema (decisão do DS §13), respeitando essa regra.

### 6.1 RobotFace (avatar de agente) — componente novo
Reflete os robôs do mascote. Quadrado arredondado (`borderRadius` = 32% do lado), cor de fundo = cor do agente. Dentro, um "visor" `rgba(20,16,40,.85)` (~60%×44% do lado, `borderRadius` 16%) com dois olhos brancos circulares (12% do lado cada, gap 12%). Sombra interna sutil embaixo. **Líder** ganha um pequeno sparkle amarelo (`#F5C44A`, contorno `#1A1730`) no canto superior direito.
- Cores dos agentes (do mascote): ciano `#3DD8C3`, lilás `#B19CD9`, roxo `#6D4AFF`, amarelo `#F5C44A`. Líder = amarelo + sparkle.
- Tamanhos usados: 24, 28, 30, 40, 44px.

### 6.2 Criação AI-first  (`app-creation.jsx`)
**Propósito:** criar um time inteiro por conversa (Virada 2). **Layout:** tela dividida.
- **Esquerda — chat (largura fixa 440px, fundo branco, borda direita).**
  - Header: avatar quadrado roxo (gradiente `135deg,#6D4AFF,#8A6BFF`) com `sparkles` branco + "IA criadora" / subtítulo.
  - Mensagens (scroll, auto-rola pro fim): bolha da IA = fundo `#F4F1FE`, texto `#2A2150`, cantos `4px 14px 14px 14px`; bolha do usuário = fundo `#1A1730`, texto branco, cantos `14px 14px 4px 14px`. Tamanho 14px, line-height 1.55, max-width 88%.
  - **Typing indicator:** 3 bolinhas `#B7A8F0` 7px com bounce escalonado (delays 0/.15/.3s).
  - **Chips de resposta** (sugestões): pílulas brancas, borda `#D6D3E8`, texto `#3D2A99`, hover borda roxa + fundo `#F4F1FE`. Empilhadas, alinhadas à esquerda.
  - **Card de aprovação** (no fim): fundo gradiente lavanda→creme, borda `#E6DEFB`. Texto "Tudo em rascunho. Ao aprovar, eu crio o time, os 5 agentes, o gatilho e a cadeia de uma vez." + botão primário **"Aprovar e criar time"** (largura total).
  - **Card de sucesso** (pós-aprovação): fundo `#E6F4EA`, texto verde; o input passa de "Responder à IA criadora…" para **"Pedir um ajuste à IA companheira…"** (transição criadora→companheira).
  - Input no rodapé: campo + botão de enviar roxo (36×36, ícone `send`).
- **Direita — canvas do rascunho (flex, fundo `#FAFAF7`, scroll).** Conteúdo centralizado `max-width` 640px.
  - **Estado vazio** (antes de montar): mascote (`mascote.png`, ~280px) + "O time aparece aqui" + explicação. (Toggle de mascote vira ícone `layers` em `#EFEAFF` se desligado — ver Tweaks; no sistema, pode ser sempre o mascote.)
  - Ao montar: header do time (nome em Bricolage 22px + badge de status `rascunho`/`ativo` + linha "Clínica Aurora · cliente da consultoria").
  - Seção **Agentes**: cards empilhados (ver 6.5), revelados com stagger de 90ms.
  - Seção **Gatilho**: card com ícone `clock` em `#EFEAFF` + tipo + detalhe.
  - Seção **Cadeia**: pipeline **vertical** — cada nó é um card (gatilho/agente/portão/fim) ligado por um segmento vertical `#D6D3E8`. Portão = ícone `message` laranja "Espera você responder no WhatsApp".
  - Seção **Custo estimado**: card com dois números grandes em Bricolage (por artigo / por mês) separados por divisor.
- **Comportamento:** roteiro conduz a conversa (ver §8). Cada escolha do usuário revela a próxima fala da IA + dispara efeitos no canvas. Modo rascunho até "Aprovar" (Fase 9 exige: nada vira definitivo sem aprovação humana explícita; ver `MIGRACAO §6.4`).

### 6.3 Dashboard do time  (`app-dashboard.jsx`)
**Propósito:** hub de um time ativo. **Layout:** coluna única, `max-width` 1000px.
- **Cabeçalho:** nome (Bricolage 27px, line-height 1.2) + badge `ativo` (verde); subtítulo; à direita "Conversar sobre o projeto" (ghost, → companheira) + "Rodar agora" (primário, `play`).
- **3 stat cards** (flex, gap 14): Próxima execução (`clock`, roxo), **Aguardando você** (`message`, laranja — borda de acento `#F0D9B8`, clicável → execução), Custo no mês (`gauge`, verde). Valor em Bricolage 24px.
- **Cadeia horizontal:** card branco com os nós em linha (RobotFace + nome), ligados por `chevron-right` cinza, com wrap.
- **Execuções recentes:** card com linhas clicáveis → inspeção. Cada linha: id mono, data, **badge de estado**, nota opcional, duração, custo, `chevron-right`. Hover destaca a linha.
- **Agentes:** grid 2 colunas dos cards de agente.

### 6.4 Inspeção de execução + espera-por-humano  (`app-execution.jsx`)
**Propósito:** auditar uma execução passo a passo e responder pausas. **Layout:** coluna única `max-width` 820px.
- **Voltar ao time** (link). **Cabeçalho:** "Execução #1284" (Bricolage + id mono) + badge de estado; meta em linha: gatilho (`zap`), quando (`clock`), custo até agora (`gauge`).
- **Painel de aprovação** (só quando `aguardando_humano`): fundo gradiente creme, borda `#F0E2C0`. "O fluxo está esperando você" + badge. Card branco com o rascunho do artigo (título, meta, chips de palavras/categoria/SEO). Botões **"Aprovar e publicar"** (primário; vira "Publicando…" com spinner) e **"Pedir um ajuste"** (ghost → abre textarea → "Enviar ajuste"). Abaixo, **legenda das três formas** de espera-por-humano (cards lado a lado: pergunta pontual `circle-help`, portão de aprovação `shield`, confirmação de baixa confiança `alert`).
- **Passo a passo** (timeline vertical): cada passo tem um **dot** (círculo com anel da cor do estado: ok=verde+check, aguardando=laranja+clock, rodando=roxo+loader girando, pendente=cinza vazio, falhou=vermelho+x) ligado por linha vertical `#EDEBF4`. Card do passo: RobotFace/ícone + nome + tokens + duração + chevron (expansível). Expandido mostra **Recebeu** / **Perguntou a um humano** (Q&A, fundo creme) / **Produziu** em blocos rotulados.
- **Interação:** aprovar → passo do publisher vai a `rodando` (~1,9s) → `concluída`; toast "Artigo publicado ✨"; custo e badge atualizam. Estados derivados do status geral (`aguardando_humano` | `publicando` | `concluida` | `falhou`).
- **Falha (PRODUTO §16):** quando `falhou`, o passo do publisher mostra ícone vermelho + nota "WordPress não respondeu. Tentou 2 vezes, esperou e avisou o líder — nada publicado pela metade." Nunca falha em silêncio.

### 6.5 Card de agente + Drawer (`app-creation.jsx`)
- **Card:** RobotFace 40px + nome (+ badge "líder") + resumo + linha de metadados (modelo `sparkles` roxo + instrumentos como chips com ícone). Hover: borda `#D6D3E8`, leve elevação. Clique → drawer.
- **Drawer (Sheet à direita, 460px):** header com RobotFace 44px + nome + badge rascunho + resumo + botão fechar (`x`, `aria-label="Fechar"`). Linha de chips: modelo+tier, instrumentos. Corpo: os **4 markdowns** — cada um com ícone roxo + rótulo ("Quem é"/"Habilidades"/"Cinto de instrumentos"/"Personalidade") + tag mono do arquivo (`agent.md` etc.) + bloco de conteúdo (fundo `#FAFAF7`, `whitespace: pre-wrap`). Rodapé: "Ajustar com a IA" (ghost).

### 6.6 IA companheira  (`app-companion.jsx`)
**Propósito:** conversar sobre um projeto existente, com memória (Virada 3). **Layout:** tela dividida.
- **Esquerda — chat (460px):** igual ao da criadora, mas avatar com gradiente **ciano→roxo** (`135deg,#3DD8C3,#6D4AFF`), título "IA companheira" / "Conhece o Time de Blog SEO desde o início". Roteiro em §8. Quando propõe mudança: card "Mudança proposta · rascunho" mostrando `8h → 7h` + "Aplicar mudança" → toast "Horário atualizado".
- **Direita — painel de memória ("O que eu sei deste projeto"):** três cards, cada um com rótulo de origem da camada:
  - **Estado atual** (`layers`) — "consultado ao vivo no banco" (conhecimento estrutural via tool use, MIGRACAO §3.6).
  - **Últimas execuções** (`activity`) — "histórico do projeto" (conversas/execuções).
  - **Decisões lembradas** (`sparkles`) — "memória de longo prazo" (vetorial/destilada).
  - Itens com bullet lilás `#B19CD9`.

### 6.7 Placeholder (áreas fora do escopo deste protótipo)
Biblioteca, Uso e custos, Acesso, Chaves, Configurações, outros times → tela centrada com mascote + "{Área}" + nota honesta. No sistema, substituir pelas telas reais correspondentes (várias já existem das Fases 2–7).

---

## 7. Interações & comportamento (resumo)
- **Navegação:** SPA-like no protótipo; no Next.js, rotas reais (ex.: `/times/[id]`, `/times/[id]/criar`, `/execucoes/[id]`, `/times/[id]/conversa`). Sidebar destaca o item ativo.
- **Auto-scroll do chat** ao chegar mensagem nova.
- **Modo rascunho** (criação e companheira): a IA propõe; o humano confirma; só então escreve no banco. Botão de desfazer/descartar a sessão (MIGRACAO Fase 9).
- **Espera-por-humano:** uma execução pode pausar e retomar (já existe no core, Etapa 1). A UI precisa: responder pergunta pontual, aprovar/reprovar portão, confirmar baixa confiança.
- **Custo visível** (PRODUTO §21): estimativa antes (criação) e consumo real depois (inspeção/uso).
- **Transições/animações:** 150ms em hovers; `rise` 420ms nas entradas; toasts via sonner (bottom-right, ~4s).

---

## 8. Roteiros de conversa (conteúdo exato)
Os textos das conversas (criadora e companheira) e os dados do time de exemplo estão em **`app-data.jsx`** (`STEPS`, `COMPANION_STEPS`, `TEAM`, `CADEIA`, `EXEC`, `RECENTES`, `MEMORIA`). No sistema real esses textos vêm da IA (tool use) — use-os como **referência de tom e formato** (PT-BR, sentence case, sem jargão, acolhedor e direto; PRODUTO/DESIGN-SYSTEM §2).

---

## 9. Dados (mapa para o cérebro)
O protótipo usa dados fake. No sistema, puxar das tabelas/endpoints existentes (BUILD-PLAN Fase 1 + adições MIGRACAO §5):
- **Time / agentes / instrumentos:** `times`, `agentes` (campos `papel`, `agent_md`, `skill_md`, `tools_md`, `soul_md`, `modelo_ia`), `instrumentos`, `agente_instrumentos`. Drawer = leitura desses campos.
- **Cadeia / gatilho:** `automacoes` (`tipo_gatilho`, `config_gatilho`, `cadeia` JSONB = grafo de nós). A cadeia visual lê esse grafo.
- **Execução / passos:** `execucoes` (`estado`: aguardando | em_andamento | aguardando_humano | concluida | falhou; entrada; resultado) e `passos_execucao` (ordem, agente, entrada, saída, estado, datas). Timeline = `passos_execucao`. Tokens/custo via medição de uso (Fase 5.4 / 7.6, `uso` por passo + origem da chave).
- **Espera-por-humano:** retomar via `POST /execucoes/{id}/responder` (já existe).
- **IA criadora/companheira:** `conversas_criacao` (a conversa eterna por projeto, com histórico) e `memorias_projeto` (memória de longo prazo — **destilada, não vetorial**: fatos/decisões/preferências curados pela IA, isolados por projeto; Fase 10). Tool use chamando as operações existentes (criar time/agente, configurar instrumento, montar automação) + `lembrar`/`recordar`/`esquecer`. Chave resolvida por projeto→consultoria→`.env` (Fase 7).
- **Papéis:** Observador responde portões/perguntas; Operador cria/edita/dispara; Admin troca chaves/apaga (MIGRACAO §3.7). Gating de UI por papel (já há `lib/permissoes.ts`).

---

## 10. Assets
Em `assets/` (copiar para `interface/public/` no sistema):
- `simbolo.png` — símbolo (batuta + ondas), recortado sem wordmark. Header/sidebar, favicon.
- `mascote.png` — maestro + 4 robôs, sem texto. Estados iniciais/vazios.
- `mascote-completo.png` — lockup completo (mascote + "Batuta" + tagline). Boas-vindas/onboarding.
- `logo-lockup.png` — símbolo + wordmark.
- **Originais são PNG** (o cliente ainda não tem SVG). Recomendado vetorizar para nitidez em telas grandes/retina e gerar o kit de favicon (DS §3, §13 TODO).
- Cores dos robôs do mascote já incorporadas como cores de agente (§6.1).

---

## 11. Design tokens
A fonte da verdade é o **`DESIGN-SYSTEM.md` v1.1** (paleta, tipografia, espaçamento, raios, sombras, ícones). Resumo dos usados aqui:
- **Cores:** Roxo `#6D4AFF` (hover `#5A3FE0`, light `#EFEAFF`, texto `#3D2A99`); Off-white `#FAFAF7`; Escuro `#1A1730`; Ciano `#3DD8C3`; Amarelo `#F5C44A`; Lilás `#B19CD9`; Verde `#3DAA5C`/`#E6F4EA`; Laranja `#E89638`/`#FDF1E3`; Erro `#E5484D`/`#FDECEC`. Texto 2ário `#6B6880`, 3ário `#A09DB8`; bordas `#E8E6F0`/`#D6D3E8`. Bolha IA `#F4F1FE`.
- **Tipografia:** Inter (UI, pesos 400/500) + Bricolage Grotesque (logotipo e títulos de marca, 500/600). Sentence case. Tamanhos: page title 24–27px, section 14–18px, body 14–15px, caption 12–13px.
- **Raios:** 6px (botões/inputs), 8–10px (cards), 12px (containers destacados), 999px (pílulas/avatares).
- **Sombras:** quase nenhuma (flat). Drawer/toast com sombra suave apenas.
- **Espaçamento:** escala 4px (4/8/12/16/24/32/48/64).

---

## 12. Arquivos deste bundle
- `Batuta — Criação AI-first.html` — entrada; carrega React/Babel, fontes, monta o `App` (roteador de telas) + Tweaks.
- `app-icons.jsx` — ícones lucide como componentes (`Icon`).
- `app-data.jsx` — dados/roteiros do cenário de exemplo (Blog SEO).
- `app-creation.jsx` — criação AI-first (chat + canvas + card/drawer de agente).
- `app-dashboard.jsx` — dashboard do time (+ `ExecBadge`, cadeia horizontal).
- `app-execution.jsx` — inspeção de execução + espera-por-humano.
- `app-companion.jsx` — IA companheira + painel de memória.
- `app-shell.jsx` — shell sidebar (e as variações Chat hub/Contexto NÃO usadas).
- `tweaks-panel.jsx` — painel de tweaks do protótipo (não faz parte do produto).
- `assets/` — mascote e símbolo.

**Para ver o protótipo funcionando:** abra o `.html` num navegador e navegue pela sidebar. É a referência viva do comportamento.

### Screenshots (`screenshots/`)
Capturas de referência das telas (largura do preview; em desktop ≥1200px o painel direito tem folga total):
- `01-dashboard.png` — Dashboard do time
- `02-criacao-ai-first.png` — Criação AI-first (estado inicial / IA criadora)
- `03-execucao-espera-humano.png` — Inspeção de execução com o portão de aprovação
- `04-ia-companheira.png` — IA companheira + painel de memória

---

## 13. Sugestão de ordem de implementação
1. **RobotFace** + tokens/primitivos shadcn confirmados.
2. **Shell sidebar** + header/breadcrumb + gating por papel.
3. **Drawer/editor de agente** (lê os 4 markdowns — já há base na Fase 2).
4. **Dashboard do time** (lê automação/cadeia/execuções).
5. **Inspeção de execução** + **espera-por-humano** (refina a tela crua da Etapa 1).
6. **Criação AI-first** (Fase 9 — modo rascunho primeiro, depois conectar a IA criadora via tool use).
7. **IA companheira** (Fase 10 — memória isolada por projeto; testar contaminação, MIGRACAO §6.4).
