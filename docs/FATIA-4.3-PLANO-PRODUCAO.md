# Fatia 4.3 — Plano de produção (Opção A, nativo): sub-fatias estranguladoras

> **Status:** 🟡 **PLANO — aguardando aval do maestro para iniciar a sub-fatia P0. NENHUM código escrito.**
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

### P0 — Subir o núcleo (dependências) em ISOLAMENTO ⭐ (primeiro, mais barato)
- **O que muda:** `uv add langgraph-checkpoint-postgres langchain` (deixa `langchain-core`/`langgraph`
  subirem para as versões compatíveis — medido no spike: `langchain-core 1.4→1.5`, `langgraph 1.2.2→1.2.10`).
  **Zero código de comportamento.**
- **Por que sozinha:** o churn de versão é o risco mais silencioso. Isolá-lo permite provar que **só a subida
  de versão** não quebrou nada, antes de qualquer feature nova.
- **Verificação:** suíte completa (754 testes) + `tsc`/`eslint`/`next build` + subir o cérebro local e um
  disparo/conversa de fumaça. **Deploy e observar a produção** antes de seguir. Se algo regredir, é aqui que
  aparece — e reverte-se limpo.
- **Não muda:** nada que o usuário vê.

### P1 — `executar_agente`: `create_react_agent` → `create_agent`, SEM checkpointer/interrupt
- **O que muda:** trocar a peça **deprecada** pela nova (`langchain.agents.create_agent`), mantendo tudo o
  mais idêntico (uma mensagem de entrada, mesmas ferramentas, mesmo prompt + cache Anthropic, mesma coleta de
  `uso`). Adaptação coberta pela ampliação nº 3 do descongelamento (`agente.py`).
- **Risco:** diferenças sutis de comportamento entre os dois construtores (formato de mensagens, `usage_metadata`,
  ordem de tool-calls).
- **Verificação:** `test_agente*`, `test_cadeia*`, `test_mensageria*`, `test_gate*` verdes sem mudança de
  expectativa de comportamento; conferir saída e `uso` equivalentes num caso real. Deploy + fumaça.
- **Não muda:** ainda **não há memória**; portão como está; nada que o usuário vê.

### P2 — Persistência + MEMÓRIA no chat (`modo=conversa`); o portão fica como está ⭐ (a CURA do "renasce")
> **É aqui que o "renasce" morre no chat.** Sub-dividida no seu próprio plano quando chegarmos:
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
aprovados antes do código**; deploy e observação antes da seguinte. A P0 é o próximo passo proposto.
