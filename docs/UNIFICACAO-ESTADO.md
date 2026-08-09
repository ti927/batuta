# Unificação de Estado — o programa que junta motor + IA criadora (âncora)

> **Status:** 📋 **PROGRAMA FUTURO — PRIORIDADE Nº 1.** Documentação consolidada e aprovada como
> registro; **execução de código NÃO iniciada** (não começar nenhuma fatia sem sinal explícito do
> maestro). Esta rodada foi **só documentação**: consolidar o que estava disperso e conciliar a base.
>
> **Este é o documento-âncora.** Ele reúne e coordena três estudos que antes viviam soltos:
> [`REMODELAGEM-MOTOR.md`](REMODELAGEM-MOTOR.md) (o runtime), [`ECONOMIA-TOKENS-IA-CRIADORA.md`](ECONOMIA-TOKENS-IA-CRIADORA.md)
> (a autoria) e [`BENCHMARK-MENSAGERIA-MOTORES.md`](BENCHMARK-MENSAGERIA-MOTORES.md) (a evidência de
> mercado). O `BUILD-PLAN.md` aponta para cá.

---

## 1. Por que este programa existe (a dor, sem rodeio)

**O Batuta não está performando bem, e o maestro quer isso resolvido.** Ao investigar, veio à tona
algo que ele **nunca soube** e que ninguém tinha dito com todas as letras: **o Batuta hoje tem dois
motores de execução** fazendo a mesma coisa de formas incompatíveis —

- **Motor 1 — Orquestração (disparo):** `orquestracao/disparo.py` → `cadeia.py` → `agente.py`. Cria
  `Execucao` + `PassoExecucao`, tem fila robusta, heartbeat, rastro rico e inspecionável.
- **Motor 2 — Conversa (mensageria):** `mensageria/servico.py::processar_turno` chama `executar_agente`
  **direto, por fora do Motor 1**. Não cria execução; o rastro fica só na thread da conversa.

Essa descoberta só apareceu porque uma regra de governança — **o "núcleo congelado / intocável"**
(`MIGRACAO.md §6.1`) — proibia mexer no motor. A regra foi **prudente e certa** no seu tempo (proteger
o core validado durante a Etapa 2), mas teve um efeito colateral pesado: **empurrou todo trabalho novo
para a borda.** Quando chegou a mensageria, em vez de a conversa virar *extensão* do motor, virou **um
segundo motor inteiro**. Nas palavras do maestro: *"escreveram que o motor era intocável, e agora temos
2; daqui a pouco teremos 3."* Consertar essa regra é parte deste programa (ver §6 e a nota de governança
no `MIGRACAO.md §6.1`).

---

## 2. A descoberta que une tudo: é UMA doença só

As duas dores que pareciam separadas — "o motor de conversa é caro e não deixa rastro" e "a IA criadora
gasta tokens demais" — são **a MESMA doença**, em dois lugares:

> **Todo turno começa do zero.** O agente é reconstruído a cada interação, remonta o contexto **a partir
> do texto** e **joga fora os resultados das ferramentas** do turno anterior. Ele não tem memória do que
> já fez; então **re-deriva** — re-busca a mesma API, re-lê a mesma tabela — e o portão de aprovação
> "renasce" entre apresentar e retomar (só texto atravessa).

Onde a doença mora, em código:
- **Runtime de conversa:** `mensageria/servico.py::_montar_entrada` (reconstrói do texto a cada mensagem).
- **Autoria (IA criadora):** `criacao/loop.py::_historico_para_mensagens` (reenvia a conversa **inteira**
  + o prompt cheio todo turno; num time antigo, ~75k tokens de histórico + 15–40k de prompt fixo, **por
  turno**).

Prova ao vivo (time de Reembolsos, Telegram → Bubble): um agente re-buscou a mesma tabela **3×** numa
conversa; um turno de lançamento chegou a **90k tokens** de entrada.

### A cura é uma família só
O [`BENCHMARK-MENSAGERIA-MOTORES.md`](BENCHMARK-MENSAGERIA-MOTORES.md) mostrou que **todo motor sério do
mercado** resolve isso do mesmo jeito: **estado de conversa PERSISTENTE entre turnos** (thread + checkpoint,
incluindo os resultados das ferramentas). O agente **retoma do último ponto** — nunca re-deriva do zero.
Aprovação humana = **pausar e retomar o MESMO estado**, não renascer.

