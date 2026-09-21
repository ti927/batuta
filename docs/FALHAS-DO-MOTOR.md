# Estudo de falhas do motor — o que pode dar errado, e o que fazer quando der

**Data:** 2026-09-21 · **Origem:** o caos da execução `e76224a6` (automação "Gerar Posts Instagram")

> Hoje o motor é desenhado para **não falhar**. Quando falha, vira caos — porque quase
> nenhuma peça foi desenhada para o **momento seguinte à falha**. Este documento varre o
> ciclo de vida inteiro de uma execução, lista o que pode quebrar em cada etapa, diz o que
> acontece hoje e propõe a mitigação. É catálogo de trabalho, não teoria.

Legenda de gravidade:
🔴 quebra o fluxo ou engana o usuário · 🟡 confunde, mas não quebra · 🟢 já está coberto

---

## 1. O incidente de 21/09, explicado com prova

### 1.1 A linha do tempo

| hora | o quê |
|---|---|
| 11:44 | execução criada (agendamento). Passo 1: capa gerada, `pedir_aprovacao` enviado |
| 15:12 | aprovação "aprovado1" **pela tela** → publica no Instagram, segue para o Gerador Carrossel |
| 15:16 | Gerador Carrossel gera 3 slides e pede aprovação → execução em `aguardando_humano`, conversa do Telegram amarrada |
| 15:17:53 | resposta **pelo Telegram**: *"Reprovado. Utilize as mesmas imagens, mas retire as logomarcas…"* |
| 15:18:03 | o agente **pergunta de volta** em vez de seguir (passo 4, zero instrumentos acionados) |
| 15:18:28 | *"Retire completamente"* → turno do Telegram começa a regenerar as 3 imagens |
| **15:19:16** | o LangGraph salva o checkpoint **step 9**: o modelo já pediu as 3 imagens, os resultados ainda não voltaram |
| **15:20:05** | clique **na tela**: "reprovado: Retire completamente" → o motor de fluxo entra na **mesma execução** |
| 15:20:06 | **erro 400 da Anthropic** → execução marcada `falhou`, aviso enviado no Telegram |
| 15:21:01 | as 3 imagens voltam; o turno do Telegram continua do step 9, **em cima de uma execução morta** |
| 15:21:26 | o turno termina "com sucesso" e manda os slides regenerados |
| 15:23:35 | a mensageria abre uma **execução nova** (modo conversa) e segue conversando fora do fluxo |

### 1.2 Por que deu erro 400 — a resposta exata

A mensagem da Anthropic foi:

```
messages.6: `tool_use` ids were found without `tool_result` blocks immediately after:
toolu_017uzgLmnpWPv8YdZdXbUEYG, toolu_01FAaQjgX5CGydBkNEW5aUKx, toolu_01VsiQCBmi5EGLHnXZjxytcB
```

Três ids — exatamente as três chamadas de `FotoMontagem 1:1` que estavam no ar naquele instante.

A tradução: **a conversa que foi mandada para a Anthropic estava pela metade.** Ela continha
o momento em que o modelo diz "gere estas 3 imagens" e **não** continha as 3 respostas. A API
recusa isso, sempre — é regra do protocolo, não problema de modelo, de rede ou de chave.

E por que chegou pela metade? Porque **a tela e o Telegram escrevem na mesma memória do
LangGraph**, com o mesmo endereço:

- Telegram: `thread_portao = f"{execucao.id}:{no_id}"` — `mensageria/servico.py:1288`
- Tela: `tid = f"{execucao.id}:{no_id}"` — `mensageria/retoma.py:313`

Enquanto as 3 imagens rodavam (1 min 45 s entre o step 9 e o step 10), essa memória ficou num
estado intermediário — normal e esperado, é assim que o LangGraph salva. A tela abriu o mesmo
endereço no meio do buraco, leu o estado pela metade, colou a mensagem nova no fim e mandou
para a API.

