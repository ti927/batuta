# Batuta — Plano de Implementação

Este é o roteiro de construção do Batuta.

**Antes de usar este documento, leia o `PRODUTO.md` e o `CLAUDE.md` por completo.** Toda tarefa aqui é executada seguindo o **protocolo de execução de 6 passos** e a **lei do pare no primeiro erro** do `CLAUDE.md`. Este plano diz *o que* fazer; o `CLAUDE.md` diz *como*.

## Como este plano é organizado

O plano tem **duas etapas**, e a ordem é inegociável:

- **ETAPA 1 — O CORE.** A orquestração de agentes funcionando de ponta a ponta, com telas clicáveis mas cruas e um usuário fixo de testes. Termina num **portão de validação**.
- **ETAPA 2 — O ENTORNO.** Login real, permissões, cobrança, identidade visual. Só começa após o maestro validar o core.

## Regras de uso

- **Uma fase por vez, uma tarefa por vez.** Não adiante trabalho.
- Cada tarefa tem três blocos: **Investigar**, **Implementar**, **Verificar**.
- Cada fase termina com um **Definition of Done** — verificações concretas. Só avance quando todas passarem, com a saída colada como prova.
- **Commit + push ao fim de cada fase.**
- Erro: aplique o Protocolo de Recuperação do `CLAUDE.md`. Não empilhe.
- Onde uma tarefa depender de conta ou segredo externo, você prepara tudo ao redor e pede ao maestro apenas o valor que só ele tem.
- **A Etapa 2 está bloqueada até o maestro declarar o core validado** (ver Portão de Validação).

---

# ETAPA 1 — O CORE

Objetivo da etapa: ao final, o maestro consegue, por telas clicáveis, criar uma Organização, criar um Time, criar o Líder e os Agentes, escrever a documentação de cada um, vincular Instrumentos, desenhar uma automação (a cadeia), dispará-la, e ver a orquestração executar passo a passo — inspecionando o que cada agente recebeu, decidiu e devolveu. Tudo com um usuário fixo de testes, sem login, e telas cruas.

---

## FASE 0 — Fundação do ambiente

**Objetivo:** o ambiente de desenvolvimento montado e verificado, as duas partes do projeto criadas e "dando sinal de vida", as contas externas prontas. Nenhuma lógica de produto ainda. Esta fase existe para garantir base sólida — não a apresse.

**Pré-requisitos:** o maestro precisa ter conta no GitHub.

### Tarefa 0.1 — Verificar e preparar a máquina

**Investigar:** descobrir o que está instalado na máquina do maestro — se há Python, Node.js, git, e em quais versões.

**Implementar:** garantir o necessário para o projeto: uma versão atual de Python, uma versão atual de Node.js (LTS), e git. Onde faltar, orientar o maestro a instalar (você indica de onde baixar; a instalação no sistema é uma das ações manuais do maestro).

**Verificar:** cada ferramenta responde com sua versão no terminal. **Registre neste ponto, no relato ao maestro, as versões exatas obtidas** — elas passam a ser os fatos fixos do ambiente, conforme a seção 7 do `CLAUDE.md`.

### Tarefa 0.2 — Repositório

**Investigar:** confirmar com o maestro o nome do repositório (sugestão: `batuta`).

**Implementar:** o maestro cria um repositório vazio no GitHub. Você o clona para a máquina, num caminho local **fora de qualquer pasta sincronizada por nuvem** (OneDrive, Dropbox, Google Drive — sincronização de nuvem corrompe o `.git`). Oriente um caminho local simples.

**Verificar:** `git status` funciona no diretório; o caminho não contém pasta de nuvem.

### Tarefa 0.3 — Estrutura de duas partes

**Investigar:** revise a seção 8 do `CLAUDE.md` (as duas partes). Decida, e apresente ao maestro, a estrutura de pastas: uma pasta para o cérebro (Python) e uma para a interface (TypeScript), dentro do mesmo repositório.

