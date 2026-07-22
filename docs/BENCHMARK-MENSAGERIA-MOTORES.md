# Benchmark — como os OUTROS motores fazem "mensageria + IA" (estado/memória entre turnos)

> **Status:** 📋 Estudo/benchmark (pedido do maestro, 2026-07-22). Informa a **FASE FUTURA — Unificação do Runtime** ([`REMODELAGEM-MOTOR.md`](REMODELAGEM-MOTOR.md)). Não é plano de execução.

## O problema do Batuta (o que motivou)
No Batuta, cada turno da conversa é um **agente NOVO** que reconstrói o contexto **do texto** (`mensageria/servico.py::_montar_entrada`; na criadora, `criacao/loop.py::_historico_para_mensagens`) e **joga fora os resultados das ferramentas** do turno anterior. Efeito: **re-busca** (o agente re-consulta a API externa a cada turno), portão que "renasce" (só texto atravessa), e custo alto. Provado ao vivo no time de Reembolsos (Telegram → Bubble): um agente re-buscou a mesma tabela 3× numa conversa, turno de lançamento a 90k tokens de entrada.

## O padrão UNIVERSAL que todo mundo usa
**Estado de conversa PERSISTENTE** (thread/sessão + checkpoint), incluindo os **resultados das ferramentas**. O agente **retoma do último checkpoint** — nunca re-deriva do zero. Aprovação humana = **pausar e retomar o MESMO estado**, não renascer.

## Benchmark

| Motor | Estado entre turnos | Aprovação humana (HITL) | Memória de longo prazo |
|---|---|---|---|
| **LangGraph** (o Batuta **JÁ usa**) | **Checkpointer** (`PostgresSaver` em prod) grava o *StateSnapshot* completo — mensagens **+ chamadas/resultados de ferramenta** — a cada passo, por `thread_id`. Retoma reconstruindo do último checkpoint. | `interrupt()` **pausa**, salva o estado pela camada de persistência, espera, e **retoma o MESMO estado** via `Command`. É o portão nativo, sem renascer. | store separado / LangMem |
| **OpenAI Assistants (Threads)** | **Thread** no servidor guarda TODAS as mensagens **+ interações de ferramenta**; você passa o `thread_id` e o estado é mantido automaticamente ("from stateless to smart"). | via aprovação de ferramenta / lógica do app | — |
| **OpenClaw** (o exemplo do maestro) | **Sessão** por (usuário × canal × agente), ~100 msgs de contexto, **sobrevive a restart** (SQLite). | — | **MEMORY.md** (arquivo markdown = fonte da verdade) + SQLite-vec (embeddings); **compactação por "turno silencioso"** que manda o modelo escrever memória durável antes de comprimir o contexto. |
| **Rasa** | *Tracker store* — estado de diálogo explícito (slots + histórico), persistido. | — | — |
| **Chat Completions cru** (OpenAI/Anthropic) | **STATELESS** — você reenvia o histórico manualmente. **É o que o Batuta faz hoje** — e ainda jogando fora os tool results. | — | — |

## O achado que importa (a ironia)
1. **O Batuta usa `create_react_agent` (LangGraph) SEM checkpointer** → reconstrói do texto a cada turno → perde os tool results → **re-busca**. Reimplementou (mal, na borda) o que o LangGraph dá de graça.
2. **A correção não é exótica: é LIGAR a persistência do LangGraph que já está na estante.** `create_react_agent(model, tools, checkpointer=PostgresSaver(...))` + passar `thread_id` = a conversa. O Batuta **já roda Postgres** → `PostgresSaver` é encaixe direto. Isso entrega, de uma vez: **estado entre turnos** (fim da re-busca), **portão nativo** (`interrupt()` pausa/retoma o mesmo estado, sem renascer) e **rastro inspecionável** (o checkpoint É o rastro).
3. **OpenClaw**, sem LangGraph, chegou às MESMAS ideias que a gente já tinha esboçado: **sessão persistente** (= dar memória à conversa, a Fatia da remodelagem) + **MEMORY.md** (= o `projeto.md` do plano de economia de tokens da IA criadora) + **compactação**. Ou seja, os dois planos futuros do Batuta batem com o estado da arte.

## Conclusão
O Batuta **não precisa inventar nada**: o padrão (thread persistente + checkpoint + interrupt) é consolidado no mercado, e o Batuta **já tem a peça** (LangGraph). A remodelagem do runtime = **adotar a persistência que o LangGraph oferece** em vez de reimplementá-la à mão na borda. Isso valida — e simplifica — a remodelagem: "dar memória à conversa" deixa de ser um projeto do zero e vira "ligar o checkpointer + `thread_id` + `interrupt`".

## Ressalvas honestas
- Adotar o checkpointer significa o estado da conversa passar a viver nas **tabelas de checkpoint do LangGraph** (Postgres) — nova camada ao lado das tabelas do Batuta; migração faseada.
- Toca `orquestracao/agente.py` (`executar_agente` passaria a receber `checkpointer` + `thread_id`) → é o núcleo congelado; entra na suspensão dirigida já prevista na remodelagem.
- `interrupt()` nativo substituiria a maquinaria de portão da borda — grande simplificação, mas é a peça mais delicada (mexer por último, com testes).

## Fontes
- LangGraph — persistence & interrupts: <https://docs.langchain.com/oss/python/langgraph/interrupts> (+ `PostgresSaver` recomendado em produção).
- OpenAI — Conversation state / Assistants Threads (persistem mensagens + tool state por thread).
- OpenClaw — arquitetura de memória (sessões + `MEMORY.md` + sqlite-vec + compactação por turno silencioso).