**A prova está no banco.** Os checkpoints do thread `e76224a6…:agente_nik77`:

| checkpoint | pai | step | hora | quem |
|---|---|---|---|---|
| `1f1b5cfc-f47d…8009` | …8008 | 9 | 15:19:16 | Telegram salva antes de gerar as imagens |
| `1f1b5cfe-cc22…800a` | **…8009** | 10 | **15:20:06** | **a tela entra** |
| `1f1b5cfe-cc26…800c` | …800b | 12 | 15:20:06 | morre 2 ms depois (o 400) |
| `1f1b5d00-e154…800a` | **…8009** | 10 | 15:21:01 | o Telegram volta das imagens |
| `1f1b5d01-c9bc…8012` | …8011 | 18 | 15:21:26 | o Telegram termina |

Dois checkpoints diferentes com **o mesmo pai** (`…8009`) e **o mesmo número de step (10)**.
Isso é uma bifurcação: dois escritores na mesma memória, cada um achando que era o único.

**Conclusão:** o 400 não foi causa, foi consequência. A causa é que **duas portas mexem na
mesma execução sem nenhuma trava entre elas**.

---

## 2. A doença única: o motor não tem noção de DONO

Os quatro sintomas que vimos são o mesmo defeito estrutural — **estado que pertence à
execução mora na borda**, e quando a borda não está lá (ou está em duplicidade), o motor não
sabe de nada:

| o que deveria ser da execução | onde mora hoje | o que acontece quando falha |
|---|---|---|
| **a trava** ("alguém já está mexendo aqui") | `conversas.estado = 'bot_respondendo'` | a tela não a enxerga → duas entradas simultâneas → o 400 |
| **o relógio** ("esta espera vence quando?") | `conversas.aguardando_ate` | espera sem canal **nunca vence e nunca avisa** |
| **o endereço** ("por onde pedi a aprovação?") | `passos_execucao.saida.aprovacao` | o caminho por canal não grava esse bloco → execução fica sem endereço |
| **o dono do fio de memória** (thread do LangGraph) | não existe | dois escritores bifurcam o checkpoint |

Uma doença, quatro sintomas. Qualquer remendo que trate um sintoma de cada vez ressurge no
próximo — foi exatamente o que aconteceu nas correções anteriores.

---

## 3. Catálogo de falhas, etapa por etapa

### A. Disparo (gatilho, agendamento, webhook, manual, chamada de outra automação)

| # | modo de falha | hoje | grav. | mitigação |
|---|---|---|---|---|
| A1 | gatilho agendado não dispara (servidor fora, agendador morto) | vigia de agendamentos + reconciliador + aviso | 🟢 | — |
| A2 | disparo duplicado (servidor local rodando contra o banco de produção) | nenhuma defesa | 🟡 | carimbar `host` na execução e alertar quando duas origens diferentes disparam a mesma automação no mesmo minuto |
| A3 | automação desativada no meio | aviso de alvo desativado | 🟢 | — |
| A4 | disjuntor desliga a automação após falhas seguidas | cobre, e pula as falhas causadas pelo próprio Batuta | 🟢 | — |
| A5 | webhook repetido (Instagram) | dedupe + anti-loop + teto | 🟢 | — |

### B. Fila, processo e infraestrutura

| # | modo de falha | hoje | grav. | mitigação |
|---|---|---|---|---|
| B1 | servidor reinicia no meio (deploy) | recuperação de órfãs marca `falhou` + evento | 🟢 | — |
| B2 | worker trava sem reiniciar o processo | vigia de presas (15 min, 3 sinais de vida) | 🟢 | — |
| B3 | pool de workers morto | `/saude` reporta | 🟢 | — |
| B4 | um vigia periódico passa a levantar exceção | batimento dos vigias + sonda + `/status` | 🟢 | — |
| B5 | banco/rede congelados | `tcp_user_timeout` + keepalive + elos + `/status` | 🟢 | — |
| B6 | **mais de uma réplica no Railway**: o boot de uma marca `falhou` as execuções em andamento da outra | a recuperação de órfãs não filtra por host | 🔴 | filtrar por host/instância, ou usar dono com prazo em vez de "tudo que está em andamento é órfão". **A confirmar se hoje roda 1 réplica** |
| B7 | execução fica em `aguardando` e nunca é reivindicada | nenhum vigia por tempo de fila | 🟡 | vigia de fila parada: `aguardando` há mais de N min com pool vivo = evento de erro |