E a ironia que fecha o argumento: **o Batuta já usa LangGraph**, que entrega isso "de graça" —
`create_react_agent(model, tools, checkpointer=PostgresSaver(...))` + um `thread_id` por conversa +
`interrupt()` para o portão. O Batuta roda `create_react_agent` **sem** checkpointer e **reimplementou à
mão, na borda,** o que a estante já tinha. A cura não é exótica; é **ligar a peça que já existe.**

---

## 3. As duas frentes do programa

O programa tem **duas frentes que compartilham a mesma fundação** (dar memória entre turnos):

| Frente | Onde | O que muda | Doc-fonte |
|---|---|---|---|
| **A — Runtime** | motor de conversa (`mensageria`) + orquestração | Uma `Execucao`/timeline única para todo fluxo (botão, hora, webhook, mensagem); portão vira passo `espera_humano`; conversa vira `modo=conversa` que dorme/acorda. Fim da re-busca e do rastro perdido. | [`REMODELAGEM-MOTOR.md`](REMODELAGEM-MOTOR.md) |
| **B — Autoria** | IA criadora (`criacao/`) | Parar de reenviar a conversa inteira: resumo rolante (`projeto.md` visível/editável) + janela de N turnos + iceberg (histórico completo + busca sob demanda) + cache de prompt + foto enxuta. | [`ECONOMIA-TOKENS-IA-CRIADORA.md`](ECONOMIA-TOKENS-IA-CRIADORA.md) |

**O vínculo (o que este documento estabelece e os dois docs-fonte agora reconhecem):** as duas frentes
atacam a **mesma doença-raiz** (turno sem memória) com a **mesma família de cura** (persistir estado
entre turnos em vez de reconstruir do texto). Fazer uma **ilumina** a outra. É por isso que elas deixam
de ser "duas fases futuras soltas" e passam a ser **um programa com prioridade nº 1**.

> **Correção de um registro anterior:** o `REMODELAGEM-MOTOR.md` dizia que a IA criadora "não unifica —
> é outro domínio". Isso está **reconciliado**: as duas de fato compartilham o problema-raiz e a família
> de cura. O que fica **em aberto** não é *se* elas se relacionam (relacionam), mas *como executá-las* —
> ver a decisão adiada, §5.

---

## 4. A tensão real (por que a decisão de forma foi ADIADA)

Aqui está o nó que o maestro corretamente recusou-se a decidir no escuro. As duas frentes puxam o
contexto do turno em **direções opostas**:

- **Frente A (persistência):** *não re-derivar* → o checkpointer guarda o **fio inteiro** (mensagens +
  resultados de ferramenta) e o traz de volta a cada turno.
- **Frente B (compactação):** *não reenviar tudo* → mandar ao modelo só um **resumo + janela curta**,
  deixando o resto num iceberg guardado.

Ingênuo, isso parece contradição: uma quer trazer tudo de volta, a outra quer mandar pouco. **Elas só se
conciliam se forem desenhadas juntas:** guardar o fio completo como **iceberg durável** (a persistência
da Frente A vira o *armazém*, não o *que se envia*) e **alimentar o modelo a cada turno só com janela +
resumo** (a compactação da Frente B decide o *que entra na janela de contexto*). Persistência ≠ reenvio.

Provar que essa combinação funciona — e medir o ganho real de tokens — **é um estudo, não um chute.** Por
isso ele é o **primeiro marco** do plano (§5) e a decisão de forma depende dele.

---

## 5. O plano de construção (estagiado; execução aguarda sinal)

> **Regra de ouro:** cada passo é pequeno, testável, deixa a produção verde e os testes passando. Nunca
> há troca simultânea dos dois mundos. Se o maestro parar em qualquer ponto, o sistema fica coerente.
> (É a migração **estranguladora** do `REMODELAGEM-MOTOR.md §5`.)

### Marco 0 — ESTUDO DE TOKENS + decisão de forma ⭐ (o primeiro, e o mais barato) — ✅ **EXECUTADO**
Medir, numa conversa longa real, o consumo **antes** e projetar o **depois** para as duas combinações;
provar que "iceberg durável + janela/resumo" (§4) concilia persistência e compactação. **Saída:** a
decisão adiada (§ abaixo) tomada com número na mão, e a sequência das fatias travada. Não escreve motor;
é planejamento com evidência.

