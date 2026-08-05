# Remodelagem do Motor — Unificação do Runtime (estudo + plano)

> **Status:** ▶️ **EM EXECUÇÃO ESTRANGULADORA.** Fatias **1 e 2 NO AR** (ver §5); Fatia 3 é a próxima na ordem do plano. Cada fatia começa só com sinal explícito do maestro. A Fatia 4 exige suspensão dirigida do congelamento do núcleo (seção 7).
>
> **Origem (2026-07-21):** pedido direto do maestro — *"QUERO UM PROJETO COMPLETO DE REMODELAGEM DO MOTOR, CÉREBRO, TUDO DE MANEIRA SIMPLIFICADA, E QUERO UM ESTUDO SINCERO, NÃO QUERO QUE FAÇA UM TREM PRA ME AGRADAR."*
>
> Este é o documento-fonte da **Frente A (runtime)** do **Programa de Unificação de Estado** (âncora: `docs/UNIFICACAO-ESTADO.md`). O `BUILD-PLAN.md` aponta para o programa; o programa aponta para cá.

---

## 1. Contexto — por que esta fase existe

Gatilho concreto: um time de atendimento por Telegram (id `15e136a1-4448-46d7-97ff-85f2a8e3bf3b`) que faz lançamentos num endpoint do Bubble.io "fez tudo certo" na conversa, mas **o lançamento não aconteceu** — e o maestro **não teve como inspecionar**, porque um agente conversacional **não gera execução** para checar; o rastro fica só na conversa.

Ao investigar, veio à tona um problema estrutural, não pontual. Nas palavras do maestro:
- *"hoje eu tenho que checar histórico de execução, você tá me sugerindo checar histórico de conversa, daqui a pouco vou ter que checar histórico de tudo."*
- *"tá uma zona esse app, um monte de amarração sem fim."*
- *"tudo começou por conta da merda do portão de aprovação, que só fica colocando nó no meio do fluxo."*
- *"a intenção era instruir agentes e direcionar os passos, caso tenha resultado A ou resultado B; virou uma burocracia infernal."*

O estudo abaixo é honesto: separa o que é **complexidade essencial** (o produto precisa, ou é lei do projeto) do que é **complexidade acidental** (a gente se enrolou sozinho), e propõe um caminho de simplificação que **não explode a produção** (batuta.team, clientes ao vivo, 714 testes).

---

## 2. Diagnóstico sincero — a doença (com evidência no código)

### A raiz: existem DOIS motores que fazem a MESMA coisa de formas incompatíveis
- **Motor 1 — Orquestração (disparo):** `orquestracao/disparo.py::rodar_execucao` → `orquestracao/cadeia.py::executar_cadeia` (laço nó-a-nó, `MAX_PASSOS=25`) → `orquestracao/agente.py::executar_agente`. Cria `Execucao` + `PassoExecucao`. Fila robusta (`fila.py`, 3 workers, `FOR UPDATE SKIP LOCKED`, recuperação de órfãos no boot e de presos por sweeper). Heartbeat ao vivo (`disparo._escrever_atividade`). **Rastro rico e inspecionável.**
- **Motor 2 — Conversa (mensageria):** `mensageria/servico.py::processar_turno` → `_rodar_turno` → chama `executar_agente` **direto**, fora do Motor 1. **Não cria execução.** Rastro só em `MensagemConversa`. Pior: `_rodar_turno` recebe `resultado["erros_instrumentos"]` (rastro cru de cada instrumento, coletado em `agente.py` "para diagnóstico") e **descarta**. Um agente conversacional que chama um instrumento e ele falha **não deixa rastro nenhum**.

Os dois reimplementam, cada um do seu jeito: rodar agente, bifurcar (A/B), esperar humano, medir custo, tratar falha, deixar rastro.

