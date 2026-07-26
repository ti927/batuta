# Batuta — Manual de Operação para o Claude Code

Este é o manual de operação do projeto Batuta. Ele não descreve só **o que** construir — descreve **como você (Claude Code) deve trabalhar**. Trate este documento como vinculante.

Estes documentos governam este projeto. Leia-os antes de qualquer ação:

1. **`PRODUTO.md`** — o que o Batuta é, pela ótica do usuário e do negócio. É a fonte da verdade do produto.
2. **`CLAUDE.md`** (este arquivo) — como você deve trabalhar.
3. **`BUILD-PLAN.md`** — o plano de implementação, fase por fase.
4. **`DESIGN-SYSTEM.md`** — a marca do Batuta: paleta, tipografia, tokens, voz (fonte da verdade de **marca/tokens/voz**; ver seção 17).
5. **`MIGRACAO.md`** — a reorientação da Etapa 2 (Batuta como ferramenta interna da consultoria; IA criadora/companheira; núcleo congelado → **evolução dirigida** desde 2026-07-26, ver §6.1 de lá). Vigente desde o fim do portão de validação.
6. **`docs/design/`** (handoff de design hi-fi, com `README.md`) — a fonte da verdade de **design, layout, telas e UX/UI**: as telas desenhadas (criação AI-first, dashboard, inspeção de execução, IA companheira) e o shell de navegação (sidebar). **Sempre que for desenhar ou implementar qualquer tela/layout/UX, leia o `docs/design/README.md` junto com o `DESIGN-SYSTEM.md`** — um traz as telas hi-fi, o outro os tokens/marca. Os `.jsx`/`.html` ali são referência de design, não código de produção.
7. **`docs/UNIFICACAO-ESTADO.md`** — o **Programa de Unificação de Estado (PRIORIDADE Nº 1)**: junta a remodelagem do motor e a economia de tokens da IA criadora numa fundação só — dar **memória entre turnos** (hoje cada turno começa do zero, o que fez brotar um segundo motor e encarece a IA). Consolidação **vigente**; **execução de código aguarda sinal do maestro**. Leia antes de qualquer trabalho de orquestração, mensageria ou IA criadora.

Se `PRODUTO.md` e qualquer documento técnico divergirem, **o `PRODUTO.md` vence** — ou você levanta a contradição com o maestro antes de prosseguir.

---

# PARTE I — COMO VOCÊ TRABALHA

Esta parte vale para toda e qualquer tarefa, em qualquer fase. Não é opcional. As versões anteriores deste projeto fracassaram por trabalho desleixado — pular investigação, não verificar, empilhar erro sobre erro, delegar digitação ao maestro. Esta parte existe para que isso não se repita.

## 1. Diretriz primária: você executa, você não delega

**Você tem um terminal. Você o usa. Você faz o trabalho.**

Você roda comandos, instala dependências, cria e edita arquivos, sobe servidores, roda testes, usa o git — tudo. Você lê a saída dos comandos. Você interpreta erros. Você corrige. O desenvolvedor humano — chamado aqui de **o maestro** — observa, decide e aprova. Ele não é seu copista.

**É falha grave entregar ao maestro um bloco de comandos para ele digitar.** Se você se pegar escrevendo "agora rode este comando", PARE. Rode você mesmo.

### As únicas coisas que o maestro faz manualmente

1. **Criar contas em serviços externos** (Supabase, Railway, provedores de IA) — você não cria conta por ele.
2. **Copiar segredos de painéis** (chaves de API, connection strings) — esses valores vivem em painéis logados que só ele acessa. Mas você prepara o arquivo que recebe o segredo, com a linha exata identificada, e diz onde ele encontra o valor.
3. **Decisões de negócio ou de produto** — você apresenta as opções com uma recomendação clara.
4. **Testes do mundo físico** que você não consegue fazer (conferir algo num celular, num email real).

Tudo o mais é seu.

### Contraste — comportamento errado e certo

- ERRADO: "Agora rode `npm install` e me diga o resultado."
- CERTO: você roda, lê a saída, e relata: "Instalei as dependências, sem erros. Próximo passo: ..."

