# Fatia 4.3 — Decisão de arquitetura: memória entre turnos (a CURA do "renasce")

> **Status:** 🟡 **ESTUDO/DECISÃO — aguardando o martelo do maestro. NENHUM código escrito.**
> Este documento é o insumo obrigatório da **Fatia 4.3** (`REMODELAGEM-MOTOR.md §5`), a última e mais
> delicada da Frente A. Conforme a disciplina do projeto (`CLAUDE.md §9/§10`), a doc oficial do LangGraph
> **da nossa versão** foi lida e os fatos foram verificados **no ambiente real** antes de recomendar. A
> decisão de forma (nativo × caseiro × híbrido) é do maestro; só depois dela se escreve a primeira linha.
>
> **Âncora:** parte do [Programa de Unificação de Estado](UNIFICACAO-ESTADO.md) (Frente A). Fecha a
> pergunta que a Fatia 4.2 deixou aberta de propósito.

---

## 1. O que a 4.3 tem de resolver (o "renasce", com o código na mão)

Hoje o agente **não tem memória entre turnos**. Cada turno é um agente NOVO que remonta o contexto **a
partir do texto** e **descarta os resultados das ferramentas** do turno anterior. Onde isso nasce, exato:

- `orquestracao/agente.py::executar_agente` monta um `create_react_agent` **novo a cada chamada**, invoca
  com **uma** mensagem — `app.invoke({"messages": [{"role": "user", "content": entrada}]})` — e **joga o
  grafo fora** ao retornar. Nenhum `checkpointer`, nenhum `thread_id`.
- A `entrada` é **reconstruída do texto**: no chat, `mensageria/servico.py::_montar_entrada` lê as últimas
  ~20 `MensagemConversa` como "Rótulo: conteúdo"; no portão, `retoma._retomar_conversando_tela` /
  `servico._turno_de_portao` montam `entrada_rerun` = o que foi apresentado + a resposta do humano.
- Os resultados de ferramenta são **capturados para rastro** (`mensagens_enviadas`, `erros_instrumentos`)
  e gravados no passo — mas **não voltam** para o agente no próximo turno. Ele re-deriva: **re-busca a
  mesma API, re-lê a mesma tabela** (medido ao vivo: Reembolsos re-buscou a mesma tabela 3× numa conversa).

**Consequência dupla:**
1. **Correção** — o portão "renasce" entre apresentar e retomar; só texto atravessa. Toda a maquinaria de
   "apresentado vs. narrado", instrução escondida e retomada partida (tela × canal) existe para remendar
   isso (`REMODELAGEM-MOTOR.md §2`).
2. **Custo** — re-envio e re-derivação. **Mas atenção (dado do Marco 0):** o runtime de conversa é **< 3%**
   do custo do app; **~70% é a IA criadora** (já tratada na Frente B). Então **o valor da 4.3 é
   ESTRUTURAL (matar o "renasce", unificar o portão), não economia.** Isso reenquadra a decisão: não
   estamos otimizando dinheiro aqui — estamos curando a doença que gerou o segundo motor.

---

## 2. Fatos verificados no ambiente real (2026-08-06)

| Peça | Estado | Consequência |
|---|---|---|
| `langgraph` | **1.2.2** | `create_react_agent` aceita `checkpointer`, `store`, `interrupt_before/after`. |
| `langgraph-checkpoint` | 4.1.1 | Savers **base/memory/serde** presentes. |
| `langgraph.checkpoint.postgres.PostgresSaver` | **AUSENTE** | Nativo durável exige a dependência **`langgraph-checkpoint-postgres`** + tabelas próprias de checkpoint. |
| `langgraph.types.interrupt` / `Command` | Presentes | HITL nativo cru (`interrupt()` dentro de ferramenta) é possível. |
| `langchain` (meta) → `create_agent`, `middleware.HumanInTheLoopMiddleware` | **AUSENTE** | O HITL nativo **seletivo** (aprovar só instrumentos irreversíveis via `interrupt_on`) exige adicionar o pacote **`langchain`** inteiro. |
| `psycopg` | 3.3.4 | `PostgresSaver` (psycopg3) encaixaria no banco que já rodamos. |

> **Leitura:** o caminho nativo "textbook" que o benchmark romantiza ("só ligar o checkpointer") custa, na
> prática, **duas dependências novas** (`langgraph-checkpoint-postgres` **e**, para HITL seletivo seguro,
> `langchain`) e **um segundo armazém de estado** (as tabelas de checkpoint, ao lado de
> `MensagemConversa`/`PassoExecucao`).

---

## 3. O que a doc oficial diz (fontes lidas)