**Implementar:** crie a estrutura de pastas. Ainda sem código de produto — só o esqueleto.

**Verificar:** a estrutura existe e está clara; o maestro entende o que é cada pasta.

### Tarefa 0.4 — O cérebro dá sinal de vida

**Investigar:** leia a documentação oficial do FastAPI sobre o exemplo mínimo.

**Implementar:** monte o ambiente Python (ambiente virtual, gerenciador de dependências) e crie a aplicação FastAPI mínima — um único endpoint de saúde (ex.: responde "Batuta cérebro no ar").

**Verificar:** você sobe o cérebro e, com um comando no terminal, recebe a resposta do endpoint de saúde. Cole a saída.

### Tarefa 0.5 — A interface dá sinal de vida

**Investigar:** leia a documentação oficial do Next.js sobre criar um projeto novo.

**Implementar:** crie o projeto Next.js com TypeScript e Tailwind. Configure o shadcn/ui. Deixe uma página inicial que apenas escreve "Batuta" na tela.

**Verificar:** você sobe a interface e o maestro abre o endereço local no navegador e vê a página.

### Tarefa 0.6 — As duas partes se falam

**Investigar:** entenda como a interface Next.js faz uma chamada a uma API externa, e como o FastAPI libera essa chamada (CORS).

**Implementar:** faça a página da interface chamar o endpoint de saúde do cérebro e mostrar a resposta na tela.

**Verificar:** o maestro abre a página no navegador e vê, vinda do cérebro, a mensagem de saúde. Isso prova que as duas partes conversam — a espinha do projeto está de pé.

### Tarefa 0.7 — Permissões do Claude Code

**Investigar:** confirme se há pasta `.claude/` no repositório.

**Implementar:** crie o `.claude/settings.json` com o modo `acceptEdits`, uma lista `allow` com os comandos seguros e repetitivos do projeto (instalar dependências, rodar os servidores de desenvolvimento, rodar testes, comandos de leitura do git, inspeção de arquivos) e uma lista `deny` de travas permanentes (nunca ler arquivos `.env`/segredos, nunca rodar comandos destrutivos). Materializa a seção 6 do `CLAUDE.md`.

**Verificar:** o arquivo é JSON válido; editar um arquivo do projeto não pede mais confirmação; um comando fora da lista `allow` ainda pede.

### Tarefa 0.8 — Contas externas

**Implementar:** o maestro cria as contas e os projetos no Supabase e no Railway. Você o orienta passo a passo. Você cria o arquivo de segredos do cérebro (ex.: `.env`) com todas as chaves necessárias listadas e vazias; o maestro preenche os valores, e você indica exatamente onde cada um é encontrado. Garanta que o arquivo de segredos está no `.gitignore`.

**Verificar:** o arquivo de segredos existe, preenchido, e **não** é rastreado pelo git (confirme com `git status`).

### Definition of Done — Fase 0

- [ ] Versões de Python, Node.js e git verificadas e registradas
- [ ] Repositório clonado, fora de pasta de nuvem
- [ ] Estrutura de duas partes (cérebro / interface) criada
- [ ] Cérebro FastAPI responde no endpoint de saúde (saída colada)
- [ ] Interface Next.js abre no navegador
- [ ] A interface exibe uma mensagem vinda do cérebro (as duas partes se falam)
- [ ] `.claude/settings.json` criado e funcionando
- [ ] Contas Supabase e Railway criadas; arquivo de segredos preenchido e fora do git
- [ ] **Commit + push:** `chore: fundação do ambiente do Batuta`

---

## FASE 1 — O modelo de dados do core

**Objetivo:** as tabelas que sustentam o core, criadas no banco do Supabase. Esta fase desenha a arquitetura de dados; o código que cria as tabelas é escrito e testado por você.

### Arquitetura das tabelas do core

Esta é a especificação. As tabelas, seus campos e suas relações. Você implementa e testa a criação delas no Supabase.