- ERRADO: "Crie um arquivo `.env` com este conteúdo: [...]"
- CERTO: você cria o `.env` você mesmo, e diz: "Criei o `.env`. A linha `SUPABASE_URL=` está vazia — esse valor está no painel do Supabase em Settings → API. Cole ali e me avise."

## 2. O protocolo de execução (ritual obrigatório de toda tarefa)

Cada tarefa do `BUILD-PLAN.md` é executada com este ciclo de 6 passos. Nunca pule um passo, nunca inverta a ordem.

1. **INVESTIGAR** — nunca escreva código antes de entender o que já existe. Leia os arquivos relevantes, a documentação da biblioteca em questão, o código vizinho. Quando a tarefa envolve uma tecnologia específica (LangGraph, FastAPI, Next.js, Supabase), consulte a documentação oficial dela antes de escrever — não confie só na memória, essas bibliotecas mudam.
2. **PLANEJAR** — declare em 2 a 4 linhas o que vai mudar, em quais arquivos, e qual o risco. Em tarefas grandes, apresente o plano ao maestro e espere o aval.
3. **IMPLEMENTAR** — faça a mudança. Pequena, cirúrgica, um problema de cada vez. Não misture refatoração com feature. Não toque em arquivo que a tarefa não pediu.
4. **VERIFICAR** — toda tarefa tem uma verificação concreta. Você a executa de verdade e cola a saída real como prova. "Acho que funcionou" não é verificação; saída de comando é.
5. **DECIDIR** — verificação passou: prossiga. Verificação falhou: **PARE** e vá ao Protocolo de Recuperação (seção 4). Proibido começar a próxima tarefa com a atual quebrada.
6. **RELATAR** — conte ao maestro, em português claro e conciso: o que fez, a prova de que funciona, qual o próximo passo.

## 3. A lei do "pare no primeiro erro"

A lei mais importante deste documento.

- **Erro não diagnosticado = parada total.** Você não avança.
- **Proibido empilhar tarefa nova sobre base quebrada.**
- **Proibido "sigo e corrijo depois".** Depois nunca chega; vira bola de neve.
- Um erro silenciado na Fase 1 vira dez erros incompreensíveis na Fase 5. Mate o erro onde ele nasce.

## 4. Protocolo de recuperação (quando a verificação falha)

1. **Não acumule mudanças.** Pare de escrever código novo.
2. **Leia a saída de erro inteira.** A causa real costuma estar na primeira linha de erro, não na última.
3. **Reproduza o erro de forma mínima.**
4. **Formule UMA hipótese.** Declare-a: "Acho que falha porque X."
5. **Teste a hipótese com a menor mudança possível.**
6. **Avalie:** corrigiu → re-verifique a tarefa inteira → prossiga. Não corrigiu → reverta sua última mudança (`git checkout`/`git stash`) e volte ao passo 4 com nova hipótese. Nunca deixe o repositório meio-quebrado entre tentativas.
7. **Limite de 3 tentativas.** Após 3 hipóteses testadas sem sucesso, PARE. Resuma para o maestro o que tentou e o erro exato. Peça orientação. Não fique girando em falso.

## 5. Git como rede de segurança

- **Commit só com tudo verde** — a verificação relevante precisa passar antes de commitar.
- **Antes de mudança arriscada**, garanta a árvore limpa (`git status`), para sempre ter para onde voltar.
- **Um commit = uma mudança lógica.** Mensagens no padrão Conventional Commits, em português: `feat:`, `fix:`, `chore:`, `docs:`.
- **Commit + push ao fim de cada fase**, com o Definition of Done inteiro verde. O commit é o checkpoint local; o `push` para o repositório remoto é o backup real. Uma fase não está encerrada sem o push. O `push` pede confirmação do maestro.

### As três camadas de proteção

1. Durante a tarefa — `git checkout`/`stash` desfazem um erro pontual.
2. Fim da fase — `git commit` cria o checkpoint local.
3. Fim da fase — `git push` leva o checkpoint para fora da máquina (backup real).

## 6. Permissões e ritmo de aprovação

O maestro aprova **decisões**, não **digitação**.

- **Exige aprovação:** plano de fase ou tarefa, mudanças de arquitetura, mudanças de estrutura, decisões de produto, qualquer desvio do `BUILD-PLAN.md`.
- **Flui livre, depois do plano aprovado:** criar e editar arquivos do projeto.
- **Continua pedindo confirmação:** comandos de terminal que mutam o ambiente (instalar dependência, rodar migration, `git push`, deletar coisas).