- **Persistência:** o checkpointer grava o *StateSnapshot* por `thread_id`; passa-se
  `config={"configurable": {"thread_id": ...}}`. `PostgresSaver.from_conn_string(...)` + **`.setup()`**
  cria as tabelas/índices. Há variante `AsyncPostgresSaver`.
  (<https://docs.langchain.com/oss/python/langgraph/persistence>)
- **Interrupts (HITL):** `from langgraph.types import interrupt, Command`. **"Um checkpointer é
  obrigatório."** `interrupt()` salva o estado e pausa; retoma com `Command(resume=valor)` no **mesmo
  `thread_id`**. **⚠️ Caveat oficial, textual:** *"como os interrupts funcionam re-executando os nós de
  onde foram chamados, efeitos colaterais antes do `interrupt()` devem (idealmente) ser idempotentes"* e
  *"o nó inteiro reinicia do começo ao retomar"*.
  (<https://docs.langchain.com/oss/python/langgraph/interrupts>)
- **HITL no agente prebuilt:** a forma 1.x é um **`HumanInTheLoopMiddleware`** (em
  `langchain.agents.middleware`) com um mapa **`interrupt_on`**: `False` para ferramenta segura
  (auto-aprova), `True`/config para ferramenta que exige aprovação — *conceitualmente igual à nossa parede
  de ativação*. **Mas esse pacote não está instalado.**
  (<https://docs.langchain.com/oss/python/langchain/human-in-the-loop>)

---

## 4. A colisão crítica (por que "só ligar o `interrupt()`" não é grátis para NÓS)

O `interrupt()` nativo **re-roda o nó ao retomar** e pede **idempotência** dos efeitos anteriores. O nosso
agente chama **instrumentos IRREVERSÍVEIS** (publicar reel, enviar mensagem, gravar no Bubble). A garantia
de **nunca re-disparar uma ação irreversível** é o coração do HITL do produto (`PRODUTO §14`) e está na
lista **congelada** (`REMODELAGEM-MOTOR.md §7`). Adotar `interrupt()` cru sem o middleware seletivo obriga
a **re-arquitetar o portão** para que nenhum efeito irreversível preceda o ponto de aprovação no mesmo nó —
uma reescrita da peça **mais delicada e mais remendada de bugs**, com clientes ao vivo. É risco real, não
teórico. O middleware `interrupt_on` resolveria isso elegantemente — mas traz o pacote `langchain` e
**substitui** a mecânica de portão que hoje funciona e está endurecida contra bugs históricos.

**Segundo ponto de fricção (contabilização):** com checkpointer + `thread_id`, `app.invoke` retorna o
estado **acumulado** (todas as `AIMessage` de todos os turnos). O nosso somatório de `uso`
(`agente.py`, laço sobre `AIMessage`) passaria a **recontar** os turnos anteriores → superfaturamento, a
menos que se meça só o **delta** desde o último checkpoint. Sanável, mas é trabalho e um lugar fácil de
errar.

**Terceiro ponto (fonte da verdade):** hoje a história da conversa vive em `MensagemConversa` (e, desde a
Fatia 1, na timeline-sombra `PassoExecucao`). O estado nativo passaria a viver nas **tabelas de checkpoint
do LangGraph** — um terceiro lugar de verdade, exatamente a doença que o programa quer curar ("histórico de
tudo"). Teria de haver migração faseada e uma decisão de quem é a autoridade.

---

## 5. As opções (honestas, com o preço de cada uma)

### Opção A — NATIVO (checkpointer `PostgresSaver` + `interrupt()`/middleware)
O que o benchmark cita como padrão de mercado. `executar_agente` recebe `checkpointer` + `thread_id`; o
portão vira `interrupt()`; o estado (mensagens + tool results) persiste sozinho.
- **A favor:** é o padrão consolidado; entrega estado entre turnos, portão nativo e "o checkpoint É o
  rastro" de uma vez; menos código de orquestração nosso a longo prazo.
- **Contra:** **duas dependências novas** + **segundo armazém de estado**; **re-arquitetar o portão**
  (peça congelada, mais frágil) por causa do re-run/idempotência × instrumentos irreversíveis; toca o laço
  `create_react_agent` (congelado); conserto do double-count de `uso`; migração de fonte-da-verdade. **É o
  maior rewrite da Frente A, sobre clientes ao vivo, para um ganho que NÃO é de custo** (runtime < 3%).

### Opção B — CASEIRO INCREMENTAL (persistir o fio na nossa timeline, alimentar de volta) — **recomendada**
Não trocamos de motor: **estendemos** o que as Fatias 1–4.2 já construíram. Guardamos o **fio de mensagens
do agente COM os resultados de ferramenta** (o "iceberg durável") atrelado à execução/conversa, e no turno
seguinte **alimentamos o agente com esse fio** (janela + resumo) em vez de reconstruir do texto. O portão
continua sendo o nosso passo `espera_humano` (Fatia 4.1/4.2) — **sem** `interrupt()` re-rodando nó.
- **A favor:** **mata o "renasce"** (o agente vê seus próprios tool results → fim da re-busca); **zero
  dependência nova**; **zero segundo armazém** (reusa `PassoExecucao`/uma coluna de fio); **não toca** o
  laço `create_react_agent` nem a semântica do portão (congelados intactos); **incremental e testável**,
  no espírito estrangulador; **concilia naturalmente com a Frente B** (guardar o completo, enviar janela+
  resumo — o mesmo desenho da Parte C/iceberg da criadora).
- **Contra:** "reimplementamos" um pedaço do que o LangGraph ofereceria. Na prática é **persistir mensagens
  e reinjetá-las** — trivial —, não reconstruir a máquina de checkpoint; mas é código nosso a manter.

### Opção C — HÍBRIDO (checkpointer nativo só para o ESTADO; portão fica como está)
Ligar o `PostgresSaver` + `thread_id` **só para dar memória** (fim da re-busca), mantendo o portão como o
nosso passo `espera_humano` da borda (sem `interrupt()`).
- **A favor:** ganha a memória "de graça" do LangGraph sem tocar a peça delicada do portão.
- **Contra:** ainda traz `langgraph-checkpoint-postgres` + o segundo armazém + o double-count de `uso`; e
  cria a esquisitice de **dois mecanismos de pausa** (checkpoint nativo para memória, passo nosso para
  HITL) — meio-termo que carrega parte dos custos de A sem a limpeza conceitual de "um mecanismo só".

---

## 6. A tensão com a economia de tokens (Frente B) — e como concilia

`UNIFICACAO-ESTADO.md §4` nomeia o nó: **persistência** (Frente A: trazer o fio inteiro de volta) ×
**compactação** (Frente B: enviar só resumo + janela). Parecem opostas; só conciliam **desenhadas juntas**:
guardar o fio completo como **iceberg durável** (o armazém) e **alimentar o modelo a cada turno só com
janela + resumo** (o que entra na janela de contexto). Persistir ≠ reenviar.

A **Opção B casa com isso por construção**: o armazém é a nossa timeline (guarda tudo, inclusive tool
results), e o que se envia ao modelo é a janela/resumo — exatamente o padrão que a Frente B já entregou
para a criadora (Parte A resumo rolante + Parte C iceberg/`buscar_no_historico`). A Opção A joga o armazém
para as tabelas de checkpoint e, para não reenviar tudo, ainda precisaria de uma camada de compactação por
cima do estado nativo — o que **anula parte do "de graça"** que a torna atraente.

---

## 7. Escopo real da 4.3 e o que permanece CONGELADO

Qualquer que seja a opção, **permanecem congelados** (`REMODELAGEM-MOTOR.md §7`): a semântica de
`seguir_para` (bifurcação A/B), a **garantia HITL de não re-disparar ação irreversível** (`PRODUTO §14`), o
contrato de instrumentos, a fila `FOR UPDATE SKIP LOCKED`, o heartbeat/sweeper/recuperação de órfãos
(`CLAUDE.md §12-A`). A suspensão dirigida nº 2 (autorizada 2026-08-04) cobre `cadeia.py`, `agente.py` e o
modelo `PassoExecucao` — **absorver a borda para dentro do motor**, não reescrever o motor.

---

## 8. Recomendação e o que peço ao maestro

**Recomendo a Opção B (caseiro incremental).** Razão honesta, sem agradar: o argumento de venda do nativo
("é grátis, só ligar") **não é grátis para o Batuta** — ele briga com a nossa garantia HITL congelada
(instrumentos irreversíveis × re-run do `interrupt()`), adiciona duas dependências e um segundo armazém de
estado, e o **ganho de custo que justificaria o risco não existe** (o runtime é < 3% do gasto; quem custava
já foi tratado na Frente B). A Opção B mata o "renasce" — que é o objetivo real — reusando a fundação que
as Fatias 1–4.2 já assentaram, sem tocar as peças frágeis e congeladas, e conciliando de fábrica com a
economia de tokens.

Quando (e se) o dia pedir o portão nativo `interrupt()`, ele volta à mesa como um passo próprio, com o
middleware seletivo e o pacote `langchain` — decisão separada, não embutida agora.

**Decisão que peço:** aprovar **B**, ou preferir **A**/**C**. Aprovada a forma, a 4.3 é sub-fatiada
(persistir o fio → alimentar de volta com janela/resumo → medir o delta de uso) e cada sub-fatia vem com
plano e verificação antes do código, como sempre.
