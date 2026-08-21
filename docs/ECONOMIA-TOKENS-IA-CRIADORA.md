# Economia de tokens da IA criadora — resumo rolante (`projeto.md`) + iceberg + cache + foto enxuta

> **Status:** ✅ **100% NO AR (partes A–E), 2026-07-27.** Plano aprovado pelo maestro (2026-07-21) e **executado por inteiro**: **A** resumo rolante + janela · **B** painel "Sobre este time" · **C** busca no iceberg · **D** cache Anthropic · **E** foto enxuta — todas em produção (ver o selo `✅ NO AR` em cada parte abaixo). **Falta só um teste ao vivo dedicado** (as peças foram medidas isoladas: A −62% de histórico, D ~88% de economia por turno). Este é o documento-fonte da **Frente B (autoria)** do **Programa de Unificação de Estado** (âncora: `docs/UNIFICACAO-ESTADO.md`) — mesma doença (turno sem memória) da Frente A (runtime, `docs/REMODELAGEM-MOTOR.md`). O `BUILD-PLAN.md` aponta para o programa.

## Contexto

A IA criadora/companheira é **uma conversa eterna por time**. Hoje, a cada turno, o `criacao/loop.py` (`responder_turno`) **remonta e reenvia a conversa inteira** ao modelo (`_historico_para_mensagens(conversa.mensagens)` — JSONB *append-only* que nunca é podado nem resumido), **mais** o prompt de sistema completo (`montar_prompt_criadora`: base + catálogo de instrumentos + "fotografia do time" + memória). Resultado: num time antigo (~100 turnos) são ~75 mil tokens só de histórico + ~15–40 mil do prompt fixo, **reenviados todo turno** → ~US$0,30 de entrada por turno na Sonnet 5, e piorando. O maestro sentiu isso ("fica caro demais") e sugeriu um `projeto.md` (resumo na linguagem da IA).

**Já contido:** resultados de ferramenta são truncados a 500 chars ao guardar (`criacao/loop.py`, `_MAX_RESULTADO_FERRAMENTA=500`).

**Decisões do maestro (2026-07-21):**
1. O `projeto.md` (resumo) é **visível e editável** — a IA mantém, ele corrige; vira documentação viva do time.
2. O histórico completo é um **"iceberg" guardado**, com uma ferramenta pra IA **buscar sob demanda** ("um lugar armazenado que eu possa instruir a IA criadora a buscar").

**Resultado desejado:** contexto por turno **limitado** (resumo + poucos turnos recentes), muito mais barato, com transparência (painel) e nada perdido (iceberg + busca).

---

## Abordagem recomendada

### Parte A — Resumo rolante + janela de turnos recentes  ✅ **NO AR (2026-07-26, commit `3621138`)**
> **Como ficou:** migração aditiva `res00rolante01` (`ConversaCriacao.resumo`/`resumo_ate`); `loop.py`
> envia `mensagens[resumo_ate:]` (mantendo `lc` dos turnos recentes) + injeta o resumo no bloco VOLÁTIL do
> prompt (não estraga o cache da Parte D); `criacao/resumo.py` dobra os turnos antigos via **Haiku**,
> chamado em `fila_turnos` **depois** de entregar a resposta (best-effort — se falhar, o turno segue e nada
> se perde). Janela = 16 msgs (~8 turnos). **Prova real: −62% do histórico** (47k→18k) numa conversa de 32
> turnos; 724 testes verdes. Retrocompatível: `resumo_ate=0` = comportamento de antes.

Parar de enviar a conversa inteira. Enviar **`resumo` + os últimos N turnos na íntegra**.
- **Modelo:** 2 colunas aditivas em `ConversaCriacao` (`modelos.py:620`): `resumo` (Text, nullable) e `resumo_ate` (Int, default 0 — quantos turnos iniciais já estão dobrados no resumo). Migração **aditiva** (padrão do projeto).
- **Envio** (`responder_turno` + `_historico_para_mensagens`): montar histórico = **`mensagens[resumo_ate:]`** (janela recente, mantendo o campo `lc` — as chamadas de ferramenta reais). O `resumo` entra como bloco no prompt de sistema (Parte B). Janela N ≈ 6–8 turnos (constante ajustável).
- **Manutenção do resumo** (dentro do processamento do turno, em `fila_turnos`, best-effort, **não bloqueia** a resposta): quando `len(mensagens) - resumo_ate > N`, dobrar os turnos que saíram da janela num resumo incremental — `novo_resumo = resumir(resumo_atual + turnos_saindo)` via **Haiku** (`construir_modelo("claude-haiku-4-5")`, barato) — e avançar `resumo_ate`. Instrução do resumidor: capturar **o que o time é/faz, decisões, preferências e pontas em aberto**, na linguagem da IA.
- **Pegadinha honrada:** manter os últimos N turnos com `lc` verbatim preserva o sinal "nesta conversa, agir = chamar ferramenta" (a nota no topo do `loop.py`). O resumo é texto, mas os turnos recentes seguram o padrão de tool-use.