**`organizacoes`** — a empresa.
- identificador único
- nome
- identificador do dono (na Etapa 1, sempre o usuário fixo de testes)
- datas de criação e atualização

**`times`** — pertencem a uma organização.
- identificador único
- organização a que pertence (relação obrigatória)
- nome
- descrição
- datas de criação e atualização

**`agentes`** — pertencem a um time. Cobre tanto o Líder quanto os Agentes (a distinção é um campo).
- identificador único
- time a que pertence (relação obrigatória)
- nome
- papel: "lider" ou "agente"
- conteúdo do `agent.md` (texto)
- conteúdo do `skill.md` (texto)
- conteúdo do `tools.md` (texto)
- conteúdo do `soul.md` (texto)
- qual modelo de IA este agente usa
- datas de criação e atualização
- regra: cada time tem no máximo um agente com papel "lider"

**`instrumentos`** — a biblioteca de instrumentos disponível; cada instrumento pertence a um time.
- identificador único
- time a que pertence (relação obrigatória)
- nome
- tipo do instrumento (ex.: chamada de API, busca web, gerar imagem, etc. — os tipos do `PRODUTO.md`, seção 13)
- configuração do instrumento (estrutura flexível, conforme o tipo)
- datas de criação e atualização

**`agente_instrumentos`** — a ligação entre agentes e instrumentos (um agente tem vários instrumentos no cinto; um instrumento pode estar no cinto de vários agentes).
- agente
- instrumento

**`automacoes`** — a definição de um fluxo: o gatilho e a cadeia de agentes. Pertence a um time.
- identificador único
- time a que pertence (relação obrigatória)
- nome
- tipo de gatilho (mensagem recebida, agendamento, webhook de entrada — `PRODUTO.md`, seção 12)
- configuração do gatilho (estrutura flexível, conforme o tipo)
- a cadeia: a sequência ordenada de agentes que processa a tarefa
- se está ativa
- datas de criação e atualização

**`execucoes`** — o registro de cada vez que uma automação roda.
- identificador único
- automação que foi executada (relação)
- estado: aguardando, em andamento, aguardando humano, concluída, falhou
- o que iniciou a execução (a entrada)
- o resultado final
- datas de início e fim

**`passos_execucao`** — cada passo de uma execução (cada agente da cadeia que processou a tarefa). É o que permite inspecionar a orquestração passo a passo.
- identificador único
- execução a que pertence (relação)
- ordem do passo na cadeia
- agente que processou
- o que o passo recebeu (entrada)
- o que o passo produziu (saída)
- estado do passo
- datas de início e fim

Observações de arquitetura:
- Toda tabela de dados de negócio carrega, direta ou indiretamente, o vínculo com uma organização — o isolamento entre organizações e times do `PRODUTO.md` depende disso.
- Decisões finas (tipos exatos de cada campo, índices) são da implementação — você as toma seguindo a documentação do Supabase, e as explica ao maestro ao relatar.

### Tarefa 1.1 — Conectar o cérebro ao banco

**Investigar:** leia a documentação do Supabase sobre conexão a partir de uma aplicação Python.

**Implementar:** configure o cérebro para se conectar ao banco do Supabase usando a connection string do arquivo de segredos.

**Verificar:** o cérebro sobe e consegue uma conexão de teste com o banco, sem erro.

### Tarefa 1.2 — Criar as tabelas

**Investigar:** revise a arquitetura das tabelas acima. Defina como as migrations serão feitas (uma ferramenta de migration para Python, ou o mecanismo do Supabase) e apresente a escolha ao maestro.

**Implementar:** escreva e aplique as migrations que criam todas as tabelas do core, com seus campos e relações.

**Verificar:** todas as tabelas aparecem no Table Editor do Supabase, com os campos e relações corretos. Cole a lista das tabelas criadas.

### Tarefa 1.3 — O usuário fixo de testes

**Investigar:** revise a seção 16 do `CLAUDE.md` — na Etapa 1 não há login; existe um usuário fixo de testes que é o "dono" de tudo.