### O portão de aprovação é a SOLDA entre os dois — e solda racha
- `no.gate = true` (flag no nó) → `Execucao` fica `aguardando_humano` (`cadeia.py`).
- `mensageria/aprovacao.py::vincular_pausa` enxerta `conversa.execucao_id` na conversa.
- **Dois turnos com "reset":** o agente renasce entre apresentar e retomar; só texto cruza. Para dizer ao agente renascido o que fazer, foi preciso inventar a instrução escondida `_instrucao_de_fluxo` (`agente.py`).
- **Retomada PARTIDA em dois caminhos:** pela TELA (`retoma.retomar_execucao`, `POST /execucoes/{id}/responder`) e pelo CANAL (`servico._turno_de_portao` → `retoma.avancar_apos_gate`). Mais a religação tardia por fora (`aprovacao.execucao_parada_do_contato`) quando o sweeper já fechou a conversa.
- **Sinceridade:** cada peça dessas **consertou um bug real**. Não é burocracia gratuita — é o custo estrutural de a mesma ideia ("um humano decide/responde") ter 4 implementações que precisam concordar entre si a cada mudança.

### A cascata de config de 5 camadas existe para reconciliar os dois mundos
`mensageria/config.py`: `GLOBAL < canal < perfil("Tipo de fluxo") < ajustes < no.config`, governando **3 dimensões não relacionadas** ao mesmo tempo (tempos de conversa; limites de segurança; comportamento do portão), com **chaves mortas** (`max_passos`, `modelo_roteador`, `acao_ao_estourar`). "Tipo de fluxo" governar 3 coisas é a raiz da confusão de config.

### As 5 "histórias" fragmentadas são o subproduto direto
(a) tela de execução (`PassoExecucao` + `Execucao.atividade`); (b) thread (`MensagemConversa`); (c) banco de logs `evento_log` (`/logs`); (d) uso (`/uso`); (e) criação (`TurnoCriacao`). **O maestro olha em lugar diferente conforme o fluxo começou** — é exatamente o "histórico de tudo".

### A causa-raiz de tudo isso: o congelamento do núcleo
`MIGRACAO.md §6.1` — *"O núcleo já validado é intocável… se uma fase parece exigir mudança no núcleo, pare e pergunte ao maestro."* A regra foi prudente, mas teve efeito colateral: **empurrou tudo o que era novo para a borda.** Quando veio a mensageria, em vez de a conversa virar extensão do motor, virou **um segundo motor inteiro na borda**. A complexidade que irrita o maestro é o preço pago por não poder tocar o motor. **Descongelar de forma dirigida é a chave da simplificação** — e há precedente: em 2026-06-16 (`MIGRACAO.md §6.1`, exceção autorizada) o maestro liberou tocar `cadeia.py` para os grafos, mantendo o laço do agente (`create_react_agent`) intocado. Este plano segue o mesmo formato.

---

## 3. O que é ESSENCIAL (não remover) × ACIDENTAL (simplificar)

**Essencial — é o produto ou é lei do projeto, permanece:**
- Instruir agentes por markdown; comportamento 100% do markdown.
- Bifurcação A/B pelo próprio agente declarar a saída (`seguir_para`) — **isto é o produto**.
- Aprovação humana antes de ação irreversível (PRODUTO §14 — "peça mais delicada").
- Trabalho longo em segundo plano + heartbeat + polling + recuperação de órfãos(boot)/presos(sweeper) — **lei** (CLAUDE.md §12-A).
- Vários gatilhos (manual/hora/webhook/conversa) — legítimos.

**Acidental — a gente se enrolou sozinho, simplificar/unificar:**
- **Dois runtimes.** O turno de conversa deveria ser o MESMO motor, não um paralelo.
- **Cascata de config de 5 camadas** + chaves mortas + "Tipo de fluxo" governando 3 coisas.
- **Portão de 2 turnos com reset + instrução escondida + retomada partida.**
- **5 superfícies de história.**
- **Constantes espalhadas/espelhadas** (`MAX_PASSOS`, `MAX_RODADAS_GATE=8`, `TETO_INATIVIDADE_EXEC_MIN=15` espelhado como `LIMIAR_PRESO_MIN`, `N_TRABALHADORES=3`).

---

## 4. Arquitetura-alvo (o destino)

**Um motor só. Uma linha do tempo só. Todo fluxo — botão, hora, webhook ou mensagem — é UMA `Execucao` com UMA timeline.**