### Parte B — `projeto.md` visível e editável  (UI)  ✅ **NO AR (2026-07-27, commit `4815f14`)**
> **Como ficou:** o resumo (que a Parte A já mantinha, invisível) virou o painel **"Sobre este time"**
> — um card no painel direito da criadora que **abre um drawer à direita** (mesmo padrão da edição de
> agentes/instrumentos; **desenho escolhido pelo maestro**), onde o resumo é lido e — por **operador+**
> — editado. **A edição humana VENCE a da IA** (o resumidor rolante da Parte A parte do `resumo` atual,
> então a correção humana vira a base a partir da qual a IA refina). **Backend:** `ConversaCriacaoLer`
> expõe `resumo`; `PUT /conversas-criacao/{id}/resumo` (operador+, auditado `criacao.resumo_editado`;
> string vazia → `NULL`). **Front:** componente auto-contido `PainelSobreTime` (`components/conversa-ia/
> painel-sobre-time.tsx`, card + drawer), encaixado nas **duas** superfícies da criadora — `/criar/[id]`
> (`criacao-cliente.tsx`) e o painel companheiro dentro de `/times/[id]` (`painel-time.tsx`). A tela de
> `.../conversas/[conversaId]` que o plano citava é a de **mensageria** (contato↔bot), não a criadora —
> referência corrigida. 748 testes backend + tsc/eslint/`next build` verdes. Sem migração (a coluna
> `resumo` veio na Parte A). **Falta:** teste ao vivo. **Com B, a Frente B está 100% COMPLETA (A–E).**

- **Prompt:** `montar_prompt_criadora` já injeta o `resumo` no bloco volátil (Parte A).
- **Backend:** em `rotas/criacao.py`, o `GET` já traz o `resumo` (em `ConversaCriacaoLer`) e o novo `PUT` do `resumo` é a edição humana (vence a versão da IA).
- **Front:** painel "Sobre este time" na tela da criadora (`interface/app/criar/[id]/criacao-cliente.tsx` e o painel companheiro `components/conversa-ia/painel-time.tsx`) — card + drawer à direita. Tipos + chamadas em `interface/lib/api.ts`.
- A IA pode **propor** atualização (ela vê o resumo no contexto); o humano tem a palavra final via o painel.

> **Acréscimo (2026-07-27, commit `7fb573b`) — a IA ESCREVE o resumo sob comando + o painel busca fresco.**
> No teste ao vivo o maestro pediu *"edite o resumo do projeto"* e a IA mexeu na **descrição do time**
> (outra coisa) — ela **não tinha ferramenta nem o conceito** de "resumo do projeto". Corrigido:
> - **`atualizar_resumo(resumo)`** (`criacao/ferramentas.py`) — a IA escreve o resumo; o prompt
>   (`criacao/prompt.py`, nova seção no `_BASE`) ensina que é **distinto** da descrição do time
>   (`definir_time`) e da memória de longo prazo (`lembrar`), e manda chamar `atualizar_resumo` quando o
>   consultor pedir. (Complementa o resumidor automático da Parte A — que segue dobrando os turnos antigos.)
> - **`GET /conversas-criacao/{id}/resumo`** (leve) + o `PainelSobreTime` busca o resumo **fresco ao abrir
>   o drawer** — antes o painel fixava o valor no load e não refletia o que a IA escrevesse durante a sessão.
> - **Diagnóstico do "resumo vazio" (prod, só leitura, `scratchpad/diag_resumo.py`):** o resumidor
>   automático **FUNCIONA** — a conversa usada hoje (COF Post Blog, 68 msgs) tem resumo de **3096 chars (26
>   turnos condensados)**; **todas** as vazias são conversas **sem atividade desde o deploy da Parte A**
>   (preenchimento preguiçoso por design — `resumo_ate=0` até uma mensagem nova cruzar a janela). Não é bug.
> 750 testes + front verde. Sem migração.