### C. Execução de um nó (agente + instrumentos)

| # | modo de falha | hoje | grav. | mitigação |
|---|---|---|---|---|
| C1 | o nó levanta exceção | passo falho gravado + segue pela saída de erro se desenhada; senão a execução falha | 🟢 | — |
| C2 | **instrumento responde `ok: false` e o agente narra sucesso** | vai para `erros_instrumentos` no rastro e o diagnóstico acusa — **mas o fluxo segue como se tivesse dado certo** | 🔴 | falha de instrumento deveria poder acionar a saída de erro do nó, como uma exceção aciona |
| C3 | instrumento demora demais | prazo do passo + limite de rede por chamada + sinal de vida | 🟢 | — |
| C4 | teto de custo / tempo / passos estourado | exceção com mensagem explicativa e "o que fazer" | 🟢 | — |
| C5 | provedor de IA devolve 429/500 | vira exceção → C1 | 🟡 | retentativa com espera para 429/5xx, que é transitório; hoje morre na primeira |
| C6 | provedor de IA devolve **400 de histórico inválido** | vira exceção → a execução inteira morre | 🔴 | 400 de protocolo é **defeito de estado**, não do fluxo: não pode matar a execução. Deve recusar a entrada e manter a espera de pé |
| C7 | modelo não chama o instrumento que o markdown manda | o rastro mostra `instrumentos_acionados` vazio | 🟢 | — (é adesão do modelo; o rastro prova) |

### D. A decisão de caminho (as setas)

| # | modo de falha | hoje | grav. | mitigação |
|---|---|---|---|---|
| D1 | nó sem saída ligada | ramo termina + aviso nomeando o agente | 🟢 | — |
| D2 | saída sem "siga por aqui quando…" | aviso explicando o que preencher | 🟢 | — |
| D3 | regra exata referencia campo ausente na ficha | aviso "não foi possível conferir a regra" | 🟢 | — |
| D4 | agente declara um rótulo que não existe | cai no roteador por IA | 🟢 | — |
| D5 | nenhuma condição bate e não há "se nenhuma das outras" | ramo termina + aviso | 🟢 | — |
| D6 | laço no grafo (ex.: `reprovado` volta para o próprio nó) | teto de passos corta | 🟡 | a mensagem é técnica ("possível laço infinito"); deveria dizer qual nó está em laço e quantas voltas deu |
| D7 | destino aponta para um nó que não existe | erro mata a execução **sem gravar passo falho** | 🟡 | validar no salvamento do desenho e gravar passo falho nomeando o destino quebrado |
| D8 | **o markdown do agente não conhece as saídas do nó** | nada detecta | 🔴 | ver E4 e §4.4 |

### E. A espera por humano — onde mora o caos