### Modelo-alvo (poucas entidades)
- **`Execucao`** (espinha, mantida). Ganha `origem/gatilho` (manual|agendamento|webhook|instagram|conversa) e `modo` (`tarefa` | `conversa`).
- **`PassoExecucao`** (registro único da timeline, mantido). Ganha `tipo`:
  - `agente` — roda agente (o de hoje).
  - `roteador` — classifica (o de hoje).
  - **`espera_humano`** (NOVO, o unificador) — representa **tanto o portão de aprovação quanto "aguardando resposta do cliente"**. Carrega o que foi apresentado, o canal/destinatário esperado e como a retomada segue. É o que hoje está espalhado entre `no.gate`, `vincular_pausa` e o estado da `Conversa`.
  - `mensagem_entrante` (opcional) — a fala do humano que chegou pela borda, como passo na mesma timeline.
- **`Agente`/`Instrumento`/`Automacao`/`cadeia`(grafo)** — intocados. Bifurcação por `seguir_para` — intocada.

### Como cada coisa se expressa nesse modelo único
- **Bifurcação A/B:** idêntica a hoje. Intocável.
- **Portão (HITL):** o nó `gate` gera um passo `espera_humano`; a execução vai a `aguardando_humano` (já é quase isso). Some a "solda": a retomada por canal deixa de ser um segundo motor.
- **Conversa:** uma `Execucao` de `modo=conversa`. Ao responder o cliente, o agente emite um passo `espera_humano` do tipo "aguardando mensagem" e a execução **dorme**; a próxima mensagem a **acorda**. **Mesmo mecanismo do portão** — muda só quem é o humano (cliente × aprovador).

### `Conversa` / `MensagemConversa` (faseado, sem colapso brusco)
- `Conversa` **sobrevive como adaptador de TRANSPORTE** (contato, token, debounce, takeover `humano_assumiu`, alcance do bot). Deixa de ser a fonte da história.
- A história migra para `PassoExecucao`. `MensagemConversa` vira **projeção/aba** derivada da timeline filtrada por canal (uma lente, não um dado concorrente).

### Config colapsada (de 5 camadas → o mínimo, separada por dimensão)
- **Dimensão A — Tempos de conversa** (debounce/timeout/nudge/encerrar). Só em `modo=conversa`. Camadas: `global < canal`. Perfil deixa de governar isto.
- **Dimensão B — Limites de segurança** (teto de passos, `teto_usd`, ação ao estourar). Camada: `global < automacao`. **`max_passos` (morto) e `max_turnos` (conversa) viram a MESMA chave "teto de passos".**
- **Dimensão C — Portão** (forma, ação ao abandonar, max rodadas). Camada: `automacao < no`.
- **Presets:** de 4 (que misturam dimensões) para **2 honestos** (`Interno`, `Atendimento externo`). "Disparo" deixa de ser preset (é um **gatilho**). "Personalizado" deixa de ser preset (é "sem preset + ajustes").
- **Morrem:** `max_passos`, `modelo_roteador`, `acao_ao_estourar` como camada de perfil. Constantes espelhadas (`TETO_INATIVIDADE`/`LIMIAR_PRESO`) viram uma só.

### Uma superfície de história
- **UMA timeline por execução** (`PassoExecucao` com `tipo`), com projeções por gatilho: tela de execução = timeline crua; aba Conversa = a **mesma** timeline como thread; `/uso` passa a cobrir a conversa automaticamente (a conversa agora grava passos).
- `evento_log` (`/logs`) **fica** — observabilidade transversal de infra (http/auth/falhas), correlacionada por `execucao_id`. É o entorno, não a história do fluxo.
- `TurnoCriacao` (IA criadora) **não colapsa na mesma timeline de runtime** — é outro domínio (autoria, não execução de fluxo). **[Reconciliado 2026-07-26]** Mas atenção: a IA criadora sofre da **mesma doença-raiz** deste motor (turno sem memória, reconstrói do texto, gasta tokens) e se cura pela **mesma família** (persistir estado entre turnos). Por isso ela é a **Frente B** do mesmo programa — ver `docs/UNIFICACAO-ESTADO.md`. Se as duas frentes viram um só programa ou dois trilhos coordenados é a **decisão adiada** (depende do estudo de tokens); o que **não se sustenta mais** é tratá-las como coisas sem relação.

