# Fatia 4.3 — Plano de produção (Opção A, nativo): sub-fatias estranguladoras

> **Status:** ▶️ **EM EXECUÇÃO. ✅ P0 e ✅ P1 NO AR (2026-08-06). Próxima: P2 (a cura — memória no chat).**
> Decisão de forma tomada (A/nativo) e ampliação de descongelamento nº 3 registrada (`MIGRACAO.md §6.1`).
> Base: [`FATIA-4.3-DECISAO-MEMORIA.md`](FATIA-4.3-DECISAO-MEMORIA.md) (estudo + achados do protótipo).
> Cada sub-fatia começa só com sinal explícito do maestro e tem seu próprio plano+verificação antes do código.

---

## Princípios (valem para todas as sub-fatias)

- **Estrangulador, sem dia-D.** Cada sub-fatia é pequena, deixa a produção **verde** e os testes passando.
  Nunca se trocam os dois mundos ao mesmo tempo. Se o maestro parar em qualquer ponto, o sistema fica coerente.
- **Ponto de parada seguro no meio do caminho:** **após a P2, o "renasce" já está curado no chat** (o agente
  lembra, para de re-buscar) — e o maestro pode **pausar antes** da reescrita do portão (P3, a mais delicada).
  A maior parte do valor vem antes do maior risco.
- **Congelado, inegociável (todas as fatias):** a **garantia HITL de nunca re-disparar ação irreversível**
  (`PRODUTO §14`), a semântica de `seguir_para`, o contrato de instrumentos, a fila `FOR UPDATE SKIP LOCKED`,
  o heartbeat/sweeper/recuperação de órfãos-presos (`CLAUDE.md §12-A`).
- **Rede de segurança:** a tag `pre-fatia-4` + o dump de PROD já existem; cada sub-fatia que mexe em dados
  aditiva-e-reversível, migração preguiçosa, nada destrutivo.
- **Uma fonte de verdade para "precisa de aprovação":** o `interrupt_on` do HITL seletivo é derivado de
  **`instrumentos/base.py::acao_irreversivel(tipo, config)`** — a MESMA regra da parede de ativação. Não se
  cria uma segunda lista de instrumentos irreversíveis.

---

## As sub-fatias (ordem inegociável — risco crescente)

### P0 — Subir o núcleo (dependências) em ISOLAMENTO ⭐ — ✅ NO AR (commit `0d33044`, 2026-08-06)
> `uv add langgraph-checkpoint-postgres langchain` (core 1.4→1.5.3, langgraph 1.2.2→1.2.10). Suíte 761/761
> verde (2ª rodada); app subiu saudável (`/saude`=`0d33044`); zero mudança de comportamento. 1 flaky
> pré-existente (mocka o LLM) à parte.
- **O que muda:** `uv add langgraph-checkpoint-postgres langchain` (deixa `langchain-core`/`langgraph`
  subirem para as versões compatíveis — medido no spike: `langchain-core 1.4→1.5`, `langgraph 1.2.2→1.2.10`).
  **Zero código de comportamento.**
- **Por que sozinha:** o churn de versão é o risco mais silencioso. Isolá-lo permite provar que **só a subida
  de versão** não quebrou nada, antes de qualquer feature nova.
- **Verificação:** suíte completa (754 testes) + `tsc`/`eslint`/`next build` + subir o cérebro local e um
  disparo/conversa de fumaça. **Deploy e observar a produção** antes de seguir. Se algo regredir, é aqui que
  aparece — e reverte-se limpo.
- **Não muda:** nada que o usuário vê.