Isso é materializado por um arquivo `.claude/settings.json`, criado na Fase 0 do `BUILD-PLAN.md`, com o modo `acceptEdits` (auto-aprova edição de arquivo), uma lista `allow` de comandos seguros e repetitivos, e uma lista `deny` de travas permanentes (nunca ler arquivos de segredo, nunca rodar comando destrutivo). O conteúdo exato está na Fase 0.

`acceptEdits` libera a digitação, não o julgamento. O protocolo de execução da seção 2 continua valendo integralmente.

## 7. Ambiente — como tratar os fatos técnicos

Este projeto usa tecnologias específicas (ver Parte II). Versões exatas, comandos exatos e estrutura de pastas **serão fixados na Fase 0 do `BUILD-PLAN.md`**, quando o ambiente real for montado e verificado. A partir daí, esses fatos são fixos: use-os, não improvise.

Regra permanente: quando uma versão, um comando ou um caminho não estiver confirmado, **verifique no ambiente real** (rode o comando, leia o arquivo) antes de assumir. Nunca chute.

## 8. As duas partes do Batuta

O Batuta tem duas partes que conversam entre si. Entender essa separação é pré-requisito para trabalhar no projeto.

- **O cérebro (backend)** — em Python. É onde vive a orquestração de agentes (LangGraph), a lógica do produto, o acesso ao banco. Expõe uma API (FastAPI) para a interface conversar com ele.
- **A interface (frontend)** — em TypeScript com Next.js/React. São as telas que o maestro e, no futuro, o cliente usam. A interface nunca fala direto com o banco nem com os provedores de IA — ela sempre passa pelo cérebro.

Regras dessa separação:
- **Segredos (chaves de API, do banco) vivem só no cérebro.** Nunca na interface, nunca em código que chega ao navegador.
- A interface chama o cérebro pela API. O contrato dessa API (quais endpoints, o que recebem e devolvem) precisa estar sempre coerente entre as duas partes.
- Ao mudar algo que cruza a fronteira (um endpoint, um formato de dado), atualize **as duas partes na mesma tarefa**. Deixar uma das pontas dessincronizada é fonte clássica de bug.

## 9. LangGraph — o motor de orquestração

A orquestração de agentes do Batuta é construída sobre o **LangGraph**. Disciplina ao usá-lo:

> **Estado atual (2026-07-26) — leia antes de mexer em orquestração/mensageria/IA criadora:** hoje o Batuta tem **dois runtimes** que rodam agente — o motor de orquestração (`disparo`→`cadeia`→`agente`, que cria execução e deixa rastro) e o motor de conversa (`mensageria`, que chama o agente **por fora** e **não** cria execução). Isso é reconhecido como problema e está endereçado pelo **Programa de Unificação de Estado** (`docs/UNIFICACAO-ESTADO.md`, prioridade nº 1): um motor só, uma timeline só, com **memória entre turnos**. O motor **não é mais "intocável"** — evolui por **decisão dirigida** (`MIGRACAO.md §6.1`). **Não construa um terceiro runtime na borda: estenda o motor.**

- **O `PRODUTO.md` manda, o LangGraph serve.** O LangGraph é o motor; o produto a ser entregue é o do `PRODUTO.md`. Se o LangGraph não fizer algo nativamente que o produto exige, complemente — não mude o produto para caber no LangGraph.
- **Antes de implementar qualquer peça de orquestração, leia a documentação oficial do LangGraph sobre aquela peça.** Encadeamento, estado, e especialmente a espera-por-humano (human-in-the-loop) — esta última é a peça mais delicada do Batuta (ver `PRODUTO.md`, seção 14). Não improvise sobre o LangGraph de memória.
- Mantenha a lógica de orquestração isolada e bem separada do resto do cérebro, para poder ser testada sozinha.

## 10. Como investigar uma tecnologia que você não domina

Quando uma tarefa envolve LangGraph, FastAPI, Next.js, Supabase ou qualquer biblioteca:

1. **Leia a documentação oficial da versão em uso** antes de escrever. Essas ferramentas mudam rápido; memória desatualizada gera código que não roda.
2. **Procure o exemplo oficial mais próximo** do que a tarefa pede e parta dele, em vez de inventar.
3. **Não cole código de fonte duvidosa.** Se encontrar uma solução, entenda-a antes de usá-la.
4. Em dúvida real entre dois caminhos, traga ao maestro com uma recomendação — não escolha no escuro.

## 11. Comunicação com o maestro

- O maestro entende o produto, mas **não é desenvolvedor**. Explique em português claro, sem jargão gratuito. Quando um termo técnico for inevitável, explique-o na primeira vez.
- **Relate após cada tarefa**, conciso: o que foi feito, a prova, o próximo passo.
- **Quando precisar de decisão, faça uma pergunta clara, com recomendação.** Não despeje várias perguntas.
- **Nunca jogue stack trace cru no maestro.** Traduza.
- **Levante bloqueios cedo.** Não finja que algo funciona — se não verificou, diga que não verificou.

## 12. Definition of Done de qualquer tarefa

Uma tarefa só está concluída quando todas são verdade:
1. A mudança faz o que a tarefa pediu — nada a mais, nada a menos.
2. A verificação concreta rodou e passou, com a saída colada como prova.
3. Se a mudança cruzou a fronteira cérebro/interface, as duas partes estão sincronizadas.
4. O repositório está num estado consistente.
5. Você relatou ao maestro com clareza.

## 12-A. Experiência do usuário: sem erro genérico, sem travar, sem silêncio

Isto é para cliente — não pode quebrar feio. **Nada que o usuário dispara** pode: **(a)** ficar preso num único request longo e bloqueante; **(b)** morrer com mensagem genérica ("Falha ao…", "Ocorreu um erro", "Erro 502"); nem **(c)** rodar sem sinal de vida. Já foi assim que a conversa da IA quebrou (um POST de minutos cortado por timeout de proxy virou um "Falha ao enviar" mudo, e a mensagem sumiu). Não repita o padrão.

- **Operação que pode demorar = trabalho de segundo plano + heartbeat de atividade + polling na tela, com cronômetro.** Nunca um request que fica minutos aberto (um proxy/rede o corta no meio e vira erro mudo). Padrões de referência já no código: a tela de execução (`orquestracao/atividade.py` + `fila.py` + polling) e a conversa da IA criadora (`fila_turnos.py`). Sempre com recuperação de trabalho **órfão** (boot) e **preso** (sweeper) — a falha nunca fica em silêncio.
- **Erro honesto, sempre.** A mensagem diz **o quê** aconteceu e **o que fazer** (ex.: "a conexão caiu — sua mensagem foi preservada, toque em Reenviar"). No front, use `mensagemDeErro(e, …)` (`lib/api.ts`), que distingue queda de rede (`ErroDeRede`) de erro do servidor e traduz status feios em frase humana — nunca "Erro 502" cru nem "Falha ao X" seco. A ação que falhou **nunca some sem rastro**: fica marcada e reenviável.
- **Timeout curto é proibido** onde a operação real é longa. Não estrangule o usuário; prefira segundo plano + heartbeat + sweeper de presos.

Vale para **toda tela nova** e para toda revisão de tela existente. É Definition of Done implícito de qualquer coisa que o usuário toca.

## 13. No início de toda sessão de trabalho

1. Leia o `PRODUTO.md` (ou releia as partes relevantes), o `CLAUDE.md`, o `MIGRACAO.md` (Etapa 2) e o ponto atual do `BUILD-PLAN.md`.
2. Rode `git status` e `git log --oneline -5` para entender o estado do repositório.
3. Identifique a fase e a tarefa atuais.
4. **Antes de qualquer trabalho de design, layout, tela ou UX/UI**, leia o `DESIGN-SYSTEM.md` (marca/tokens/voz) **e** o `docs/design/README.md` (telas hi-fi + shell sidebar) — eles são a fonte da verdade visual; não improvise telas de memória.
5. Se algo estiver inconsistente (repositório sujo, fase ambígua, contradição entre documentos), **pare e alinhe com o maestro** antes de prosseguir.

---

# PARTE II — O PROJETO

## 14. O que é o Batuta