**O que o maestro passa a olhar SEMPRE:** a timeline da execução. "Começou por botão, hora ou mensagem" vira etiqueta/filtro, não um lugar diferente do app.

---

## 5. Caminho de migração — ESTRANGULADOR, sem dia-D

Cada fatia é pequena, testável, deixa a produção verde e os testes passando. Nunca há troca simultânea dos dois mundos. Se o maestro parar em qualquer ponto, o sistema fica coerente.

### FATIA 1 — Unificar o RASTRO (maior valor / menor risco) ⭐ — ✅ NO AR (1a+1b, 2026-07-26)
Toda conversa nasce com uma `Execucao` sombra `modo=conversa` (criada preguiçosamente no 1º turno). `_rodar_turno` passa a gravar o passo do agente pelo **mesmo** registrador do disparo (`disparo._fazer_registrador`), **incluindo `erros_instrumentos`** (hoje descartado). Comportamento visível ao cliente **inalterado** — só passa a existir rastro. **Aditivo, baixo risco, NÃO toca o portão.**
→ **Resolve JÁ a dor de hoje:** dá para inspecionar o "agente lançador" do Bubble (qual instrumento chamou, com que corpo, o que a API respondeu, o erro).

> **✅ FATIA 1 COMPLETA (1a+1b) NO AR (2026-07-26).** 1a = deploy `7dcdfc4` + migração `snd00sombra01` (backend — o rastro passa a EXISTIR). 1b = deploy `4505a8d`, sem migração (o rastro fica VISÍVEL, reusando a tela de Execuções). Onde o construído ficou diferente do esboço acima:
> - `Execucao` ganhou `modo` ('fluxo'|'conversa'), `automacao_id` **nulável** e `conversa_id` (FK). A sombra vive no estado próprio **`'conversa'`**, que a fila (`aguardando`) e os recuperadores de órfãs/presas (`em_andamento`) **IGNORAM** — por isso **nada da fila/sweeper mudou** e nenhum reinício a marca `'falhou'`. Sem automação, fica fora de todas as listas/métricas (join com automação) → não polui taxa de sucesso nem duplica custo.
> - O passo **não** reusa literalmente `disparo._fazer_registrador` (acoplado à cadeia + à sessão do worker): é um escritor dedicado `servico._gravar_rastro_conversa` que **espelha a mesma forma** (entrada/saída/instrumentos/`erros_instrumentos`/uso), porém em **sessão própria e à prova de falha** (isolamento do heartbeat) — o rastro nunca quebra o atendimento (§12-A). O turno de **portão (gate) fica de fora** (pertence ao rastro do fluxo).
> - **1b (visibilidade):** filtro **"Conversas"** na aba Execuções (molde do "Agendadas"; busca no cliente, fora dos stat cards) + a MESMA tela de detalhe. `execucao_acessivel` escopa a sombra pela conversa→agente→time; novo `GET /times/{id}/conversas-rastro`; a página de detalhe tolera sem-automação e não polla o estado 'conversa'.
> - 100% aditivo; **736 testes** + tsc/eslint/`next build`; duplicar automação e inspeção de execução seguem idênticos. **Falta:** só teste ao vivo.