> **✅ Estudo feito (2026-07-26) — [`ESTUDO-TOKENS-MARCO-0.md`](ESTUDO-TOKENS-MARCO-0.md).** Medição
> real (somente-leitura) no snapshot de produção. **Achados que reorientam a decisão:** (1) o custo é
> **~70% a IA criadora** (Frente B); a mensageria (Frente A) é **< 3%** — o runtime **não** é problema
> de custo, é de **rastro/HITL**. (2) A doença da Frente B está medida: o custo/turno da criadora sobe
> **6,3×** (19,7k → 300k+) por reenviar a conversa inteira. (3) Projeção: janela+resumo cortam
> **~40–51%** e o cache Anthropic (não ligado hoje) evita **+~4,3M tokens** — combinado, **50–70%** da
> maior categoria, **sem tocar o motor**. **Recomendação do estudo (§9 de lá):** dois trilhos
> coordenados, **Frente B primeiro** (dinheiro + não precisa descongelar). **A decisão de forma é do
> maestro** — segue adiada em §7 até ele bater o martelo.

**Três eixos de medição** (o 2º e o 3º foram adicionados em 2026-07-26 — detalhe e números em `docs/BENCHMARK-MENSAGERIA-MOTORES.md` § "Economia por PROVEDOR"):
1. **Arquitetura** (o Programa): consumo antes × depois de *persistir estado* (fim da re-busca, Frente A) + *compactar* (resumo/janela, Frente B). **Provedor-agnóstico** — é o ganho estrutural.
2. **Modelo por agente** (preço-base, **spread de 5×** Haiku↔Opus): cada agente e a criadora estão superdimensionados para o que fazem? **Já disponível hoje** (`Agente.modelo_ia` / `Organizacao.modelo_criadora`), sem tocar o motor — possivelmente a economia mais barata. Ressalva: modelo mais barato pode custar qualidade (a criadora quer um modelo forte) → **right-size por agente**, não "tudo no Haiku".
3. **Cache por provedor:** na Anthropic o Batuta hoje **não** liga `cache_control` → paga cheio; OpenAI/Gemini dão **auto-cache de ~90%** do contexto repetido de graça. Medir o ganho de ligar o cache na Anthropic (Frente B, Parte D) × o que já se ganharia noutro provedor.

**Nuance:** cache só vale dentro da janela (5 min / 24h / implícito); "abrir time frio" quem resolve é o resumo rolante (Parte A). Os Eixos 2 e 3 economizam **sem** o rewrite; o Eixo 1 é o ganho de fundo do Programa.

### Frente A — as fatias do runtime (do `REMODELAGEM-MOTOR.md §5`)
- **Fatia 1 — Unificar o RASTRO** (maior valor / menor risco; **NÃO toca o portão**) — ✅ **NO AR (1a+1b, 2026-07-26)**. Toda conversa nasce
  com uma `Execucao` sombra `modo=conversa`; o turno grava o passo (entrada/saída/instrumentos/
  **`erros_instrumentos` hoje descartados**/uso), nos mesmos trilhos da orquestração. Comportamento visível
  **inalterado** — só passa a existir rastro. **Resolve JÁ a dor de hoje:** dá para depurar o agente
  lançador do Bubble. Detalhes do que foi construído (estado próprio `'conversa'` fora da fila/recuperadores;
  escritor dedicado à prova de falha; portão de fora; 100% aditivo, 736 testes) em `REMODELAGEM-MOTOR.md §5`.
  **1a** (deploy `7dcdfc4`) fez o rastro EXISTIR; **1b** (deploy `4505a8d`, sem migração) o tornou VISÍVEL na
  tela de Execuções (filtro "Conversas" + a MESMA tela de detalhe). Falta só teste ao vivo.