| # | modo de falha | hoje | grav. | mitigação |
|---|---|---|---|---|
| E1 | **duas portas respondem a mesma espera (tela + canal)** | nenhuma trava compartilhada | 🔴 | **trava na execução** (§4.1) |
| E2 | **a espera nunca vence quando não há canal amarrado** | nenhum vigia olha para `aguardando_humano` | 🔴 | **relógio na execução** (§4.2) |
| E3 | **o passo de pausa criado pelo canal perde o bloco `aprovacao`** | o turno de portão grava o passo sem ele → a execução fica sem endereço para ser re-amarrada a um canal | 🔴 | gravar `aprovacao` no passo, como o caminho da tela já faz |
| E4 | **o agente termina o turno de portão sem escolher ramo e sem pedir aprovação** | indistinguível de "ele perguntou de propósito" — silêncio total | 🔴 | evento de erro + aviso na tela depois de N rodadas sem decisão |
| E5 | o agente chama `pedir_aprovacao` **dentro** do turno de portão | o turno ignora o `pausado` e trata como "ele perguntou" | 🔴 | honrar `pausado`/`aprovacao` (mesmo conserto de E3) |
| E6 | teto de idas-e-vindas do portão estourado | o agente explica e a resposta segue pelo caminho mecânico | 🟢 | — |
| E7 | aprovador nunca responde | cutucada + despedida + estacionar/cancelar conforme o Tipo de fluxo | 🟢 | — (só vale quando há canal — ver E2) |
| E8 | conversa assumida por uma pessoa de verdade | o pedido é enviado e a resposta é engolida | 🟡 | avisar na tela que aquele portão está com o canal surdo |
| E9 | destinatário nunca deu `/start` no bot | o envio falha; o motivo aparece no rastro | 🟡 | detectar na hora de amarrar e avisar antes de o fluxo parar |
| E10 | dois nós pedem aprovação na mesma onda (fan-out) | o segundo vira pendência e só é apresentado depois | 🟡 | documentar na tela; hoje parece que "sumiu" |

### F. A retomada

| # | modo de falha | hoje | grav. | mitigação |
|---|---|---|---|---|
| F1 | **dois escritores no mesmo thread do LangGraph** | nada impede → bifurca o checkpoint | 🔴 | dono da execução (§4.1); nunca abrir um thread que já está sendo escrito |
| F2 | retomada falha por qualquer motivo | execução vira `falhou`, avisa pelo canal | 🟡 | distinguir "entrada duplicada/recusada" (não é falha do fluxo) de "quebrou de verdade" |
| F3 | **execução vira `falhou` e a conversa continua viva apontando para ela** | ninguém desvincula | 🔴 | ao falhar, desvincular a conversa e mandar recado honesto |
| F4 | vigia de presas mata a retomada demorada | três sinais de vida; já foi consertado uma vez | 🟢 | — |
| F5 | resposta tardia depois da conversa encerrada | religa pelo contato | 🟢 | — |
| F6 | mensagem técnica crua vai para o resultado e para a tela | `Error code: 400 - {'type': …}` | 🟡 | traduzir para frase humana; o texto cru fica no log |

### G. Espera de tempo e sub-fluxo

| # | modo de falha | hoje | grav. | mitigação |
|---|---|---|---|---|
| G1 | nó "Esperar" sem tempo configurado | segue direto + aviso | 🟢 | — |
| G2 | servidor reinicia durante a espera | o estado está no banco; o vigia solta assim mesmo | 🟢 | — |
| G3 | automação-alvo do "Chamar" nunca termina | o chamador fica preso | 🟡 | teto de espera do chamador (a filha tem tetos; o chamador não tem prazo próprio) |
| G4 | filha falha | saída de erro do nó "Chamar", se desenhada | 🟢 | — |

### H. Visibilidade — o que o usuário vê

| # | modo de falha | hoje | grav. | mitigação |
|---|---|---|---|---|
| H1 | **a tela mostra os botões de aprovação enquanto o Telegram conduz** | nada indica | 🔴 | mostrar "respondendo pelo Telegram…" e desabilitar os botões |
| H2 | execução morta e agente ainda falando | acontece (F3) | 🔴 | F3 |
| H3 | um aviso do motor ("terminou sem seguir por nenhum caminho") fica só no rastro | não aparece como alerta | 🟡 | avisos de execução viram alerta na lista de execuções |
| H4 | não dá para saber se uma execução rodou em modo degradado | o carimbo `memoria: duravel/legado` existe no passo | 🟢 | — |

---

## 4. As mitigações, na ordem em que eu faria