### P1 — `executar_agente`: `create_react_agent` → `create_agent`, SEM checkpointer/interrupt — ✅ NO AR (commit `a82b5fd`, 2026-08-06)
> Troca do construtor (o `create_react_agent` está deprecado). `system_prompt` aceita `SystemMessage` COMO
> ESTÁ → o `cache_control` (cache Anthropic da Frente B) sobrevive. Verificação: suíte **761/761**; fumaça ao
> vivo (turno Haiku real: resposta + `seguir_para` + uso); **cache provado no Sonnet via `create_agent`
> (cache_read=4324)**; confirmado que nem P0 nem P1 quebraram o cache (idêntico antes/depois). Nota menor: o
> `cache_write` de CRIAÇÃO aparece 0 no reporte do langchain (idêntico nos 2 construtores; erra p/ subestimar
> custo) — item à parte. `test_declaracao_ramo` passou a interceptar `create_agent`.
- **O que muda:** trocar a peça **deprecada** pela nova (`langchain.agents.create_agent`), mantendo tudo o
  mais idêntico (uma mensagem de entrada, mesmas ferramentas, mesmo prompt + cache Anthropic, mesma coleta de
  `uso`). Adaptação coberta pela ampliação nº 3 do descongelamento (`agente.py`).
- **Risco:** diferenças sutis de comportamento entre os dois construtores (formato de mensagens, `usage_metadata`,
  ordem de tool-calls).
- **Verificação:** `test_agente*`, `test_cadeia*`, `test_mensageria*`, `test_gate*` verdes sem mudança de
  expectativa de comportamento; conferir saída e `uso` equivalentes num caso real. Deploy + fumaça.
- **Não muda:** ainda **não há memória**; portão como está; nada que o usuário vê.

### P2 — Persistência + MEMÓRIA no chat (`modo=conversa`); o portão fica como está ⭐ (a CURA do "renasce")
> **É aqui que o "renasce" morre no chat.**
>
> **🟡 P2a IMPLEMENTADA (2026-08-08) — verificada em isolamento; aguarda deploy.** Novo módulo
> `orquestracao/memoria_conversa.py` (PostgresSaver + pool, à prova de falha → sem checkpointer a conversa
> cai no modo legado); `executar_agente` ganhou `checkpointer`/`thread_id`/`preambulo_sistema` opcionais +
> medição pelo **delta** (sem memória, byte-idêntico à P1); `mensageria/servico._rodar_turno` usa a memória
> SÓ no chat (não no portão) com **semeadura** do histórico no 1º turno (cobre conversas em andamento no
> deploy); `main.ciclo_de_vida` faz o `setup()` no boot. Verificação: suíte **765 verde** (1 flaky
> pré-existente à parte) + `test_memoria_conversa` (delta/preâmbulo) + `test_mensageria` (semeadura/fala-nova)
> + **integração ao vivo** (executar_agente real + PostgresSaver real + Sonnet: lembrou o fato entre turnos,
> delta certo, tabelas dropadas). Prod usa o pooler Supabase modo-sessão (5432 → DDL/prepared OK);
> `prepare_threshold=0` pooler-safe. **Falta:** deploy + teste ao vivo. P2b (janela) e P2c já embutido (delta).
>
> Sub-divisão original:
- **P2a — Checkpointer + `thread_id`:** ligar `PostgresSaver` (`.setup()` cria as tabelas de checkpoint —
  migração aditiva); `thread_id` = a conversa (`conversa.id`). A entrada do turno passa a ser **só a mensagem
  NOVA** — `_montar_entrada` deixa de reconstruir o histórico do texto (o checkpoint é a memória de trabalho).
  `MensagemConversa` **permanece** como projeção humana (a thread que o operador lê); `PassoExecucao`
  **permanece** como a timeline inspecionável (rastro).
- **P2b — Janela/compactação:** o thread do checkpoint não pode crescer sem fim → um `middleware` de
  trim/resumo (a decidir na fatia: `SummarizationMiddleware`/context-editing nativo × janela caseira) alimenta
  o modelo com janela + resumo. **É o encontro com a Frente B** (`UNIFICACAO-ESTADO.md §4`): persistir tudo
  (armazém) × enviar pouco (janela). Reusar o padrão do resumo rolante da criadora.
- **P2c — Contabilização pelo DELTA:** o `invoke` devolve o estado acumulado (medido no spike → soma
  superfatura). A medição de `uso` passa a ser o **delta** do turno. `medir_conversa` (Fatia 2) reconciliada.
