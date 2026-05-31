# Batuta — Plano de Implementação

Este é o roteiro de construção do Batuta.

**Antes de usar este documento, leia o `PRODUTO.md` e o `CLAUDE.md` por completo.** Toda tarefa aqui é executada seguindo o **protocolo de execução de 6 passos** e a **lei do pare no primeiro erro** do `CLAUDE.md`. Este plano diz *o que* fazer; o `CLAUDE.md` diz *como*.

## Ambiente fixado (Fase 0, 2026-05-28)

Fatos verificados na máquina — não alterar sem re-verificar:

| Ferramenta | Versão |
|---|---|
| Python (sistema) | 3.14.5 |
| Python (projeto, via uv) | 3.13.13 |
| Gerenciador Python | uv 0.11.16 |
| Node.js | 24.15.0 |
| npm | 11.14.1 |
| git | 2.54.0 |
| FastAPI | 0.136.3 |
| uvicorn | 0.48.0 |
| SQLAlchemy | 2.0.50 |
| psycopg | 3.3.4 |
| Alembic | 1.18.4 |
| Next.js | 16.2.6 |
| React | 19.2.4 |

Repositório: `github.com/ti927/batuta`, branch `main`. Estrutura: `cerebro/` (Python) + `interface/` (Next.js). Banco: Supabase `lxprnyommztfgcvcjrzf`, conexão direta (IPv6 disponível).

---

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

### Definition of Done — Fase 0 ✅ (concluída 2026-05-28, commit `97ca6fb`)

- [x] Versões de Python, Node.js e git verificadas e registradas
- [x] Repositório clonado, fora de pasta de nuvem (`c:\dev\batuta`, branch `main`)
- [x] Estrutura de duas partes (cérebro / interface) criada
- [x] Cérebro FastAPI responde no endpoint de saúde — `HTTP 200 {"mensagem":"Batuta cérebro no ar"}`
- [x] Interface Next.js abre no navegador — confirmado pelo maestro
- [x] A interface exibe uma mensagem vinda do cérebro (as duas partes se falam) — confirmado pelo maestro
- [x] `.claude/settings.json` criado e funcionando
- [x] Contas Supabase e Railway criadas; arquivo de segredos preenchido e fora do git
- [x] **Commit + push:** `chore: fundação do ambiente do Batuta`

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

### Definition of Done — Fase 1 ✅ (concluída 2026-05-28, commit `c9b7c9f`)

- [x] Cérebro conecta ao banco do Supabase sem erro — `PostgreSQL 17.6` via conexão direta
- [x] Todas as tabelas do core criadas e visíveis no Supabase — 9 tabelas + `alembic_version`
- [x] Relações entre tabelas corretas — 10 FKs, cascade e SET NULL conforme especificação
- [x] Usuário fixo de testes criado e reconhecido pelo cérebro — `00000000-0000-0000-0000-000000000001`
- [x] **Commit + push:** `feat: modelo de dados do core`

**Decisões técnicas desta fase:**
- Gerenciador de migrations: **Alembic** (escolha do maestro) com autogenerate a partir dos modelos SQLAlchemy
- Conexão: por componentes (não URL crua) para lidar com caracteres especiais na senha (`$ * ,`)
- Índice parcial `uq_um_lider_por_time` garante no banco a regra de "no máximo um Líder por time"
- `passos_execucao.agente_id` usa `SET NULL` (não CASCADE) para preservar histórico de auditoria

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

### Definition of Done — Fase 2 ✅ (concluída 2026-05-29, commit `f1aa462`)

- [x] Verificações automáticas das duas partes passam — `tsc` e `eslint` da interface verdes; CRUD do cérebro exercitado por chamadas reais
- [x] Criar/listar/editar/remover Organizações funciona pela tela
- [x] Criar/listar/editar/remover Times funciona pela tela
- [x] Criar/listar/editar/remover Agentes funciona, com os quatro markdowns
- [x] Regra de um Líder por time respeitada — checagem prévia devolve 409 com mensagem clara; índice parcial do banco como backstop
- [x] Maestro confirmou o fluxo completo clicando nas telas
- [x] **Commit + push:** `feat: gestão de organizações, times e agentes`