> **📊 MEDIÇÃO + CACHE do runtime (2026-07-26, pós-Fatia 1, deploy `bf36cd8`).** O rastro da 1ª conversa real (Reembolsos/Bubble) permitiu MEDIR o custo: o peso **não** é o histórico reenviado (< 600 tok/turno), e sim a **multiplicação do laço ReAct** — o `create_react_agent` reenvia [ferramentas + prompt de sistema] a CADA passo de tool-calling (turno de 9 chamadas ao Bubble = 84,7k tok de entrada, ~17× o conteúdo real).
> - **Ganho rápido entregue:** `_prompt_de_sistema` (`orquestracao/agente.py`) marca `cache_control: ephemeral` no prompt de sistema **só na Anthropic** (guard por provedor, espelha `criacao/prompt.prompt_criadora`) + captura `cache_read`/`cache_creation` no uso, para o custo ficar correto (a Anthropic conta o token cacheado na entrada pelo número cheio, mas cobra ~10%). Beneficia os DOIS motores (ambos passam por `executar_agente`).
> - **Medido ao vivo (conversa nova, mesmo caso):** 48% da entrada servida do cache → custo **US$ 0,63 vs US$ 1,00** a preço cheio = **−37%**. (A contagem de tokens NÃO cai — o cacheado conta cheio; cai o CUSTO.)
> - **A cura ESTRUTURAL — persistência entre turnos (parar de re-buscar o mesmo dado a cada turno) — segue PENDENTE:** ela ELIMINA os reenvios; o cache só os barateia. É a próxima empreitada estruturada (Fatias 4–5).

### FATIA 2 — Unificar MEDIÇÃO/limites sobre a execução sombra — ✅ NO AR (2026-08-04)
Teto de custo/turnos passa a ler da timeline (contagem de passos + soma de uso); `Conversa.turnos`/`custo_acumulado_usd` viram cache derivado. Prepara a Dimensão B.

> **✅ FATIA 2 COMPLETA (2026-08-04).** Backend puro, sem migração (as colunas já existem). Onde ficou diferente do esboço:
> - **Nova autoridade da medição:** `servico.medir_conversa(sessao, conversa) -> (turnos, custo)` lê a timeline-sombra e substitui a leitura dos contadores. O **teto de chat** (`processar_turno`) passa a decidir por ela. O turno de **portão** continua medido pelo contador (é rastro do FLUXO, não da conversa — só entra na timeline na Fatia 4); por isso os contadores **continuam sendo escritos** e viram *puramente* derivados só na Fatia 4.
> - **Conserto de fidelidade:** o passo da sombra passou a guardar o uso **CHEIO** do turno (agente + transcrição + visão + instrumentos pagos) — antes guardava só o do agente, e medir pela timeline ficaria MENOR que o contador, afrouxando o limite de segurança. `_gravar_rastro_conversa` ganhou `uso_cheio`; o `uso_turno` é medido uma vez, antes de gravar o passo, e reusado pelo contador. (De quebra, a tela de inspeção mostra o custo real por turno.)
> - **Regras espelhadas ao token:** `medir_conversa` conta só passos PRODUTIVOS (com texto OU ramo) e soma o uso deles — turno sem produto e turno de erro rodam mas NÃO contam, igual ao contador. `custo_de_entrada` (mesmo cálculo do `_custo_do_turno`).
> - **Sem duplicar `/uso`:** a sombra segue fora daquela agregação (INNER JOIN com automação; sombra tem `automacao_id=None`). Escopo aditivo e reversível; nada visível ao cliente muda.
> - **Verificação:** `test_medir_conversa.py` (6 testes — equivalência com o contador em chat puro, com custo além do agente, turno sem produto, turno de erro, sem-sombra) + suíte de mensageria/portão/uso/config verde. `test_teto_estourado_passa_para_humano` migrado para semear a timeline (a nova autoridade). **Falta:** só teste ao vivo.

### FATIA 3 — Colapsar a CONFIG por dimensão (seção 4) — ✅ PARTE SEGURA NO AR (2026-08-04)
2 presets + 3 dimensões, com `resolver_config` como fachada de compatibilidade. Migração preguiçosa (automação migra ao re-salvar, como o grafo já faz). Remover chaves mortas. Efetivo idêntico para as automações existentes.