**Implementar:** crie o usuário fixo de testes no banco (um registro fixo, conhecido) e faça o cérebro tratá-lo como o usuário atual de todas as operações, por enquanto. Deixe isso isolado e bem marcado no código, para ser substituído com facilidade na Etapa 2.

**Verificar:** o cérebro consegue identificar o usuário fixo em uma operação de teste.

### Definition of Done — Fase 1

- [ ] Cérebro conecta ao banco do Supabase sem erro
- [ ] Todas as tabelas do core criadas e visíveis no Supabase
- [ ] Relações entre tabelas corretas
- [ ] Usuário fixo de testes criado e reconhecido pelo cérebro
- [ ] **Commit + push:** `feat: modelo de dados do core`

---

## FASE 2 — Gerir Organizações, Times e Agentes

**Objetivo:** o maestro consegue, por telas cruas mas clicáveis, criar e gerenciar Organizações, Times, o Líder e os Agentes — com a documentação (`agent.md`, `skill.md`, `tools.md`, `soul.md`) de cada um.

Cada tarefa abaixo envolve as duas partes (cérebro e interface) e deve mantê-las sincronizadas.

### Tarefa 2.1 — Organizações

**Investigar:** defina os endpoints do cérebro para criar, listar, editar e remover organizações.

**Implementar:** os endpoints no cérebro; a tela crua na interface para criar, listar, editar e remover organizações.

**Verificar:** o maestro cria uma organização pela tela; ela aparece na lista e no banco do Supabase.

### Tarefa 2.2 — Times

**Implementar:** endpoints e tela para criar, listar, editar e remover times dentro de uma organização.

**Verificar:** o maestro cria um time dentro de uma organização; ele aparece corretamente vinculado, na tela e no banco.

### Tarefa 2.3 — Agentes e sua documentação

**Investigar:** revise no `PRODUTO.md` (seções 10 e 11) o Líder e os Agentes, e os quatro documentos markdown de cada um.

**Implementar:** endpoints e telas para criar, listar, editar e remover agentes dentro de um time. A tela de edição de um agente permite escrever os quatro markdowns (`agent.md`, `skill.md`, `tools.md`, `soul.md`), definir o papel (Líder ou Agente) e escolher o modelo de IA. Respeite a regra de no máximo um Líder por time.

**Verificar:** o maestro cria um Líder e dois Agentes num time, preenche os markdowns de cada um, e tudo é salvo e relido corretamente.

### Definition of Done — Fase 2

- [ ] Verificações automáticas das duas partes passam
- [ ] Criar/listar/editar/remover Organizações funciona pela tela
- [ ] Criar/listar/editar/remover Times funciona pela tela
- [ ] Criar/listar/editar/remover Agentes funciona, com os quatro markdowns
- [ ] Regra de um Líder por time respeitada
- [ ] Maestro confirmou o fluxo completo clicando nas telas
- [ ] **Commit + push:** `feat: gestão de organizações, times e agentes`

---

## FASE 3 — Instrumentos e o cinto

**Objetivo:** o maestro consegue criar Instrumentos num time e vinculá-los ao cinto dos agentes. Nesta fase, foca-se em **um ou dois tipos de instrumento** que provem o encaixe — os demais entram depois, no mesmo encaixe.

### Tarefa 3.1 — Gerir instrumentos

**Investigar:** revise o `PRODUTO.md`, seção 13 (o cinto de instrumentos). Defina como a configuração de um instrumento é representada de forma flexível (cada tipo tem campos diferentes).

**Implementar:** endpoints e tela para criar, listar, editar e remover instrumentos num time.

**Verificar:** o maestro cria um instrumento; ele é salvo com sua configuração.

### Tarefa 3.2 — O encaixe de instrumentos

**Investigar:** este é o ponto-chave da fase. Defina como o cérebro disponibiliza um instrumento para um agente usar durante a orquestração — o "encaixe" padrão pelo qual qualquer tipo de instrumento se conecta.