**Decisões técnicas desta fase:**
- Estrutura do cérebro: `sessao.py` (sessão por requisição), `esquemas.py` (Pydantic v2) e pacote `rotas/` por recurso
- Isolamento por dono em toda consulta, via `usuario_fixo` — ponto único a trocar na Etapa 2
- Interface: padrão Server Component (busca) + ilha cliente (mutação) + `router.refresh()`, porque o Next 16 barra `useEffect`+`fetch` no lint
- Cliente único `lib/api.ts` centraliza o acesso ao cérebro e traduz o `detail` do FastAPI em mensagem

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

### Definition of Done — Fase 3 ✅ (concluída 2026-05-29, commit `9a06c49`)

- [x] Verificações automáticas passam — `tsc`/`eslint` verdes; CRUD, cinto e acionamento exercitados por chamadas reais
- [x] Criar/listar/editar/remover Instrumentos funciona pela tela
- [x] O encaixe de instrumentos está definido e funciona — registro de tipos com contrato uniforme (`instrumentos/base.py`)
- [x] Vincular instrumento ao cinto de um agente funciona
- [x] Um tipo de instrumento real executa e devolve resultado — Chamar API REST, status 200 + JSON real
- [x] **Commit + push:** `feat: instrumentos e o cinto`

**Decisões técnicas desta fase:**
- O encaixe é um registro (`instrumentos/base.py`): cada tipo é subclasse de `TipoInstrumento` declarando `Config`, `Args`, `executar()` e `definicao_para_ia()` (formato de ferramenta para a LLM, que a Fase 4 consumirá)
- Configuração validada contra o `Config` do tipo na criação/edição — é o que mantém o JSONB flexível sem virar caos
- Primeiro tipo real: `chamar_api_rest` via `httpx` (dependência nova)
- Endpoint `/instrumentos/{id}/acionar` aciona isolado pelo encaixe — base do que a Fase 4 fará na orquestração
- Helpers de posse centralizados em `rotas/_comum.py`

---

## FASE 4 — A orquestração (o coração do core)

**Objetivo:** a peça central do Batuta. O maestro desenha uma automação — o gatilho e a cadeia de agentes — dispara, e a orquestração executa: cada agente recebe a entrada, raciocina com sua documentação e seus instrumentos, e passa o resultado adiante, até a resposta final. Construída sobre o LangGraph.

Esta é a fase mais difícil do projeto. Vá devagar, tarefa por tarefa, verificando cada uma.

> **Progresso (sessão de 2026-05-30) — Fase 4 COMPLETA (4.1–4.7 feitas).**
> A 4.7 (gatilhos) foi implementada e verificada de ponta a ponta pelo Claude
> (manual, agendamento/CRON disparando sozinho às 09:58 BR, e webhook de
> entrada com guarda 409). Falta só o **click-test do maestro na tela** do novo
> construtor de gatilho e o **push** para fechar a fase.
>
> Feito e **validado pelo maestro clicando**:
> - **4.1** Chamar LLM — `orquestracao/llm.py` (langchain-anthropic; chave do `.env`). Commit `8fe99e3`.
> - **4.2** Um agente sozinho — `orquestracao/agente.py` (markdowns→prompt; cinto→ferramentas; `create_react_agent`). Endpoint `POST /agentes/{id}/executar`. Commit `8fe99e3`.
> - **4.3** Cadeia com **bifurcação** — `orquestracao/cadeia.py` (grafo; roteamento por LLM estruturado; loops com guarda). Commit `7d4f180`. Plano corrigido em `58456a4`.
> - **4.4** Registrar cada passo — disparo grava `execucoes`/`passos_execucao`. Commit `1b8c794`.
> - **4.5** Tela de inspeção — `/automacoes/[id]` mostra passos. Commit `1b8c794`.
> - **Construtor de automação** (lacuna do plano, suprida) — `/times/[id]/automacoes` monta o grafo. Gatilho de teste `tipo_gatilho="manual"`. Commit `1b8c794`.
> - **4.6** Espera-por-humano — agente marcado `pausa_humano` pausa (estado `aguardando_humano` salvo no banco, sobrevive a reinícios); `POST /execucoes/{id}/responder` retoma com a resposta. Interruptor no construtor + caixa de resposta na inspeção. Commits `4cf30f8` e o fix `agente sem saída sempre pausa`. **Evoluído na validação (`941ee8e`) para o portão de aprovação do §14: a resposta do humano escolhe a saída (ver o bloco "Validação EM ANDAMENTO" no Portão).**
>
> **4.7 Gatilhos (sessão 2026-05-30):** três tipos no produto, todos no core.
> - **Manual** (botão de teste) — já existia; o disparo foi refatorado para
>   `orquestracao/disparo.py` (`executar_automacao`), reusado por todos os gatilhos.
> - **Agendamento (CRON)** — `agendador.py` (APScheduler 3.x, `BackgroundScheduler`,
>   fuso America/Sao_Paulo). Relógio em memória reconstruído do banco no startup
>   (lifespan do FastAPI) e re-sincronizado no CRUD de automações. Formulário guiado
>   na tela (frequência diária/semanal/mensal + horário), sem jargão cron. Só dispara
>   se `ativa=true`.
> - **Webhook de entrada** — `rotas/webhooks.py`: `POST /webhooks/automacoes/{id}`,
>   público, dispara se gatilho é `webhook` e `ativa`; corpo vira a entrada.
> - O interruptor `ativa` liga/desliga gatilhos automáticos; o botão manual roda
>   sempre (é a forma de testar qualquer fluxo na Etapa 1).
>
> **Decisão de produto registrada:** a "pausa para humano" é por **interruptor por agente** (não um agente fixo), respondida na tela no core; o canal WhatsApp (via Líder, §10) fica para a Etapa 2. O comportamento do agente vem 100% dos markdowns (sem preâmbulo escondido).
>
> **Para retomar:** subir o cérebro (`uv run uvicorn main:app --port 8000` em `cerebro/`, com `uv` no PATH) e a interface (`npm run dev` em `interface/`). A `ANTHROPIC_API_KEY` já está no `cerebro/.env` (fora do git).