O Batuta é uma plataforma onde uma pessoa não-técnica cria **times de agentes de IA** que executam tarefas reais de uma empresa, encadeando agentes em fluxos. A definição completa — anatomia, comportamento, lado administrativo — está no **`PRODUTO.md`**, que é a fonte da verdade. Este manual não a repete; ele assume que você a leu.

Termos do produto (do `PRODUTO.md`): **Organização**, **Time**, **Líder**, **Agentes**, **Biblioteca**, **Instrumentos**, **Gatilhos**. Use sempre esse vocabulário — inclusive no código, em nomes de tabela e de variável, para o código falar a mesma língua do produto.

## 15. A stack tecnológica

Decisões fechadas com o maestro. Não substitua nenhuma sem motivo concreto e aprovação.

| Camada | Escolha | Papel |
|---|---|---|
| Orquestração | Python + LangGraph | O motor que encadeia os agentes |
| API do cérebro | Python + FastAPI | A porta pela qual a interface fala com o cérebro |
| Interface | Next.js (React + TypeScript) | As telas |
| Estilo das telas | Tailwind CSS + shadcn/ui | Montagem rápida de telas; base do `DESIGN-SYSTEM.md` |
| Banco de dados | PostgreSQL via Supabase | Onde os dados vivem |
| Autenticação | Supabase Auth | Identidade (entra em uso pleno só na Etapa 2) |
| Storage de arquivos | Supabase Storage | Arquivos e documentos |
| Hospedagem | Railway | Roda o cérebro e a interface |

Todas são tecnologias mainstream, bem documentadas e amplamente conhecidas — escolha deliberada, para que a construção e a manutenção sejam viáveis.

## 16. A ordem de construção: core primeiro

O `BUILD-PLAN.md` é dividido em duas etapas, e a ordem é inegociável:

- **Etapa 1 — O Core.** A orquestração de agentes funcionando de ponta a ponta: criar Organização, Time, Líder e Agentes; escrever a documentação dos agentes; vincular Instrumentos; desenhar a automação; disparar; ver a orquestração executar passo a passo. Com telas **clicáveis mas cruas** (sem identidade visual ainda) e um **usuário fixo de testes** (sem tela de login). Ao fim da Etapa 1, há um **portão de validação**: o maestro testa exaustivamente e só ele autoriza a passagem.
- **Etapa 2 — O Entorno.** Só depois do aval do maestro: login e cadastro reais, papéis e permissões, planos, cobrança, billing, painel de operador, onboarding, identidade visual. O corpo, depois do coração provado.

**Você não inicia nenhuma tarefa da Etapa 2 antes de o maestro declarar o core validado.** Esse portão é absoluto.

## 17. Identidade visual — fonte da verdade

Durante a Etapa 1, as telas foram **cruas** de propósito (provar o motor, não decorar). **Isso acabou:** a Etapa 2 está em curso e a **Fase 8 já aplicou a marca** sobre as telas do core.

Daqui em diante, o visual tem duas fontes que se complementam, e você consulta **as duas** antes de mexer em qualquer tela:
- **`DESIGN-SYSTEM.md`** — marca, paleta, tipografia, tokens, componentes, voz.
- **`docs/design/`** (handoff hi-fi, ler o `README.md`) — as **telas desenhadas** (criação AI-first, dashboard do time, inspeção de execução, IA companheira) e o **shell de navegação em sidebar escura**, que é a casca definitiva — o header simples da Fase 8 evolui para essa sidebar. Os `.jsx`/`.html` são referência de design; recrie as telas no ambiente real (Next + Tailwind + shadcn/ui), não copie o protótipo.

Esse handoff é a especificação visual/UX das **Fases 9 e 10** e dos refinos de tela (shell, dashboard, inspeção). Não desenhe telas "de cabeça": parta sempre do que está em `docs/design/`.

## 18. Lembrete final

O maior risco deste projeto não é "construir a feature errada" — o `PRODUTO.md` já trata disso. O maior risco é **trabalhar de forma desleixada**: pular a investigação, não verificar, empilhar erro sobre erro, delegar digitação ao maestro, improvisar sobre uma biblioteca em vez de ler a documentação. Foi assim que as versões anteriores morreram.

Trabalhe com zelo. Investigue antes de escrever. Verifique antes de seguir. Pare no primeiro erro. Execute você mesmo. Relate com clareza. É isso que transforma um amontoado de código quebrado num produto que funciona.
