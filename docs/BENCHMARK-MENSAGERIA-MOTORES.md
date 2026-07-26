# Benchmark — como os OUTROS motores fazem "mensageria + IA" (estado/memória entre turnos)

> **Status:** 📋 Estudo/benchmark (pedido do maestro, 2026-07-22). É a **evidência de mercado comum** do **Programa de Unificação de Estado** (âncora: [`UNIFICACAO-ESTADO.md`](UNIFICACAO-ESTADO.md)) — informa tanto a **Frente A** ([`REMODELAGEM-MOTOR.md`](REMODELAGEM-MOTOR.md)) quanto a **Frente B** ([`ECONOMIA-TOKENS-IA-CRIADORA.md`](ECONOMIA-TOKENS-IA-CRIADORA.md)). Não é plano de execução.

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

## Economia por PROVEDOR — os recursos de API (o eixo que o estudo original pulou)

> **[Adicionado 2026-07-26]** O benchmark original só olhou a persistência de estado (arquitetura) e, de recursos de API, só a Anthropic. Mas o Batuta deixa **cada agente** e a **IA criadora** escolherem o modelo/provedor — então a economia real também depende de **qual provedor está em uso**. Aqui os fatos verificados dos três.

### Todos dão ~90% de desconto no token de ENTRADA em cache — o que muda é COMO se liga

| Provedor | Leitura em cache | Como se liga | Pegadinhas |
|---|---|---|---|
| **Anthropic** | ~**10%** do preço de entrada (≈90% off) | **manual** (marcar `cache_control` nos breakpoints) **ou** automático no topo do request | **escrita custa 1,25×** (5 min) / 2× (1h); janela padrão **5 min** (1h opcional); prefixo mínimo 1024–4096 tokens; trocar de modelo invalida o cache |
| **OpenAI** | ~**10–25%** do preço | **automático** no servidor (prefixo estável >1024 tokens), zero config | retenção **24h** nos modelos novos; sem custo de escrita |
| **Gemini** | ~**10%** do preço | **implícito** (automático, ligado por padrão nos 2.5+) **ou** explícito | explícito tem custo de armazenagem; implícito é grátis |

**Cache NUNCA desconta token de SAÍDA** (nenhum provedor). **Batch API = 50% off** nos três, mas **assíncrono** (lote, não conversa interativa).

### O achado que importa para o Batuta (a assimetria)
Hoje o Batuta roda na Anthropic **sem** marcar `cache_control` (o cache é a Parte D da economia — Frente B — ainda **não fiada**). Logo, **na Anthropic o Batuta paga o preço cheio todo turno**: reenvia a conversa inteira sem desconto. O **mesmo** agente em **OpenAI ou Gemini pegaria o desconto de ~90% do contexto repetido automaticamente**, de graça. **A Anthropic é hoje a única das três onde estamos deixando o cache na mesa — e é onde o Batuta mais roda.**

### O lever de preço-base (independente de cache) — spread de 5×
| Modelo | Entrada / Saída (por 1M de tokens) |
|---|---|
| **Haiku 4.5** | $1 / $5 |
| **Sonnet 5** | $3 / $15 (intro $2/$10 até 2026-08-31) |
| **Opus 4.8** | $5 / $25 |

Um agente simples em **Opus custa 5× mais** que em Haiku pelo mesmo trabalho. O Batuta **já deixa** cada agente escolher o modelo (`Agente.modelo_ia`) e a criadora o seu (`Organizacao.modelo_criadora`) — então **dimensionar cada agente ao que ele precisa** é possivelmente a economia mais barata de todas, **sem tocar código de motor**.

### Honestidade — o que NÃO se resolve trocando de provedor/modelo
- **Qualidade:** modelo mais barato = potencialmente pior. A **criadora** quer um modelo forte (constrói times). Não é "tudo no Haiku" — é **right-size por agente**.
- **Janela do cache:** cache só ajuda dentro do TTL (5 min Anthropic / 24h OpenAI / implícito Gemini). **Abrir um time frio** depois de horas NÃO pega cache — quem resolve isso é o **resumo rolante** (Frente B, Parte A). Cache e compactação são **complementares**.
- **A fundação continua provedor-agnóstica:** persistir estado e parar de re-buscar (Frente A) economiza com **qualquer** modelo. O cache é um multiplicador por cima, **não** um substituto do Programa.

## Fontes
- LangGraph — persistence & interrupts: <https://docs.langchain.com/oss/python/langgraph/interrupts> (+ `PostgresSaver` recomendado em produção).
- OpenAI — Conversation state / Assistants Threads (persistem mensagens + tool state por thread); prompt caching automático (retenção 24h nos modelos novos).
- Gemini — context caching implícito (padrão, ~90% off) × explícito (com armazenagem): <https://ai.google.dev/gemini-api/docs/caching>.
- Anthropic — prompt caching (leitura ~0,1×, escrita 1,25×/2×; TTL 5 min/1h) + preços (Opus 4.8 $5/$25, Sonnet 5 $3/$15, Haiku 4.5 $1/$5) pela referência oficial do SDK (skill `claude-api`).
- Comparativos de cache 2026 (Anthropic × OpenAI × Azure/Gemini): <https://technspire.com/en/blog/prompt-caching-2026-real-cost-wins>.
- OpenClaw — arquitetura de memória (sessões + `MEMORY.md` + sqlite-vec + compactação por turno silencioso).