### Tarefa 4.1 — Chamar uma LLM

**Investigar:** leia a documentação do LangGraph e do provedor de IA sobre fazer uma chamada simples a um modelo, usando a chave do arquivo de segredos.

**Implementar:** a capacidade do cérebro de chamar uma LLM — receber um texto, mandar ao modelo, devolver a resposta.

**Verificar:** uma chamada de teste a uma LLM devolve uma resposta real.

### Tarefa 4.2 — Um agente sozinho executa

**Investigar:** defina como a documentação de um agente (`agent.md`, `skill.md`, `tools.md`, `soul.md`) é transformada na instrução que vai à LLM, e como os instrumentos do cinto são oferecidos ao agente.

**Implementar:** a execução de um único agente — ele recebe uma entrada, raciocina com base na sua documentação, pode usar um instrumento do cinto, e produz uma saída.

**Verificar:** o maestro dispara um agente isolado com uma entrada e vê a saída coerente; se o agente usou um instrumento, isso é visível.

### Tarefa 4.3 — A cadeia: encadear agentes com bifurcação (LangGraph)

> **Correção (2026-05-29, decisão do maestro):** a cadeia **não é linear** — é um
> **grafo de caminhos com bifurcação**, como o `PRODUTO.md` §14 ("Bifurcação por
> intenção") e o cenário 6 exigem. Cada agente, ao terminar, **escolhe uma de várias
> saídas**, e cada saída leva a um destino: outro agente (inclusive um **anterior** —
> loops permitidos) ou o fim (entregar ao usuário). "Encadeamento fixo" no produto
> significa que **o humano desenha o caminho** (a IA não improvisa a topologia), não
> "linha reta". O `automacoes.cadeia` (JSONB) guarda esse grafo — sem migration.

**Investigar:** leia a documentação do LangGraph sobre estado e **arestas condicionais**. Defina o formato do grafo em `automacoes.cadeia` (nós = agentes; cada nó com suas saídas rotuladas → destino), como o resultado de um agente vira a entrada do próximo, e como se escolhe a saída quando há mais de uma.

**Implementar:** a orquestração com bifurcação — uma automação cujos agentes formam um grafo; cada agente processa, escolhe uma saída e passa adiante; loops permitidos, com guarda de máximo de passos contra laço infinito.

**Verificar:** o maestro dispara uma automação com bifurcação (um agente classificador que manda a tarefa por um de dois caminhos) e a resposta final reflete o caminho correto; testar também os dois ramos.

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

- [x] Verificações automáticas passam
- [x] O cérebro chama uma LLM e recebe resposta
- [x] Um agente isolado executa, usando instrumentos do cinto
- [x] Uma cadeia de vários agentes executa encadeada, sobre o LangGraph
- [x] Cada execução e cada passo são registrados
- [x] A tela de inspeção mostra a orquestração passo a passo
- [x] A espera-por-humano funciona nas três formas, inclusive com pausa longa
- [x] Disparo manual e por agendamento funcionam (e webhook de entrada)
- [ ] **Commit + push:** `feat: orquestração de agentes` (push pende confirmação do maestro)

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

### Tarefa 5.5 — Gestão de execuções

> **Origem (2026-05-30):** lacuna levantada pelo maestro ao testar o agendamento
> (Tarefa 4.7). Hoje as execuções só aparecem listadas por automação e o único
> controle é responder uma pausa (4.6) e disparar manualmente (4.7). Falta a
> visão e o controle operacional de todas elas.

**Investigar:** revise os estados de `execucoes` (`aguardando`, `em_andamento`,
`aguardando_humano`, `concluida`, `falhou`) e como uma execução em andamento ou
pausada pode ser interrompida com segurança (especialmente a integração com a
espera-por-humano e a futura fila da 5.3). Defina o que "cancelar" significa para
cada estado.

**Implementar:** uma visão consolidada de execuções (não só por automação) com
filtro por estado — ver de relance quais estão **paradas/aguardando humano**, em
andamento, concluídas ou falhas; e o controle sobre cada uma: **cancelar** uma em
andamento ou pausada (estado final claro), **deletar** o registro de uma execução,
**disparar/retomar** pela tela. Crua na aparência, completa no conteúdo.

**Verificar:** o maestro abre a visão de execuções, filtra as paradas, cancela
uma, deleta outra, e retoma uma terceira — cada ação reflete corretamente no
banco e na tela.

### Definition of Done — Fase 5

- [x] Verificações automáticas passam
- [x] Falha de instrumento é tratada e fica visível, nunca silenciosa
- [x] O progresso de uma execução é visível em tempo real
- [x] Várias execuções simultâneas são processadas sem perda
- [x] O uso (tokens, custo aproximado) é registrado e exibido
- [x] Gestão de execuções: listar/filtrar (inclusive as paradas), cancelar, deletar e retomar pela tela
- [x] **Commit + push:** `feat: robustez do core` (push `05f2032..6124ba9` em 2026-05-30)

---

## FASE 5.6 — Mais instrumentos do core (pré-portão)

> **Origem (2026-05-30):** o maestro observou, com razão, que validar o core
> "exaustivamente" com **um só** instrumento (REST) não exercita o **cinto**, que
> é conceito central (PRODUTO §13). O encaixe (Fase 3) já está provado, então cada
> instrumento novo é "mais um plugue". O maestro escolheu adicionar quatro antes
> do portão. Os demais do §13 (SQL, planilhas, multimídia "de entendimento",
> contas Google/MS via OAuth+cofre) seguem para a Etapa 2 (Fase 8).

Cada um entra no encaixe `instrumentos/base.py` (subclasse `TipoInstrumento` com
`Config`/`Args`/`executar`), com verificação real e acionamento isolado, e a tela
de configuração já existente.

- [x] **Webhook de saída** — POST a uma URL para avisar/acionar outro sistema. `instrumentos/webhook_saida.py`. Commit `6953c77`.
- [x] **Busca na web** — via Tavily; chave em `cerebro/.env` (`TAVILY_API_KEY`). `instrumentos/busca_web.py`, commit `ebb13ff`. Verificado: busca real devolveu resultados (título/link/trecho).
- [x] **Gerar PDF/documento** — `instrumentos/gerar_pdf.py` (fpdf2); arquivo servido localmente pelo cérebro em `/arquivos` (`arquivos.py` + StaticFiles), migra para Supabase Storage na Etapa 2. Commit `ebb13ff`.
- [→] **Conectar MCP** — **adiado para a Etapa 2 (Fase 8)** por decisão do maestro (2026-05-30): é o único que mexe no núcleo da orquestração (instrumento multi-ferramenta + assíncrono); não vale arriscar o motor às vésperas do portão.
- [x] **Commit + push:** instrumentos em `6953c77` e `ebb13ff`; frente fechada (3 feitos, MCP adiado).

---

## PORTÃO DE VALIDAÇÃO DO CORE

**Este é o portão entre a Etapa 1 e a Etapa 2. A Etapa 2 está bloqueada até que o maestro o abra.**

> **Validação EM ANDAMENTO (iniciada 2026-05-31).** O maestro está testando com um
> time real (news-to-insight → curator-lure-fit → lure-writer → Lure.publisher) e o
> teste já expôs correções de núcleo, todas implementadas, verificadas e enviadas:
> - **`fix d615376`** — teto de tokens de SAÍDA subiu de 2048 → **8192**
>   (`orquestracao/llm.py`): 2048 cortava saídas longas no meio (a tabela do curador
>   truncava; o escritor recebia o pacote pela metade).
> - **`feat 941ee8e` — Portão de aprovação (PRODUTO §14):** a forma "portão de
>   aprovação" da espera-por-humano não existia de fato. Antes, num nó com pausa, a
>   IA escolhia o ramo a partir da saída do próprio agente e a resposta do humano
>   só virava a entrada do ramo já escolhido. Agora o nó com pausa **não roteia**; a
>   **resposta do humano** escolhe a saída (no `responder`, um roteador casa
>   "aprovado"/"reprovado, mude X" com o `quando` de cada saída) e o próximo nó
>   recebe trabalho-pausado + decisão. Na tela, um botão por saída na pausa.
> - **Aprendizado de autoria (não é bug):** o comportamento do agente vem 100% do
>   markdown — o motor só monta o prompt dos 4 markdowns e passa a entrada como
>   mensagem do usuário (não há "insumo inicial" no código). Agente em cadeia
>   automática deve FAZER e entregar só o produto (não validar o colega nem pedir
>   confirmação); conhecimento citado ("biblioteca Lure") precisa ser materializado
>   no markdown ou via instrumento.
>
> **Sessão 2026-05-31 (cont.) — instrumento "Publicar no WordPress" + decisão de
> modelo. Commits LOCAIS, push pendente do OK do maestro:**
> - **`feat 0e3d3a2` + `feat ae7f50e` — instrumento `publicar_wordpress`**
>   (`cerebro/instrumentos/wordpress.py`, molde do `busca_web`): publica via
>   `/wp-json/wp/v2/posts` (Basic Auth). Credenciais no `cerebro/.env`
>   (`WORDPRESS_URL`, `WORDPRESS_USUARIO=lure_admin`, `WORDPRESS_APP_PASSWORD`) —
>   nunca no banco/interface (CLAUDE §8). Aceita título+conteúdo (IA), status e
>   **categorias** (config; nome→ID, não cria), **tags** (IA; nome→ID, cria se
>   faltar) e **resumo** (IA→excerpt). Validado lendo o post de volta (rascunho
>   com categoria, tags e excerpt gravados). Pendurado no cinto do `Lure.publisher`.
> - **Lição de diagnóstico:** WordPress recusava auth com erro idêntico para senha
>   certa/errada e usuário inexistente. Não era o servidor descartando o header
>   (hipótese inicial, errada) — era **usuário errado** (`lure_admin`, não `admin`).
>   Confirmar o `user_login` exato antes de culpar a infra.
> - **`fix 2a8c072`** — `busca_web` trunca a consulta em 400 caracteres (limite da
>   Tavily; HTTP 400 acima disso). Só apareceu quando um agente Sonnet de fato
>   aciona a busca (o Haiku narrava em vez de buscar).
> - **Decisão de modelo (do maestro):** `lure-writer` e `curator-lure-fit` passam a
>   rodar em **`claude-sonnet-4-6`** — em Haiku o escritor travava pedindo "o
>   pacote" mesmo com o pacote na frente, e os agentes narravam apesar do markdown
>   proibir. `news-to-insight` e `Lure.publisher` seguem Haiku. Os 4 markdowns foram
>   reescritos (claros/diretos, contratos de repasse encaixando, `soul.md`
>   preenchido) — essa mudança vive no banco, não no git.
> - **Dúvidas do maestro p/ Etapa 2:** segredos por-empresário → **cofre de segredos
>   por Organização** (Fase 8; só a senha de app é segredo, URL/usuário ficam na
>   config); mais campos do WordPress (SEO/palavra-chave) dependem de plugin
>   (Yoast/RankMath) via post meta — capítulo à parte, adiado.

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
- [ ] Listar as execuções, filtrar as paradas, e cancelar/deletar/retomar uma pela tela

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
O cofre de chaves dos clientes (`PRODUTO.md`, seção 26). Os demais tipos de instrumento do `PRODUTO.md`, seção 13, entrando no encaixe já provado na Fase 3 — incluindo o **Conectar MCP** (adiado da frente 5.6 por exigir instrumento multi-ferramenta + assíncrono no núcleo), além de SQL direto, planilhas, multimídia "de entendimento" e contas Google/Microsoft/Apple (OAuth + cofre).

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