**Implementar:** o mecanismo de encaixe, mais o vínculo (tela e endpoints) que pendura instrumentos no cinto de um agente.

**Verificar:** o maestro vincula um instrumento ao cinto de um agente; o vínculo é salvo e relido.

### Tarefa 3.3 — O primeiro tipo de instrumento real

**Investigar:** escolha, com o maestro, um primeiro tipo de instrumento concreto para implementar de verdade (recomendação: um instrumento simples e verificável, como busca web ou uma chamada de API de teste). Leia a documentação necessária.

**Implementar:** o primeiro tipo de instrumento funcionando de verdade, dentro do encaixe.

**Verificar:** acionado isoladamente, o instrumento executa e devolve um resultado real.

### Definition of Done — Fase 3

- [ ] Verificações automáticas passam
- [ ] Criar/listar/editar/remover Instrumentos funciona pela tela
- [ ] O encaixe de instrumentos está definido e funciona
- [ ] Vincular instrumento ao cinto de um agente funciona
- [ ] Um tipo de instrumento real executa e devolve resultado
- [ ] **Commit + push:** `feat: instrumentos e o cinto`

---

## FASE 4 — A orquestração (o coração do core)

**Objetivo:** a peça central do Batuta. O maestro desenha uma automação — o gatilho e a cadeia de agentes — dispara, e a orquestração executa: cada agente recebe a entrada, raciocina com sua documentação e seus instrumentos, e passa o resultado adiante, até a resposta final. Construída sobre o LangGraph.

Esta é a fase mais difícil do projeto. Vá devagar, tarefa por tarefa, verificando cada uma.

### Tarefa 4.1 — Chamar uma LLM

**Investigar:** leia a documentação do LangGraph e do provedor de IA sobre fazer uma chamada simples a um modelo, usando a chave do arquivo de segredos.

**Implementar:** a capacidade do cérebro de chamar uma LLM — receber um texto, mandar ao modelo, devolver a resposta.

**Verificar:** uma chamada de teste a uma LLM devolve uma resposta real.

### Tarefa 4.2 — Um agente sozinho executa

**Investigar:** defina como a documentação de um agente (`agent.md`, `skill.md`, `tools.md`, `soul.md`) é transformada na instrução que vai à LLM, e como os instrumentos do cinto são oferecidos ao agente.

**Implementar:** a execução de um único agente — ele recebe uma entrada, raciocina com base na sua documentação, pode usar um instrumento do cinto, e produz uma saída.

**Verificar:** o maestro dispara um agente isolado com uma entrada e vê a saída coerente; se o agente usou um instrumento, isso é visível.

### Tarefa 4.3 — A cadeia: encadear agentes com o LangGraph

**Investigar:** leia a documentação do LangGraph sobre encadeamento e estado. Defina como a cadeia de uma automação vira um grafo do LangGraph, e como o resultado de um agente vira a entrada do próximo.

**Implementar:** a orquestração encadeada — uma automação com vários agentes em sequência, cada um processando e passando adiante, sobre o LangGraph.

**Verificar:** o maestro dispara uma automação de três agentes encadeados e a resposta final reflete a passagem pelos três.

### Tarefa 4.4 — Registrar cada passo

**Investigar:** revise as tabelas `execucoes` e `passos_execucao` da Fase 1.

**Implementar:** a cada execução de uma automação, registrar a execução e cada passo — o que cada agente recebeu, produziu, e seu estado.

**Verificar:** após uma execução, os registros de execução e de passos estão completos e corretos no banco.

### Tarefa 4.5 — A tela de inspeção da orquestração

**Investigar:** esta tela é o que permite ao maestro testar exaustivamente. Defina como mostrar uma execução passo a passo.

**Implementar:** uma tela crua que mostra, para uma execução, cada passo da cadeia: qual agente, o que recebeu, o que produziu, o estado, quanto demorou. Crua na aparência, completa no conteúdo.