- **Fatia 2 — Medição sobre a execução sombra** — ✅ **NO AR (2026-08-04, commit `4d2ab1e`).** O teto de custo/turnos da conversa passa a ser lido da TIMELINE (`servico.medir_conversa`), não dos contadores soltos (que viram cache). Conserto de fidelidade: o passo passou a guardar o uso CHEIO do turno (agente + transcrição + visão + instrumentos). Backend puro, sem migração, zero mudança de comportamento (equivalência provada em `test_medir_conversa.py`).
- **Fatia 3 (parte segura) — Declutter da config** — ✅ **NO AR (2026-08-04, commit `7efb6e7`).** Removidas as chaves MORTAS (`max_passos`, `modelo_roteador`, `acao_ao_estourar`); presets 4→2 honestos (Processo interno + Atendimento externo; caíram disparo/personalizado, sem uso em prod); constante espelhada unificada. Front data-driven (tela se atualiza sozinha). **ADIADO p/ Fatia 4:** re-dimensionar a cascata por dimensão + `max_passos`→cadeia (núcleo).
- **Fatia 4 ⚠️ — Portão como passo `espera_humano` unificado** — ▶️ **EM EXECUÇÃO (descongelamento nº 2 autorizado, `MIGRACAO.md §6.1`, 2026-08-04).** Sub-fatiada em três: **✅ 4.1 (vocabulário) NO AR** (`62e18d5`, migração aditiva `tip00passo001` — coluna `PassoExecucao.tipo`; portão carimbado `espera_humano`; nada lê ainda → zero mudança). **✅ 4.2 (unificação do rastro) NO AR** (`12fb70f` — o portão pelo CANAL passa a deixar passo `espera_humano` na timeline do fluxo, como a tela; achado honesto: merge do ciclo-de-vida = risco alto/pouco ganho, a 4.3 reescreve o re-run). **✅ 4.3 — A CURA: memória entre turnos NO AR e PROVADA AO VIVO (2026-08-09)** (o agente do portão retoma do estado salvo, não re-deriva) — **mata o "renasce".** Rede de segurança montada antes: tag `pre-fatia-4` + dump de PROD. **Decisão de forma:** o maestro escolheu o **NATIVO do LangGraph** (Opção A — `PostgresSaver`+`thread_id`+`interrupt`, ampliação de descongelamento nº 3, `MIGRACAO §6.1`) contra a recomendação técnica (caseiro), e o protótipo isolado provou memória + proteção do irreversível. Plano estrangulador `P0`→`P4` ([`FATIA-4.3-PLANO-PRODUCAO.md`](FATIA-4.3-PLANO-PRODUCAO.md)): **✅ P0/P1** (deps + `create_react_agent`→`create_agent`) · **✅ P2a/P2b** (memória durável + janela/resumo nativos) · **✅ P3 = portão nativo** (P3a HITL seletivo · P3b TRAVA na conversa · P3d governança = **parede de aprovação**, fim da confirmação em dobro · P3c-B portão de esteira com memória, tela+canal). Provado: conversa `ea7d7e26` + automação `21bcb42e`. Retrocompatível (sem checkpointer = idêntico ao legado). **Resta:** limpar o "Confirma?" manual dos agentes (o maestro faz) + P4 (opcional).
- **Fatia 5** — Conversa vira `modo=conversa` de primeira classe (dorme/acorda); sweepers convergem.
- **Fatia 6** (opcional) — Projeção única na UI (aba Conversa lê a timeline).

### Frente B — as partes da economia (do `ECONOMIA-TOKENS-IA-CRIADORA.md`)
- **A ✅ NO AR (2026-07-26)** — Resumo rolante + janela de turnos recentes (−62% do histórico provado; commit `3621138`).  **B ✅ NO AR (2026-07-27)** — Painel "Sobre este time" (resumo visível/editável, drawer à direita; edição humana vence a da IA; commit `4815f14`).
- **C ✅ NO AR (2026-07-26)** — Iceberg + `buscar_no_historico` (tool; commit `1a8712f`; fecha a ressalva do resumo com perda).  **D ✅ NO AR (2026-07-26)** — Cache de prompt Anthropic (~88%/turno provado; commit `b28d091`; ver [`ESTUDO-TOKENS-MARCO-0.md`](ESTUDO-TOKENS-MARCO-0.md)).
- **E ✅ NO AR (2026-07-27)** — Foto enxuta: o prompt da criadora leva só a estrutura do time (sem os markdowns dos agentes nem a cadeia); detalhe sob demanda via `ver_agente`/`ver_automacao` (commit `d3ce135`; a foto cheia segue para o front). **Frente B completa (A–E).**

**Onde as frentes se tocam:** a Fatia 1 (parar de descartar o rastro/tool results) e a Parte C (iceberg
que guarda tudo e busca sob demanda) são a **mesma ideia** aplicada aos dois lados — guardar o completo,
alimentar o enxuto. O Marco 0 decide se elas viram **uma fundação comum** (ex.: o checkpointer do
LangGraph servindo runtime e autoria) ou **dois trilhos coordenados**.

---

## 6. Governança — como o motor volta a poder evoluir

Este programa **corrige a regra que criou o problema.** O "núcleo intocável" (`MIGRACAO.md §6.1`) foi
substituído pelo princípio de **evolução dirigida do motor**: o motor é precioso e protegido, mas **pode e
deve evoluir** quando o produto exige — por um mecanismo **formal, aditivo e aprovado-antes**, nunca uma
reescrita cega. Há **precedente**: 2026-06-16 (grafos, tocou `cadeia.py` com aval) e 2026-07-20 (1 linha
aditiva). Ver a nota de governança datada no `MIGRACAO.md §6.1`.