### 4.1 — UM DONO POR EXECUÇÃO (resolve E1, F1 e metade do resto)

Duas colunas novas em `execucoes`: **`dono`** (quem está mexendo agora) e **`dono_ate`** (até
quando esse direito vale — um prazo, para nunca travar para sempre).

Regra única, válida para todas as portas: **quem quer mexer numa execução pega o dono
primeiro.** Quem não consegue, recebe recusa honesta, não entra.

- A tela clica em responder e o Telegram está no meio → *"Sua resposta pelo Telegram ainda
  está sendo processada. Aguarde alguns instantes."*
- O Telegram chega e a tela está no meio → a mensagem fica para o próximo turno.
- O dono vence sozinho (prazo) → nada trava para sempre, e o vencimento vira evento.

Isso resolve de uma vez a trava da espera **e** o dono do fio de memória do LangGraph:
ninguém abre o thread sem ser dono da execução.

### 4.2 — TODA ESPERA TEM PRAZO PRÓPRIO (resolve E2)

Coluna `espera_ate` na execução. Um vigia novo varre `aguardando_humano` vencido e: registra
evento, avisa quem pediu, e aplica a ação de abandono do fluxo (estacionar ou cancelar) —
**independente de haver canal amarrado**. Hoje a espera sem canal é o único estado do sistema
que ninguém varre.

### 4.3 — O CANAL GRAVA O QUE A TELA GRAVA (resolve E3 e E5)

O turno de portão passa a honrar `pausado`/`aprovacao` e a gravar o bloco `aprovacao` no
passo — exatamente como o caminho da tela já faz. Duas superfícies, um formato de rastro só.

### 4.4 — SILÊNCIO DO AGENTE VIRA ALARME (resolve E4 e D8)

Quando o nó tem 2+ saídas e o turno de portão termina sem escolher ramo **nem** pedir
aprovação, isso vira evento de erro no banco de logs, com o nome do agente e a contagem de
rodadas. Depois de N rodadas assim, aviso na tela: *"o agente X está conversando há N rodadas
sem decidir o caminho — confira o markdown dele"*.

**Complemento, na criação:** a IA criadora e o validador do desenho passam a exigir que o
markdown de um agente com 2+ saídas **cite os rótulos**. Foi exatamente esse buraco que deixou
o Gerador Carrossel sem saber que existia um caminho "reprovado".

### 4.5 — FALHA NÃO CONTAMINA (resolve F2, F3, C6, H2)

- 400 de protocolo (histórico inválido) **não mata a execução**: recusa a entrada, mantém a
  espera de pé, registra evento.
- Execução que vira `falhou` **desvincula a conversa** e manda um recado honesto.
- Antes de gravar, todo turno em voo confere se a execução ainda é dele.

### 4.6 — A TELA CONTA A VERDADE (resolve H1)

Quando existe conversa amarrada respondendo, a tela de execução mostra *"respondendo pelo
Telegram…"* e desabilita os botões. É a correção mais barata do lote e a que teria evitado o
incidente inteiro — porque o clique fatal foi uma reação racional a uma tela que mentia.

### 4.7 — Depois, na ordem: C2, C5, B6, B7, D6, D7, G3

---

## 5. O que eu ainda NÃO verifiquei

Honestidade sobre o alcance deste estudo:

1. **Quantas réplicas o cérebro roda no Railway.** Se for mais de uma, B6 é falha ativa hoje,
   não teórica.
2. **Se o debounce da mensageria protege contra duas mensagens do mesmo contato em rajada
   durante um turno de portão.** Li o caminho principal, não o de rajada.
3. **O caminho do "Para cada item" combinado com aprovação.** O código guarda as pendências,
   mas não testei uma repetição pedindo aprovação enquanto outras rodam.
4. **Se algum outro lugar do código abre um thread do LangGraph com endereço derivado da
   execução.** Encontrei dois (tela e canal); não varri o projeto inteiro.

Estes quatro pontos entram na próxima passada.