**Verificar:** o maestro dispara uma automação e acompanha, pela tela, cada passo da orquestração.

### Tarefa 4.6 — A espera-por-humano

**Investigar:** esta é a peça mais delicada do Batuta (`PRODUTO.md`, seção 14). Leia com cuidado a documentação do LangGraph sobre human-in-the-loop. Defina como uma execução **pausa**, registra que está aguardando um humano, e **retoma de onde parou** quando a resposta chega.

**Implementar:** a espera-por-humano nas três formas do `PRODUTO.md` (pergunta pontual, portão de aprovação, confirmação de baixa confiança). Na Etapa 1, a resposta do humano pode ser dada por uma tela crua de testes.

**Verificar:** o maestro dispara uma automação que, no meio, pausa e pede uma informação; ele responde pela tela; a execução retoma e conclui. Teste também um caso em que a pausa dura mais tempo (responder depois) e confirme que a execução retoma corretamente.

### Tarefa 4.7 — Os gatilhos

**Investigar:** revise os três tipos de gatilho (`PRODUTO.md`, seção 12). Para o core, foque em disparar uma automação manualmente e por agendamento; o webhook de entrada pode ser incluído se for simples no encaixe atual.

**Implementar:** o disparo manual de uma automação (um botão na tela) e o disparo por agendamento.

**Verificar:** o maestro dispara uma automação pelo botão; cria um agendamento e confirma que dispara sozinho no momento certo.

### Definition of Done — Fase 4

- [ ] Verificações automáticas passam
- [ ] O cérebro chama uma LLM e recebe resposta
- [ ] Um agente isolado executa, usando instrumentos do cinto
- [ ] Uma cadeia de vários agentes executa encadeada, sobre o LangGraph
- [ ] Cada execução e cada passo são registrados
- [ ] A tela de inspeção mostra a orquestração passo a passo
- [ ] A espera-por-humano funciona nas três formas, inclusive com pausa longa
- [ ] Disparo manual e por agendamento funcionam
- [ ] **Commit + push:** `feat: orquestração de agentes`

---

## FASE 5 — Robustez do core

**Objetivo:** o core não só funciona no caminho feliz — ele se comporta bem quando algo dá errado. Implementa as decisões de design da Parte III do `PRODUTO.md` que pertencem ao core.

### Tarefa 5.1 — Falha de um instrumento

**Investigar:** revise o `PRODUTO.md`, seção 16. Defina o comportamento: quantas tentativas, e o que acontece quando um instrumento falha de vez.

**Implementar:** o tratamento de falha — uma execução cujo instrumento falha não "morre em silêncio"; ela tenta novamente conforme definido e, se desistir, fica num estado de falha claro e visível.

**Verificar:** o maestro força uma falha (ex.: um instrumento de API apontando para um endereço inválido) e vê a execução tratar a falha de forma visível e correta.

### Tarefa 5.2 — Feedback de progresso

**Investigar:** revise o `PRODUTO.md`, seção 17.

**Implementar:** a tela de inspeção mostra o progresso de uma execução em andamento — qual passo está rodando agora — sem o maestro precisar recarregar.

**Verificar:** durante uma execução longa, o maestro vê o progresso avançar passo a passo.

### Tarefa 5.3 — Volume e fila

**Investigar:** revise o `PRODUTO.md`, seção 18. Defina como várias execuções disparadas ao mesmo tempo são organizadas.

**Implementar:** o mecanismo que dá conta de várias execuções simultâneas sem perder nenhuma.

**Verificar:** o maestro dispara várias automações quase ao mesmo tempo e todas são processadas e concluídas corretamente.

### Tarefa 5.4 — Medição de uso

**Investigar:** revise o `PRODUTO.md`, seção 25. A medição é informativa.

**Implementar:** o registro, a cada chamada de LLM e de instrumento, do uso (tokens, modelo) na execução; e uma exibição crua desse uso com custo aproximado.

**Verificar:** após algumas execuções, o maestro vê o uso registrado por execução, com custo estimado.