> **✅ FATIA 3 (PARTE SEGURA) COMPLETA (2026-08-04).** Backend puro, SEM migração, **zero mudança de comportamento** (verificado contra a produção: 18 automações, só `interno`/sem-perfil; ninguém usava disparo/personalizado; 0 canais com regra própria). Decisão do maestro: fazer só a parte segura agora e **adiar** o re-dimensionar a cascata + o teto-de-passos para a Fatia 4. O que entrou:
> - **Chaves MORTAS removidas:** `max_passos`, `modelo_roteador` (o motor usa o fixo `MAX_PASSOS`/`MODELO_PADRAO`, nunca lia essas) e `acao_ao_estourar` (o teto SEMPRE passa para humano — o campo na tela era decorativo/enganoso). Saíram de `GLOBAL`/`PERFIS`/`ESCOLHAS`/`CAMPOS`.
> - **Presets 4 → 2 honestos:** `interno` (Processo interno) + `atendimento` (Atendimento externo). Caíram `disparo` (é um GATILHO, vira `origem` na Fatia 4) e `personalizado` (é só "sem tipo + ajustes", já é como a tela trata a ausência de perfil).
> - **Constante espelhada unificada:** `diagnostico_execucao.LIMIAR_PRESO_MIN` passou a importar `fila.TETO_INATIVIDADE_EXEC_MIN` (fonte única; sem ciclo de import — verificado).
> - **Front:** a tela de config é 100% data-driven de `/config/fluxo` (`painel_config`) → o seletor mostra 2 tipos e o campo "Ao estourar o limite" some **sozinho**; `tsc` verde, nenhuma linha de front mudou.
> - **Verificação:** testes de config/perfil/gate/diagnóstico/fila verdes; `test_config_fluxo`/`test_gate_conversa` migrados de `perfil="disparo"` para `ajustes` explícitos (a forma "direto"/"cancelar" continua sendo VALOR válido, só não mais empacotada num preset).
>
> **ADIADO para a Fatia 4 (com o descongelamento §7):** (a) `max_passos`→`cadeia.py` como teto de passos configurável (núcleo congelado); (b) o re-dimensionar a cascata por dimensão (A=tempos `global<canal`; B=limites `global<automacao`; C=portão `automacao<no`) — é o único trecho que MUDA comportamento ao vivo (os tempos das 9 automações `interno`) e exige acompanhar o front; casa melhor com a unificação do motor.

### FATIA 4 — Portão como passo `espera_humano` unificado (delicada) ⚠️ — ▶️ EM EXECUÇÃO (descongelamento nº 2 autorizado 2026-08-04)
Introduzir `PassoExecucao.tipo`. O portão produz um passo `espera_humano` explícito. A retomada por CANAL deixa de ser motor paralelo: `servico` só ENTREGA a resposta como `mensagem_entrante` e chama o **único** caminho de retomada. `_turno_de_portao` vira adaptador fino. Tela e canal continuam como **pontos de entrada** legítimos, convergindo para UMA função. **Exige a suspensão dirigida do congelamento (seção 7).** Rede de testes máxima.