- **Verificação:** a re-busca **some** (o agente lembra o resultado de ferramenta do turno anterior — o caso
  Reembolsos/Bubble deixa de re-consultar); teto/limite ainda corretos; custo medido certo; **teste ao vivo**.
- **Não muda:** o portão continua sendo o passo `espera_humano` da borda (Fatias 4.1/4.2) — **sem** `interrupt()`
  nativo ainda. **Ponto de parada seguro.**

### P3 — Portão NATIVO (`interrupt()` + HITL seletivo) — a peça mais delicada, por ÚLTIMO ⚠️
- **O que muda:** substituir a maquinaria de portão da borda por `interrupt()` via
  `HumanInTheLoopMiddleware(interrupt_on=<derivado de acao_irreversivel>)`, gateando **só** os instrumentos
  irreversíveis. A retomada (tela **e** canal) vira `Command(resume=...)` no mesmo `thread_id` — os dois
  caminhos partidos **colapsam** num só (o objetivo original da Fatia 4). Some a instrução escondida
  `_instrucao_de_fluxo` e a re-derivação do `entrada_rerun`.
- **Proteção obrigatória (do achado (c) do spike):** garantir que **nada com efeito colateral não-idempotente
  rode antes do `interrupt()` no mesmo nó** — senão re-executa ao retomar. O gate seletivo interrompe **antes**
  do efeito irreversível; ações de leitura idempotentes podem re-rodar sem dano. Testar explicitamente:
  aprovar → publica **1×**; recusar → **não** publica; re-aprovar/reenvio **não duplica**.
- **Risco:** máximo (é o portão, onde moram os bugs históricos, sobre clientes ao vivo).
- **Verificação:** `test_gate_conversa`, `test_aprovacao_por_canal`, `test_portao_*`, `test_retoma*`
  reescritos/verdes; **teste ao vivo** exaustivo do portão pela tela e pelo canal; rede `pre-fatia-4`/dump.
- **Não muda:** a garantia de nunca re-disparar irreversível (é o que estamos protegendo).

### P4 — Convergência / limpeza
- A retomada partida (tela × canal) some de vez; `_montar_entrada`/`entrada_rerun`/`_instrucao_de_fluxo`
  saem; a fonte-da-verdade do histórico fica consolidada. Encosta na **Fatia 5** (conversa dorme/acorda como
  passo `espera_humano`, sweepers convergem).

---

## Questões de design em aberto (a resolver DENTRO da fatia, com plano próprio — não agora)
1. **Três armazéns × papéis distintos (P2/P4):** checkpoint (memória de trabalho do agente) × `PassoExecucao`
   (timeline inspecionável) × `MensagemConversa` (thread humana). O benchmark dizia "o checkpoint É o rastro",
   mas já construímos a timeline nas Fatias 1–4.2. **Decidir** se a timeline passa a ser projeção do checkpoint
   ou se os dois coexistem com papéis separados. Não colapsar às cegas.
2. **Mecanismo de janela/compactação (P2b):** middleware nativo × janela caseira reusando o resumo rolante da
   Frente B. Medir tokens antes/depois.
3. **`thread_id` para o modo FLUXO (P3):** a orquestração clássica (`disparo`/`cadeia`) também passa a ter
   `thread_id`? Ou só a conversa/portão? Definir o alcance sem inflar o escopo.
4. **Migração de conversas vivas:** conversas em curso no deploy da P2 não têm checkpoint — tratar como
   "primeiro turno frio" (o resumo rolante cobre), sem quebrar nada.

---

## Ordem e portões de aprovação
`P0 → P1 → P2(a,b,c) → [parada segura possível] → P3 → P4`. Cada uma: **plano + verificação apresentados e
aprovados antes do código**; deploy e observação antes da seguinte. ✅ P0 e P1 NO AR; **a P2 é o próximo
passo** (aguarda plano+aval; e um teste real da P1 em produção antes, se o maestro quiser).