### Definition of Done — Fase 5

- [ ] Verificações automáticas passam
- [ ] Falha de instrumento é tratada e fica visível, nunca silenciosa
- [ ] O progresso de uma execução é visível em tempo real
- [ ] Várias execuções simultâneas são processadas sem perda
- [ ] O uso (tokens, custo aproximado) é registrado e exibido
- [ ] **Commit + push:** `feat: robustez do core`

---

## PORTÃO DE VALIDAÇÃO DO CORE

**Este é o portão entre a Etapa 1 e a Etapa 2. A Etapa 2 está bloqueada até que o maestro o abra.**

Antes de qualquer tarefa da Etapa 2, o maestro testa o core exaustivamente. Roteiro mínimo de validação, todo feito pelas telas:

- [ ] Criar uma Organização
- [ ] Criar dois Times nela
- [ ] Criar, num time, um Líder e vários Agentes, com a documentação de cada um
- [ ] Criar Instrumentos e vinculá-los aos cintos dos agentes
- [ ] Desenhar uma automação curta (3 passos) e executá-la, acompanhando passo a passo
- [ ] Desenhar uma automação longa (vários passos) e executá-la
- [ ] Executar uma automação que pausa para esperar um humano, responder, e vê-la concluir
- [ ] Responder uma espera-por-humano só depois de um tempo, e confirmar que retoma
- [ ] Forçar uma falha de instrumento e ver o tratamento
- [ ] Disparar várias execuções ao mesmo tempo
- [ ] Conferir a medição de uso

**O maestro, e somente o maestro, declara o core validado.** Enquanto não declarar, o trabalho continua na Etapa 1, corrigindo e refinando. Nenhuma tarefa da Etapa 2 começa antes dessa declaração.

---

# ETAPA 2 — O ENTORNO

**Esta etapa só começa após o maestro declarar o core validado no Portão acima.**

A Etapa 2 transforma o core provado num produto completo. As fases abaixo são o esqueleto — cada uma será detalhada no nível das fases da Etapa 1 **quando a Etapa 2 for autorizada**, e não antes. Detalhá-las agora seria planejar sobre um core ainda não validado.

## FASE 6 — Identidade e acesso
Login e cadastro reais (Supabase Auth), substituindo o usuário fixo de testes. Papéis e permissões dentro de organizações e times (`PRODUTO.md`, seção 28). O ponto isolado criado na Tarefa 1.3 é trocado aqui.

## FASE 7 — Identidade visual
Aplicar o `DESIGN-SYSTEM.md` — cores, tipografia, logo, tom de voz — sobre as telas cruas do core. As telas deixam de ser cruas e passam a ser o Batuta.

## FASE 8 — Cofre de segredos e mais instrumentos
O cofre de chaves dos clientes (`PRODUTO.md`, seção 26). Os demais tipos de instrumento do `PRODUTO.md`, seção 13, entrando no encaixe já provado na Fase 3.

## FASE 9 — Canais e gatilhos completos
O canal de WhatsApp e o webhook de entrada completos, ligados ao Líder, conforme o `PRODUTO.md`.

## FASE 10 — Cobrança e administração
Planos da plataforma, mensalidade via cobrança recorrente, billing, inadimplência (`PRODUTO.md`, seções 24, 27, 29, 30).

## FASE 11 — Painel do operador e fechamento
O painel do operador (`PRODUTO.md`, seção 32), auditoria, onboarding e suporte, termos legais e a camada de LGPD (`PRODUTO.md`, seções 23, 31, 33, 34).

## FASE 12 — Implantação em produção
Publicação no Railway, domínio, e o teste de ponta a ponta do produto completo.

---

# Encerramento

Quando a Etapa 2 for autorizada, este documento será estendido — cada fase de 6 a 12 ganhará suas tarefas detalhadas no formato investigar/implementar/verificar, com seu Definition of Done. Até lá, o foco é um só: **o core, provado e validado.**