> **Sub-fatiamento (2026-08-04) — a Fatia 4 é grande demais para um passo só num produto ao vivo. Quebrada em três, cada uma testável e parável:**
> - **4.1 — `PassoExecucao.tipo` (vocabulário da timeline). ✅ NO AR (2026-08-04).** Migração aditiva `tip00passo001` (coluna nulável `tipo`: `agente`|`roteador`|`espera_humano`|`mensagem_entrante`). Cada passo passa a se carimbar: o nó de PORTÃO = `espera_humano` (`cadeia.py` + o re-run na tela `retoma.py`), os demais `agente`/`roteador`, e o turno conversacional-sombra = `agente` (`servico.py`). O registrador (`disparo._fazer_registrador`) mapeia `tipo`→coluna. **Nada LÊ a coluna ainda (4.1 só POPULA) → zero mudança de comportamento.** Verificação: `test_cadeia_grafo` (portão→espera_humano, roteador→roteador, agente→agente) + `test_rastro_conversa` (coluna no banco). Não matou o "renasce" — é fundação.
> - **4.2 — Unificar o RASTRO da retomada (tela × canal). ✅ NO AR (2026-08-04).** **Achado da investigação (honesto):** os dois caminhos de re-run do portão compartilham MENOS do que um "merge numa função só" sugeria — o re-run pelo canal está tecido na máquina de conversa (`_rodar_turno`: transcrição/visão/thread/contador/entrega pela borda) e o da tela é passo-a-passo autônomo; um merge de ciclo-de-vida agora seria arriscado na peça mais frágil, para pouco ganho — e a **4.3 reescreve o próprio re-run** (ao dar memória), sendo o lugar natural de unificar a EXECUÇÃO. Então a 4.2 fez a convergência SEGURA e de maior valor: **o portão pelo CANAL passa a deixar um passo `espera_humano` na timeline do fluxo** (como a tela já fazia) — some a lacuna "canal não gera passo"; o portão fica inspecionável em qualquer superfície (rumo a UMA timeline). O aditivo mecânico já estava unificado (`_processar_aprovacao`→`retomar_execucao`). Detalhes: passo gravado DIRETO (não pelo registrador, que auto-soma custo de instrumento) com `uso=[]` — o custo do turno já vive na `MensagemConversa`, então **não conta em dobro no `/uso`**; `ordem_inicial` do avanço passou a `ultimo.ordem+1` (consistente com a tela). Entrega/ciclo-de-vida do canal IDÊNTICOS → nada visível ao cliente muda. Verificação: `test_gate_conversa` (novo `test_canal_portao_deixa_passo_espera_humano_no_fluxo`) + suíte de gate/aprovação verde. **NÃO matou o "renasce" (o agente ainda re-roda) — isso é a 4.3.**
> - **4.3 — A CURA: memória entre turnos (o agente do portão retoma do estado salvo, não re-deriva).** Risco alto. Decisão de arquitetura à parte (checkpointer nativo do LangGraph × solução caseira) — trazida com a doc oficial lida (§9) e o estudo de tokens, ANTES de qualquer código. É aqui que o "renasce" morre — e o lugar natural de unificar a EXECUÇÃO do re-run (não só o rastro).
>
> **Fatos da versão confirmados no ambiente (2026-08-04):** LangGraph **1.2.2**; `create_react_agent` aceita `checkpointer` e há `interrupt()`/`Command` (`langgraph.types`); mas o `PostgresSaver` **não está instalado** (só o de memória) → a 4.3 nativa exigiria a dependência `langgraph-checkpoint-postgres` + tabelas próprias.

### FATIA 5 — Conversa vira `modo=conversa` de primeira classe
"Esperar mensagem" vira passo `espera_humano` (sem ramo). Sweeper de conversa e de execução **convergem** (a conversa herda o heartbeat/recuperação do Motor 1). `Conversa` encolhe para transporte. **Cuidado central:** o sweeper de presos NÃO pode confundir "dormindo esperando o cliente" com "travada" (conversa é potencialmente eterna; execução clássica termina).

### FATIA 6 (opcional) — Projeção única na UI
Aba Conversa lê a timeline; `MensagemConversa` vira view.

---

## 6. O que NÃO tocar / riscos

**Carga essencial disfarçada de burocracia (NÃO remover):**
- Heartbeat + sweeper de presos + recuperação de órfãos (`fila.py`, `disparo._escrever_atividade`, `recuperar_execucoes_presas`): é lei (CLAUDE.md §12-A) e é ouro. Unificar **para cima** (a versão da conversa é mais fraca — a conversa herda a do motor).
- HITL antes de ação irreversível (parede de ativação, `gate`): produto + lei. Simplificar a mecânica, **nunca** remover a garantia.
- Bifurcação A/B via `seguir_para`: é o produto. Intocável.
- "Apresentado vs. narrado" (o que a pessoa viu, não o status que o agente narra depois): parece barroco, é correção de bug real. Preservar a semântica.

**Riscos do rewrite num sistema com clientes:**
- O portão é a peça mais delicada e concentra os bugs históricos → mexer **por último** (por isso a Fatia 1 não o toca).
- **Conversa eterna × execução finita** → maior risco conceitual; o heartbeat de presos não pode matar conversa dormindo (Fatia 5).
- Migração de dados viva → seguir o padrão preguiçoso já provado (normaliza na leitura; migra ao re-salvar); nada destrutivo em `MensagemConversa`.
- 1 réplica (a fila e o agendador assumem isso) → manter.