### Parte C — Iceberg: histórico completo + ferramenta de busca  ✅ **NO AR (2026-07-26, commit `1a8712f`)**
> **Como ficou:** ferramenta `buscar_no_historico(consulta)` em `criacao/ferramentas.py` — varre os turnos
> já dobrados (`mensagens[:resumo_ate]`, o que saiu da janela), casa por palavra/trecho e devolve o texto
> original, com teto de resultados/tamanho (a busca é para economia). Entrada em `MENSAGENS_CRIADORA` (feedback
> ao vivo). Fecha a ressalva "resumo com perda" da Parte A. Backend puro (sem migração, sem tela); +2 testes.
- O `conversa.mensagens` **continua guardando tudo** (nada é apagado — só não é tudo enviado).
- Nova ferramenta em `montar_ferramentas` (`ferramentas.py:333`): **`buscar_no_historico(consulta)`** — procura nos turnos **anteriores à janela** (`mensagens[:resumo_ate]`) por palavra/trecho e devolve os turnos casados (texto). Entrada em `MENSAGENS_CRIADORA` (`ferramentas.py:304`) para o feedback ao vivo. Assim o maestro instrui: *"procura no histórico o que combinamos sobre X"*.

### Parte D — Cache de prompt (Anthropic)  ✅ **NO AR (2026-07-26, commit `b28d091`)**
> **Como ficou:** o spike confirmou que `langchain-anthropic 1.4.4` propaga `cache_control` e que
> `create_react_agent` o preserva. Implementado em `criacao/prompt.py` (`montar_system_criadora` +
> `prompt_criadora`, que **só cacheia na Anthropic** — OpenAI/Google recebem texto puro), `criacao/loop.py`
> (capta `cache_read`/`cache_creation` na medição) e `precos.py` (custo cache-aware + correção do preço do
> Opus). **Prova real: ~88% de economia por turno** numa conversa da criadora. 719 testes verdes.
- Marcar o **prefixo estável** do prompt de sistema como cacheável: passar ao `create_react_agent` um `SystemMessage` com blocos de conteúdo levando `cache_control: {"type":"ephemeral"}` — um breakpoint após a parte fixa (base + catálogo + índice de conhecimento) e outro após fotografia + memória + resumo (Anthropic permite até 4). Turnos seguintes na **mesma sessão** pagam ~10% nesse prefixo. **Zero perda de informação.**
- **Viabilidade:** `langchain-anthropic` 1.4.4 propaga `cache_control` em blocos de conteúdo e o `create_react_agent` aceita `SystemMessage` como `prompt` — **confirmar com um spike curto**; fallback: cachear só o prompt de sistema, ou baixar ao SDK `anthropic` neste laço.
- **Opcional:** `precos.py` ler `cache_read_input_tokens`/`cache_creation_input_tokens` do `usage_metadata` para a medição refletir o cache (hoje conta tudo como entrada normal — informativo).
- **Honestidade:** o cache esfria em ~5 min (ou 1h numa variante) → ajuda uma sessão de vários turnos, **não** o primeiríssimo turno ao reabrir um time parado. Quem resolve o "abrir time velho" é a Parte A.

### Parte E — Foto enxuta + detalhe sob demanda  (ganho p/ times grandes)  ✅ **NO AR (2026-07-27, commit `d3ce135`)**
> **Como ficou:** função pura `enxugar_snapshot(foto)` (`criacao/ferramentas.py`) aplicada **só no
> `loop.py`** (a cópia que vai no PROMPT): tira os 4 markdowns de cada agente e a `cadeia` de cada
> automação, mantém a estrutura (id/nome/papel/modelo/cinto; instrumentos INTEIROS — config/
> `acao_irreversivel`/`segredos_pendentes` são pequenos e guiam a decisão). Duas ferramentas novas de
> detalhe sob demanda — **`ver_agente(id)`** (os 4 markdowns + cinto) e **`ver_automacao(id)`** (a
> cadeia) — e o cabeçalho da foto no prompt avisa "só estrutura; peça o detalhe do que este turno
> toca; não adivinhe o texto antes de editar". **A foto CHEIA continua indo para o front** (redesenhar
> o canvas: `rotas/criacao.py` + a resposta do turno) e para o `ver_time` — `enxugar_snapshot` NÃO
> altera aquela, então **zero regressão na tela**. Backend puro, sem migração, sem UI. 743 testes verdes
> (+5 em `test_foto_enxuta.py`). **Falta:** teste ao vivo (abrir um time grande, medir a queda do
> `tokens_entrada` por turno; ver a IA chamar `ver_agente` antes de editar um agente).

- `snapshot_time` (`ferramentas.py`) passa a mandar, **no prompt**, só a **estrutura**: time + agentes (nome/papel/id/modelo/cinto-ids) + instrumentos (inteiros) + automações (nome/gatilho/ativa/id) — **sem** os 4 markdowns de cada agente nem a `cadeia` inteira.
- Ferramenta(s) de detalhe sob demanda: **`ver_agente(agente_id)`** (markdowns) e **`ver_automacao(automacao_id)`** (cadeia). (`ver_time` já existe; estende o padrão.) A IA puxa o detalhe do agente que o turno realmente toca. Corta muito o custo fixo em times grandes.