**Permanece congelado (garantias que o rewrite NÃO remove):** a semântica de `seguir_para` (a bifurcação
A/B é o produto), a garantia HITL antes de ação irreversível (`PRODUTO §14`), o contrato de instrumentos,
a fila `FOR UPDATE SKIP LOCKED`, o laço `create_react_agent` do agente, e o heartbeat/sweeper/recuperação
de órfãos (lei `CLAUDE.md §12-A`). **Suspender o congelamento não é licença para reescrever o motor — é
licença para absorver a borda de conversa para dentro dele, faseado e testado.** A suspensão é cirúrgica
(3 alvos: `cadeia.py`, `agente.py`, modelo `PassoExecucao`), só **antes da Fatia 4**, por aditivo curto ao
`MIGRACAO.md` aprovado pelo maestro (formato do precedente de 2026-06-16). Detalhe em `REMODELAGEM-MOTOR.md §7`.

---

## 7. DECISÃO DE FORMA — ✅ **TOMADA pelo maestro (2026-07-26)**

> **DECISÃO:** **dois trilhos coordenados, Frente B (IA criadora) primeiro** — conforme a recomendação do
> Marco 0 (§9 do estudo). O maestro autorizou **iniciar a execução**. **Já NO AR (2026-07-26): Frente B
> Parte D — cache (`b28d091`, ~88%/turno), Parte A — resumo rolante + janela (`3621138`, −62% do histórico
> na conversa longa real) — e Parte C — busca no histórico (`1a8712f`, fecha a ressalva do resumo com
> perda).** Cache no prompt fixo, janela no histórico que cresce, busca para recuperar o antigo sob
> demanda. A execução segue a disciplina de sempre (fatia pequena, testável, produção verde, aprovada
> antes de cada código). O histórico da deliberação fica abaixo.

**Um só programa × dois trilhos** — as duas frentes viram um único programa de trabalho (planejadas e
executadas juntas sobre uma fundação comum de persistência), ou dois trilhos separados que apenas se
reconhecem e compartilham conceitos?

- **Insumo obrigatório — ✅ ENTREGUE:** o **Marco 0** (estudo de tokens, §5) foi feito com medição real —
  [`ESTUDO-TOKENS-MARCO-0.md`](ESTUDO-TOKENS-MARCO-0.md). Ele prova a conciliação (§4) e quantifica o
  ganho de cada caminho.
- **Recomendação na mesa (do estudo, §9):** **dois trilhos coordenados, Frente B primeiro** — o custo
  (~70%) está inteiro na criadora, que corta 50–70% **na borda, sem descongelar o motor**; a Frente A é
  trabalho estrutural (rastro/HITL) que só precisa da suspensão dirigida na Fatia 4. Acoplar as duas num
  programa monolítico casaria o barato-urgente com o delicado-arriscado.
- **Fator decisivo (palavra do maestro):** **consumo de tokens.** O número esteve na mão.
- **✅ RESOLVIDO (2026-07-26):** o maestro bateu o martelo — **dois trilhos, Frente B primeiro** (ver o
  box no topo desta seção). Execução autorizada, fatia por fatia.

---

## 8. O que NÃO está no escopo desta rodada (nomeado, não feito)
- **Nenhum código.** Esta rodada foi só documentação.
- **Reescrever os ~50 capítulos de `cerebro/central/`** (o manual servido em `/ajuda` e lido pela IA
  criadora): eles ensinam a dualidade atual (Execuções × Conversas como lugares separados) como se fosse
  definitiva. Precisarão de uma passada **depois** que a unificação for executada — não agora.

## 9. Documentos relacionados
- Runtime (as fatias, o diagnóstico completo dos dois motores): [`REMODELAGEM-MOTOR.md`](REMODELAGEM-MOTOR.md).
- Autoria (as partes A–E da economia): [`ECONOMIA-TOKENS-IA-CRIADORA.md`](ECONOMIA-TOKENS-IA-CRIADORA.md).
- Evidência de mercado (por que a cura é "ligar o checkpointer"): [`BENCHMARK-MENSAGERIA-MOTORES.md`](BENCHMARK-MENSAGERIA-MOTORES.md).
- Governança (a regra que muda): `MIGRACAO.md §6.1`.
- **Não confundir** com a **Observabilidade** (`evento_log` + `/logs`, já no ar): aquela é o *entorno*
  (infra transversal, correlaciona por `execucao_id`); este programa é a *história do fluxo* (a timeline
  do que o agente fez). Convivem.