---

## 7. Governança — suspensão dirigida do congelamento

O congelamento (`MIGRACAO.md §6.1`) precisa ser **suspenso de forma limitada e explícita**, e só **antes da Fatia 4**, em dois pontos:
1. `orquestracao/cadeia.py` e `orquestracao/agente.py` — para acomodar o passo `espera_humano` de primeira classe e o `modo=conversa`.
2. `PassoExecucao` (modelo) — para ganhar `tipo`.

**Permanece congelado:** a semântica de `seguir_para`, a garantia HITL, o contrato de instrumentos, a fila `FOR UPDATE SKIP LOCKED`, o laço `create_react_agent` do agente. Suspender **não** é licença para reescrever o motor — é licença para **absorver a borda de conversa para dentro dele**, faseado e testado. Seguir o precedente formal de 2026-06-16 (aditivo curto ao `MIGRACAO.md`, aprovado pelo maestro antes da Fatia 4).

---

## 8. Verificação (como cada fatia se prova)
- **Fatia 1:** disparar uma conversa; abrir a nova timeline e ver o instrumento chamado, o corpo, a resposta, o erro. Suíte completa verde; nenhum teste de comportamento visível ao cliente muda.
- **Fatias 3–5:** `test_config_fluxo.py`, `test_gate_conversa.py`, `test_aprovacao_por_canal.py`, `test_portao_*`, `test_fila_sweeper.py` reescritos/verdes; efetivo idêntico para automações existentes; teste ao vivo do portão (aprovar → agenda E encaminha) e da conversa dormindo/acordando.

## 9. Arquivos-chave (por fatia)
- **Fatia 1:** `cerebro/mensageria/servico.py` (`_rodar_turno` grava passo; para de descartar `erros_instrumentos`), `cerebro/orquestracao/disparo.py` (`_fazer_registrador` como registrador único), `cerebro/modelos.py` (`Execucao` sombra), `cerebro/diagnostico_execucao.py`, tela de inspeção de execução (front).
- **Fatia 3:** `cerebro/mensageria/config.py`, `cerebro/fila.py` + `cerebro/diagnostico_execucao.py` (unificar constantes), `cerebro/orquestracao/cadeia.py` (`MAX_PASSOS` → teto configurável).
- **Fatias 4–5:** `cerebro/orquestracao/cadeia.py`, `cerebro/orquestracao/agente.py`, `cerebro/mensageria/retoma.py` (colapsar os dois caminhos), `cerebro/mensageria/aprovacao.py` + `cerebro/mensageria/servico.py` (`_turno_de_portao` vira adaptador), `cerebro/mensageria/sweeper.py` + `cerebro/fila.py` (sweepers convergem), `cerebro/modelos.py` (`PassoExecucao.tipo`; `Conversa` encolhe).
- **Espinha reusada (apoiar-se, não reescrever):** `cerebro/fila.py`, `cerebro/observabilidade/` (`evento_log` transversal), `cerebro/orquestracao/disparo.py::_fazer_registrador` (`PassoExecucao` como registro único).

---

## 10. Relação com outras fases / observações
- **Parte de um programa maior:** esta remodelagem é a **Frente A (runtime)** do **Programa de Unificação de Estado** (`docs/UNIFICACAO-ESTADO.md`), que a coordena com a **Frente B (autoria)** — a economia de tokens da IA criadora (`docs/ECONOMIA-TOKENS-IA-CRIADORA.md`). As duas compartilham a fundação "memória entre turnos"; o benchmark (`docs/BENCHMARK-MENSAGERIA-MOTORES.md`) é a evidência comum.
- **Não confundir** com a fase de **Observabilidade** (`evento_log` + `/logs`, já no ar): aquela é o *entorno* (infra transversal). Esta é a *história do fluxo* (a timeline do que o agente fez). As duas convivem — `evento_log` correlaciona por `execucao_id`.
- A dor imediata que originou o estudo (não dá pra depurar o agente lançador do Bubble) é resolvida já na **Fatia 1**, sem tocar o portão. Se o maestro quiser só isso primeiro, é a fatia certa.