---

## Sequência / prioridade
1. **A + B + C** — o que o maestro pediu (o `projeto.md` + o iceberg). É o núcleo e o maior ganho no caso "time antigo".
2. **D (cache)** — alívio mais rápido de custo, baixo risco, independente; pode ir em paralelo/primeiro se ele quiser resultado imediato.
3. **E (foto enxuta)** — maior ganho em times grandes; depois de A validado.

Cada parte é verificável e não quebra as outras. Núcleo de orquestração **não** é tocado — tudo vive na borda de criação (`criacao/`) + medição + UI.

## Retrocompatibilidade / riscos
- Migração **aditiva** (`resumo`, `resumo_ate`); histórico preservado (nada de destrutivo).
- Conversas atuais: `resumo_ate=0` → comportamento idêntico ao de hoje até a janela ser excedida (aí começa a dobrar). Sem virada brusca.
- Resumo é "com perda" → mitigado pelo iceberg + `buscar_no_historico` + painel editável.
- Padrão de tool-use preservado (janela recente mantém `lc`).
- Cache: incerteza de fiação do langchain → **spike primeiro**, fallback documentado.

## Verificação
- **Testes:** histórico enviado = `resumo` + últimos N (não tudo); manutenção avança `resumo_ate` e atualiza `resumo`; `buscar_no_historico` acha turno antigo; snapshot enxuto por padrão; `ver_agente` traz o markdown; `PUT` do resumo sobrescreve.
- **Custo (prova):** medir `tokens_entrada` numa conversa longa **antes × depois** (queda forte esperada); com cache, `usage_metadata` mostra `cache_read` nos turnos seguintes.
- **Ao vivo:** abrir um time antigo, trocar vários turnos → custo cai; painel "Sobre este time" mostra/edita o resumo; *"procura no histórico X"* funciona.

## Arquivos-chave
- **Backend:** `cerebro/criacao/loop.py` (janela + injeção do resumo + manutenção), `cerebro/criacao/prompt.py` (bloco do resumo + blocos de cache + texto da foto enxuta), `cerebro/criacao/ferramentas.py` (`buscar_no_historico`, `ver_agente`/`ver_automacao`, `snapshot_time` enxuto, `MENSAGENS_CRIADORA`), `cerebro/criacao/memoria.py` (padrão de referência), `cerebro/modelos.py` (`ConversaCriacao.resumo`/`resumo_ate`), `cerebro/rotas/criacao.py` (GET/PUT resumo), `cerebro/orquestracao/llm.py` (fiação do cache, se preciso), `cerebro/precos.py` (medição cache-aware, opcional), migração aditiva em `cerebro/alembic/`.
- **Front:** `interface/app/criar/[id]/criacao-cliente.tsx`, `interface/app/times/[id]/conversas/[conversaId]/conversa-cliente.tsx`, `interface/components/conversa-ia/usar-conversa.ts`, `interface/lib/api.ts`.

## Relação com outras fases
- **Frente B do Programa de Unificação de Estado** (`docs/UNIFICACAO-ESTADO.md`): esta economia e a **remodelagem do motor** (`docs/REMODELAGEM-MOTOR.md`, Frente A) atacam a **mesma doença-raiz** — o turno que começa do zero e reconstrói o contexto do texto — com a **mesma família de cura** (persistir estado entre turnos). Há uma **tensão a resolver** (persistir tudo × enviar pouco), que só se concilia desenhando as duas juntas e que é o objeto do **estudo de tokens** (Marco 0 do programa). Se viram um só programa ou dois trilhos é a **decisão adiada**.
- **Não confundir** com a [Base de conhecimento centralizada da IA criadora] (que é sobre a criadora *consultar* um catálogo de recursos) nem com a **memória vetorial** da Fase 10 (recuperação semântica). Esta fase é sobre **cortar o custo de contexto** da conversa eterna. A memória de projeto atual (`criacao/memoria.py`, texto/recência) permanece e é complementar ao `resumo`.
- **Batuta-MCP** (`docs/MCP-BATUTA.md`, NO AR 2026-08): alavanca **complementar e ortogonal** contra o mesmo 70%. Em vez de *baratear* a criadora, **move** a criação para o **claude.ai do próprio consultor** (assinatura dele), de forma permitida pela Anthropic. **Coexiste** com a criadora (não a substitui); ataca o custo por fora, tirando-o da conta de API do Batuta.
