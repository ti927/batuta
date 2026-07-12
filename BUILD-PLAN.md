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
> **Decisão de produto registrada:** a "pausa para humano" é por **interruptor por agente** (não um agente fixo), respondida na tela no core; o canal WhatsApp (via Líder, §10) fica para a Etapa 2 — **formalizado na `FASE — Mensageria (WhatsApp)` no fim deste documento** (não estava em nenhuma fase concreta até 2026-06-09). O comportamento do agente vem 100% dos markdowns (sem preâmbulo escondido).
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

> **✅ PORTÃO ABERTO em 2026-06-04.** O maestro exercitou o roteiro de validação por inteiro (incluindo webhook de entrada+saída, falha de instrumento forçada, volume/fila com várias execuções simultâneas e espera-por-humano respondida com atraso) e **autorizou a Etapa 2**, agora guiada pelo `MIGRACAO.md`. A Etapa 1 (o core) está **encerrada e validada**.

**Este foi o portão entre a Etapa 1 e a Etapa 2.**

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

# ETAPA 2 — O ENTORNO (reorganizada pelo `MIGRACAO.md`)

O Batuta deixou de ser SaaS público e passou a ser **ferramenta interna da consultoria Lure**. A Etapa 2 foi **reorganizada pelo `MIGRACAO.md`** (jun/2026): caem planos/billing/inadimplência/onboarding público; entram a camada conversacional (IA criadora) e a IA companheira. O **núcleo de orquestração da Etapa 1 é intocável** — só se estende. Cada fase é detalhada no formato investigar/implementar/verificar à medida que é executada (MIGRACAO §4.3/§6.3). Trabalho na branch **`migracao-etapa-2`**.

## FASE 6 — Identidade e papéis  ✅ CONCLUÍDA (2026-06-04)

Trocar o usuário fixo por **login real (Supabase Auth)** e **três papéis** (admin/operador/observador), com convites, desativação de usuários e auditoria nominal. Referência completa: `MIGRACAO.md` §4.1/§5/§6.

**Decisões fixadas:** começar do zero (apaga dados, mantém estrutura; sem migração de histórico); 1º admin `luregpt@lureconsultoria.com.br`; "apagar = só admin". Supabase usa **JWKS/ES256** (validação local, sem segredo novo).

**Cérebro — ✅ feito e verificado (19 testes pytest verdes em `cerebro/testes/`):**
- **6.1/6.2** `auth_supabase.py` valida o token do Supabase via JWKS (pyjwt[crypto]). — `8f3dfc5`
- **6.3** Modelos + migration aditiva `cf6de832ad21`: `usuarios.auth_id`+`ativo`; tabelas `membros`/`convites`/`auditoria` (reversível; core intocado). — `85dd448`
- **6.4** `auth.py` (`usuario_atual`→401/403, `papel_na_org`, `exigir_papel`) + helpers `*_acessivel` em `_comum.py`. — `c8fae83`
- **6.5** Matriz de papéis em todas as rotas (menos webhooks); `usuario_fixo` aposentado; pytest introduzido. — `ae3989d`
- **6.6** `auditoria.py` + instrumentação (criar/remover org/time/agente/instrumento, markdown_alterado, portao.aprovado). — `9379345`
- **6.7** `rotas/membros.py` + `supabase_admin.py`: membros, papéis (guarda do último admin), convites (Supabase invite), `POST /convites/aceitar`, (des)ativação, `GET /eu`. — `3d76a27`
- **6.8** `scripts/bootstrap_admin.py` + `iniciar_do_zero.py`; admin ligado, banco zerado, `usuario_fixo.py` removido. — `1d55b02`

**Interface (Next 16) — ✅ feita e verificada (tsc/eslint verdes):**
- **I6.1/I6.2** Base `@supabase/ssr` (clientes navegador/servidor) + `proxy.ts` (no Next 16 substitui o `middleware.ts`) protegendo as rotas; tela `/login` e barra de sessão com Sair. — `d2e06bf`. Verificado pelo maestro (login/logout no navegador).
- **I6.3** Token encaminhado ao cérebro nos dois contextos: `lib/api.ts` (núcleo `requisitar` + `api` do navegador) e `lib/cerebro-servidor.ts` (`buscarCerebro`, server-only) nos 8 Server Components. — `72a4ccc`. Verificado: maestro criou orgs/times/agentes/instrumentos e fez logoff/login.
- **I6.4** Aceite de convite: `app/auth/confirm/route.ts` (verifyOtp do token do e-mail → sessão) + `app/convite` (define senha + `POST /convites/aceitar`). — `cadbeaa`. Verificado de ponta a ponta com link gerado sem e-mail (membro criado, convite "aceito").
- **I6.5** Telas de gestão (`/organizacoes/[id]/acesso`): membros (papel, remover, (des)ativar) e convites (convidar, revogar); gating por `GET /eu`. — `962b2ff`.
- **I6.6** UI ciente de papel em todas as telas (`lib/permissoes.ts`); cérebro ganhou `organizacao_id` aditivo na lista global de execuções. — `7b11d9c`.

**Envio de e-mail (resolvido 2026-06-04):** o e-mail de convite sai pelo **Resend** (SMTP `smtp.resend.com:587`, usuário `resend`, senha = API key; domínio verificado no Resend). O Gmail foi descartado (bloqueia SMTP a partir dos servidores do Supabase). O template "Invite user" do Supabase aponta o link para `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=invite&next=/convite` — sem isso, o link cai no `verify` padrão e não chega à tela de senha.

**Correção pós-conclusão (2026-06-04) — reconvite de quem já tem conta:** convidar um e-mail que **já tem conta no Supabase** (ex.: ex-membro removido) não enviava e-mail — o `POST /auth/v1/invite` só dispara e-mail ao criar conta nova; para conta existente devolve 422 e o cérebro engolia o erro. **Solução (escolha do maestro): "aviso dentro do Batuta"** — novo `GET /convites/pendentes` (autentica pelo token direto, não `usuario_atual`) + banner no **layout** (`interface/app/banner-convites.tsx` em `app/layout.tsx`, aparece em toda tela autenticada) que reusa `POST /convites/aceitar`; `criar_convite` passou a devolver `email_enviado` e a tela de acesso avisa o admin quando o e-mail não saiu. +3 testes pytest (22 verdes). Validado pelo maestro. Commits `993ed7c` e `eb0100b`.

### Definition of Done — Fase 6 ✅
- [x] Cérebro: login real + três papéis em todas as rotas + convites/desativação + auditoria — **19 testes verdes**.
- [x] Interface: login funcionando, token encaminhado, telas de gestão, UI por papel — **tsc/eslint verdes**.
- [x] Verificação pelas telas: maestro logou; CRUD via token; aceite de convite **ponta a ponta com e-mail real** (Resend); UI por papel (admin vê tudo, operador sem deletar/criar-time/gerir-acesso).
- [x] Envio de e-mail de convite funcionando (Resend).
- [x] `PRODUTO.md`/`BUILD-PLAN.md` atualizados; commit da branch. Push/merge em `main` com confirmação do maestro.

## FASE 7 — Cofre de chaves por projeto  🚧 EM ANDAMENTO (7.1–7.2 feitas)
Cofre criptografado; chave por **organização** + **chave-mãe da consultoria** + fallback; troca de chave (admin); **medição refinada por chave/IA**. As **três** IAs (executora/criadora/companheira) têm chaves **trocáveis** por escolha do admin; medição de tokens obrigatória em tudo quando se usa a chave da consultoria (MIGRACAO Viradas 4/5).

**Decisões fixadas com o maestro (2026-06-04):**
- A chave de IA vincula-se à **Organização** (o cliente); todos os times dela usam. `organizacao_id` nulo na `chaves_api` = **chave-mãe da consultoria** (fallback).
- A chave-mãe é gerida só por **"admins da consultoria"**, definidos por uma **lista de e-mails no `.env`** do cérebro (leve, seguro; pode evoluir depois).
- Os **três tipos de IA** (`tipo_ia`: executora/criadora/companheira) são modelados desde já; nesta fase só a **executora** é consumida pelo motor (criadora/companheira chegam nas Fases 9/10).
- Resolução da chave na execução: **chave da organização → chave-mãe da consultoria → `ANTHROPIC_API_KEY` legado do `.env`** (retrocompatibilidade; nada quebra antes de qualquer chave cadastrada).
- Provedor: campo `provedor` pronto (anthropic/openai/google…), mas só **Anthropic** implementado agora.

**Tarefas:**
- **7.1 — A tabela do cofre ✅** (`fd47141`): modelo `ChaveApi` + migration aditiva `73ecf4dbc909` (`chaves_api`: `organizacao_id` nulável, `tipo_ia`, `provedor`, `valor_cifrado`, `ultimos4`, `apelido`, `ativa`; índice único `(org,tipo,provedor)` com `NULLS NOT DISTINCT`). Verificado no Postgres real.
- **7.2 — Criptografia ✅** (`99a920f`): `cofre.py` (Fernet/AES+HMAC) `cifrar`/`decifrar`/`ultimos4`; chave-mestra `COFRE_CHAVE_MESTRA` no `.env` (gerada por `scripts/gerar_chave_mestra.py` sem expor o valor); `cryptography` vira dep direta. Verificado: segredo não vaza no token, roundtrip, adulteração detectada.
- **7.3 — Resolução com fallback + ligação no motor ✅** (`31d3659`): novo `chaves.py` resolve org → consultoria (chave-mãe, `organizacao_id` nulo) → `.env` legado. `orquestracao/llm.py` ganhou `usar_chave` (contextvar) e `construir_modelo` lê a chave do contexto; o grafo (cadeia/agente) ficou intocado. As três fronteiras — disparo da fila, retomada pós-pausa (`rotas/automacoes.py`), agente isolado (`rotas/execucao.py`) — resolvem e embrulham a chamada do motor. 10 testes novos (32 verdes). Cofre vazio = nada quebra (cai no `.env`).
- **7.4 — Endpoints + permissão ✅**: `rotas/chaves_api.py` — chaves da org (`GET/PUT/DELETE /organizacoes/{id}/chaves`, só **admin** da org) e chave-mãe (`GET/PUT/DELETE /chaves-consultoria`, só **admin da consultoria**). `PUT` faz upsert (cadastra/**troca** sem duplicar). `consultoria.py` define os admins da consultoria por `CONSULTORIA_ADMINS` no `.env` (fail-closed: vazio = ninguém). Provedor restrito a `anthropic` nesta fase (422 nos demais, evita chave morta). O valor nunca volta na leitura (`ChaveApiLer` só traz `ultimos4`+metadados). 11 testes novos (43 verdes).
- **7.5 — Tela de gestão de chaves ✅**: duas telas cruas compartilhando `components/gestao-chaves.tsx` (lista mascarada com `••••ultimos4` + cadastrar/trocar/remover; valor em campo `password`, nunca reexibido). Chaves da org em `/organizacoes/[id]/chaves` (só admin; link na tela do time). Chave-mãe em `/chaves-consultoria` (só admin da consultoria; link na lista de orgs). O cérebro ganhou `admin_consultoria` no `/eu` para a UI mostrar o link certo. tsc/eslint verdes; +1 teste do `/eu` (44 pytest verdes). Falta o click-test do maestro.
- **7.6 — Medição refinada por chave ✅**: a resolução passou a devolver a **origem** (`chaves.resolver_chave_e_origem_por_time`: cliente=`organizacao` / `consultoria` / `legado`); o registrador de passos (`disparo._fazer_registrador`) carimba a origem em cada entrada de `uso` (no disparo e na retomada). `precos.resumir_uso` ganhou `por_origem`. Novo endpoint `GET /uso/resumo` (agrega o consumo das execuções visíveis ao usuário, isolado por `membros`, filtro opcional por org). UI: a inspeção mostra "Por origem da chave" e a tela `/execucoes` ganhou painel "Uso por origem da chave" (consultoria × cliente). 6 testes novos (50 pytest verdes); tsc/eslint verdes.
- **7.7 — Auditoria de troca de chave ✅ (feita junto da 7.4)**: cada cadastro/troca/remoção de chave (org e mãe) chama `auditoria.registrar` inline na rota — ações `chave.cadastrada`/`chave.trocada`/`chave.removida` e `chave_mae.*`, com `ultimos4` no detalhe (nunca o valor). Segue o padrão "auditoria desde o primeiro dia" (MIGRACAO §6.4), igual à Fase 6.

**DoD:** testes pytest verdes; chave cifrada nunca reexibida; agente executa com a chave certa e o fallback; só admin troca; medição separa por chave; auditoria registra; tsc/eslint verdes; commit + push.

> **Fase 7 COMPLETA (2026-06-06):** 7.1–7.7 todas ✅ (50 pytest + tsc/eslint verdes). Falta só o **merge em `main` + push** da branch `migracao-etapa-2` (pende confirmação do maestro). Próximo: Fase 7-A.

## FASE 7-A — Múltiplos provedores de IA  ✅ CONCLUÍDA (2026-06-06)

> **Origem (2026-06-06, decisão do maestro):** o motor hoje só constrói `ChatAnthropic` — um agente com `modelo_ia` de outro provedor falharia. O `PRODUTO.md §11` ("cada Agente pode usar uma LLM diferente") e o `MIGRACAO Virada 5` (OpenAI, Google, etc.) exigem multi-provedor. A `chaves_api` já tem o campo `provedor`, mas a resolução e o endpoint estavam fixos em `anthropic`. Esta fase é dedicada, **logo após a Fase 7** (antes da identidade visual). Lembrete: `executora/criadora/companheira` são *papéis* de IA, não modelos — o modelo é o `modelo_ia` do agente.

> **FEITO (2026-06-06):** novo `cerebro/orquestracao/modelos_ia.py` (registro modelo→provedor, com inferência por prefixo). `orquestracao/llm.py`: o contextvar virou um MAPA `{provedor: chave}` (`usar_chaves`) e `construir_modelo` despacha por provedor — `ChatAnthropic`/`ChatOpenAI`/`ChatGoogleGenerativeAI` (imports preguiçosos), Anthropic com fallback `.env`, OpenAI/Google exigem chave do cofre (erro claro se faltar). `chaves.resolver_chaves_por_time` resolve a chave de cada provedor + origens por provedor (a medição 7.6 agora carimba a origem pelo provedor do modelo de cada passo). Fronteiras (disparo/retomada/agente isolado) e `_fazer_registrador` ajustados. Endpoint `chaves_api`: `PROVEDORES_SUPORTADOS={anthropic,openai,google}`. Deps `langchain-openai`+`langchain-google-genai`. UI: `lib/modelos.ts` (registro espelhado), seletor de modelo do agente agrupado por provedor (`<optgroup>`), seleção de provedor ao cadastrar chave. **55 testes pytest + tsc/eslint verdes** (5 novos: registro, build OpenAI, falha sem chave, mapa por provedor). Verificação de chamada LIVE a OpenAI/Google depende de chave real do maestro.

**Objetivo:** um agente roda em modelo não-Anthropic (OpenAI, Google) com a chave do provedor certo, do cofre, mantendo o fallback consultoria → `.env` da 7.3.

**Abordagem (estende o núcleo, não refatora):**
- **Registro de modelos** — novo `cerebro/orquestracao/modelos_ia.py`: mapa único `modelo → provedor` (fonte da verdade), espelhado em TS na interface. Modelo desconhecido → erro claro.
- **Resolução por provedor** — a fronteira resolve, de uma vez, a chave de cada provedor da org (`dict {provedor: chave}`) no contexto; o `contextvar` da 7.3 (`usar_chave`) vira `usar_chaves(mapa)`. Necessário porque agentes da mesma cadeia podem usar provedores diferentes; `cadeia.py`/`agente.py` ficam intocados.
- **Despacho no motor** — `orquestracao/llm.py` `construir_modelo` deriva o provedor pelo registro e constrói `ChatAnthropic`/`ChatOpenAI`/`ChatGoogleGenerativeAI`, pegando `mapa[provedor]` (fallback `.env` p/ anthropic).
- **Dependências** — `langchain-openai`, `langchain-google-genai` no `pyproject.toml`.
- **Endpoint** — `rotas/chaves_api.py`: expandir `PROVEDORES_SUPORTADOS` para `{anthropic, openai, google}` (upsert já é por `provedor`).
- **Interface** — dropdown de modelo (`interface/app/times/[id]/agentes-cliente.tsx`) agrupado por provedor; `components/gestao-chaves.tsx` ganha seleção de provedor.

**DoD:** agente em OpenAI/Google executa de fato com a chave certa; resolução por provedor com fallback; endpoint aceita os novos provedores; tela escolhe provedor+modelo; pytest + tsc/eslint verdes; commit + push.

## FASE 7-B — Cofre de segredos de instrumentos  ✅ CONCLUÍDA (2026-06-06)

> **Origem (2026-06-06, decisão do maestro):** o `PRODUTO.md §26` prevê as credenciais de instrumentos no mesmo cofre criptografado. Hoje WordPress/Tavily leem do `.env` (paliativo por-cérebro) e **REST/webhook guardam o token em texto plano** na config JSONB do banco — viola o §26. Fase dedicada, **antes da identidade visual**. (Recupera o slot que a renumeração do MIGRACAO sobrescreveu.)

> **FEITO (2026-06-06):** mecanismo geral `campos_secretos` no encaixe (`instrumentos/base.py`) + `preparar_config` (separa config pública × segredos). Nova tabela `segredos_instrumento` (migration aditiva `b26cc22ca49a`, aplicada) + módulo `cerebro/segredos_instrumento.py` (reusa `cofre.py`: cifrar/decifrar/ultimos4; upsert que preserva ao omitir; `anexar_aos_instrumentos` injeta os segredos decifrados num atributo transitório). Instrumentos migrados: WordPress (`site_url`/`usuario` na config + `senha_app` secreto), busca web (`chave_api` secreto), REST e webhook (`token_bearer` secreto → `Authorization: Bearer`) — todos com **`.env` como fallback legado** (não quebra os já configurados). Injeção na execução: `cadeia._carregar_cinto` + `agente._ferramenta_de_instrumento` mesclam os segredos só em memória; rota `acionar` idem; rota CRUD separa/cifra os segredos e audita (`instrumento.segredo_alterado`); leitura devolve só `ultimos4`, nunca o valor. UI: aviso dos campos secretos + o que já está guardado (mascarado). **62 testes pytest + tsc/eslint verdes** (8 novos). Atende a parte de credenciais de instrumentos do `PRODUTO §26`.

**Objetivo:** credenciais de instrumento guardadas cifradas por organização, nunca em texto plano, injetadas só na execução; reusa a cripto do `cofre.py`.

**Abordagem:**
- **Campos secretos no encaixe** — cada `TipoInstrumento` (`instrumentos/base.py`) declara quais campos da `Config` são secretos; ao salvar, esses são cifrados e guardados fora da config em claro (URL/usuário/categorias seguem na config).
- **Armazenamento** — nova tabela `segredos_instrumento` (`instrumento_id`, `campo`, `valor_cifrado`, `ultimos4`) + migration aditiva; per-org por herança (instrumento → time → org); reusa `cofre.cifrar/decifrar/ultimos4`.
- **Injeção** — decifrar os segredos ao carregar o cinto (`orquestracao/cadeia.py` `_carregar_cinto`, que já tem a sessão), mesclando na `Config` antes do `executar`; laço react intocado.
- **Migrar paliativos** — `instrumentos/wordpress.py` e `busca_web.py` leem o segredo do cofre (com `.env` como fallback legado); `rest.py`/`webhook_saida.py` movem o token de `cabecalhos` para campo secreto.
- **Interface** — formulário de config de instrumento marca campos secretos como `password`, mostra `••••ultimos4`, nunca reexibe.
- **Auditoria** — registra troca/remoção de segredo de instrumento.

**DoD:** segredo salvo cifrado e nunca reexibido; instrumento executa com o segredo decifrado; nenhum segredo novo em texto plano no banco; `.env` como fallback legado; auditoria registra; pytest + tsc/eslint verdes; commit + push. Atende a parte de "credenciais de instrumentos" do `PRODUTO §26`.

## FASE 8 — Identidade visual  ✅ CONCLUÍDA (2026-06-06)
Aplicar o `DESIGN-SYSTEM.md` sobre as telas cruas do core.

> **Feito:** fundação (paleta Batuta + Inter/Bricolage), primitivos (Button DS, Input,
> Textarea, Select, Label, Card, Badge, Aviso, EstadoVazio), casca (header com logotipo),
> e varredura das 19 telas — zero cor crua, sentence case, só pesos 400/500 (Bricolage 600
> só no logotipo), ícones lucide, estados vazios e erros com ícone. Tema só claro (escuro
> pronto nos tokens). 8.9 (voz): estados vazios/erros/tipografia entregues; a reescrita de
> cópia para o "tom consumidor" do DS §12 NÃO foi feita por decisão do maestro (telas de
> operador usam vocab de produto). Mascote/favicon final pendem de arte (DS §13 TODO).
> Verificação: `tsc`+`eslint`+`next build` verdes a cada commit (8.1→8.8).
>
> **Pós-QA (2026-06-06):** durante o QA do maestro surgiram dois tropeços, ambos por **processo
> de longa duração servindo código velho** (não bug de código): (a) as fontes não pareciam mudar —
> dev server `next dev` em cache (resolvido reiniciando após limpar `interface/.next`); (b) clicar
> "Novo instrumento" quebrava (`Cannot read properties of undefined`) porque o **cérebro estava no
> ar desde antes da Fase 7-B** e devolvia tipos sem `campos_secretos` (resolvido reiniciando o
> uvicorn). Além do restart, blindou-se a tela com `?.`/`?? []` (commit `802d949`) para um campo
> ausente nunca derrubar a página. Lição: **reiniciar cérebro + dev server ao iniciar o QA de uma
> fase.**
>
> **Handoff de design recebido:** pasta `design_handoff_batuta_ai_first/` (na raiz, fora do git por
> ora) com mockups da visão AI-first (dashboard, criação, companheira, execução) e os **assets de
> marca que faltavam** (`mascote.png`, `mascote-completo.png`, `simbolo.png`, `logo-lockup.png`) +
> screenshots + README. Insumo para fechar o §13 do DS (mascote/favicon) e para a Fase 9.

> **Decisões do maestro (2026-06-06):** (1) **vocabulário de produto** mantido nas telas
> ("Agente/Instrumento/Automação"), NÃO a tradução "Assistente/Habilidade" do tom de voz do
> DS — estas são telas de operador, não do cliente final; (2) **só tema claro** agora (tokens
> do escuro ficam prontos no `globals.css`, sem botão de troca). Mascote, ilustrações de
> empty state e favicon final dependem de arte ainda não produzida (DS §13 TODO) — entrega-se
> só o logotipo tipográfico ("Batuta" em Bricolage) e um símbolo simples.

**Marca a aplicar:** Roxo Batuta `#6D4AFF` + off-white `#FAFAF7`; **Inter** (interface) +
**Bricolage Grotesque** (logotipo); sentence case; só pesos 400/500; ícones lucide; flat design.

**Sub-tarefas (cada uma: verificação `tsc`+`eslint` verde + commit):**
- **8.1 — Fundação de marca.** Paleta Batuta mapeada nos tokens do `globals.css` (claro + escuro
  pronto) + fontes Inter/Bricolage via `next/font` no `layout.tsx`. Vira a cara de quase tudo de
  uma vez (telas que já usam tokens semânticos `bg-background`/`bg-primary`/`border-border`).
- **8.2 — Primitivos.** `Button` no padrão DS (altura `h-10`, roxo, destrutivo cheio) + criar
  `Input`, `Card`, `Badge`, `Label`, `Select`, `Textarea`, `Dialog`/`AlertDialog`, Toast (`sonner`).
- **8.3 — Casca do app.** Header com logotipo "Batuta", fundo off-white, container centrado, respiro.
- **8.4–8.8 — Varredura das 19 telas.** Trocar as ~211 cores cruas (`zinc/blue/red/...`) por tokens
  + componentes, sentence case, ícones, estados vazios. Grupos: (a) login/convite, (b)
  organizações/acesso, (c) times/agentes, (d) instrumentos, (e) automações/execuções/chaves.
- **8.9 — Voz e microcópia.** Mensagens de erro empáticas e estados vazios conforme DS §12.

**DoD:** telas com a marca Batuta aplicada; nenhuma cor crua solta nas telas varridas; `tsc`+`eslint`
verdes; servidor de dev sobe; QA visual do maestro aprovado; commit + push.

## DESIGN — fonte da verdade das telas (handoff hi-fi)
A partir da Fase 8, o visual tem **duas fontes complementares**: `DESIGN-SYSTEM.md` (marca/tokens/voz)
e **`docs/design/`** (handoff hi-fi — ler o `README.md`), que traz as **telas desenhadas** e o
**shell de navegação em sidebar escura** (a casca definitiva; o header simples da Fase 8 evolui para
ela). **Antes de qualquer tela/layout/UX, ler os dois.** Os `.jsx`/`.html` do handoff são referência
de design, não código de produção — recriar com Next + Tailwind + shadcn/ui. Mapa tela→arquivo→fase:

| Tela | Arquivo no handoff | Onde entra |
|---|---|---|
| Shell sidebar (navegação) | `app-shell.jsx` (variação "Sidebar"; README §5) | Refino de casca (substitui o header da Fase 8); base das Fases 9/10 |
| Dashboard do time | `app-dashboard.jsx` (README §6.3) | Refino de tela |
| Inspeção de execução + espera-por-humano | `app-execution.jsx` (README §6.4) | Refino da tela crua da Etapa 1 |
| Card/Drawer de agente + RobotFace | `app-creation.jsx` (README §6.1, §6.5) | Refino + Fase 9 |
| Criação AI-first (IA criadora) | `app-creation.jsx` (README §6.2; roteiros §8; dados §9) | **Fase 9** |
| IA companheira + painel de memória | `app-companion.jsx` (README §6.6) | **Fase 10** |

Ordem de implementação sugerida no `docs/design/README.md` §13.

## FASE 9 — IA criadora (conversa eterna sobre o time real)  ✅ IMPLEMENTADA E VALIDADA AO VIVO (2026-06-07)
Uma IA, uma conversa que **nunca termina**: investiga, monta, ativa e mantém o time. A IA escreve no **time real** desde o começo; nada dispara até o consultor ATIVAR.
- **Spec visual/UX:** `docs/design/` — `app-creation.jsx` (tela dividida chat + canvas), README §6.2/§6.5.

> **Histórico:** a Fase 9 foi entregue primeiro em "modo rascunho + 3 modos (investigação/projeto/montagem) + Aprovar e criar time" (commits `cfc1dc4`/`00f77b5`, depois Opus + playbook). O maestro validou que o motor funcionava, mas **mudou o paradigma** (2026-06-07): some o rascunho, somem os 3 modos, some o ritual de aprovar. O que vale é o estado abaixo.

**Paradigma final (branch `migracao-etapa-2`, PR #1):**
- **A IA opera no time REAL** por uma porta única e validada — `cerebro/criacao/servicos.py` (criar/editar time, agente com líder único, instrumento com segredos no cofre, cinto, automação, ativar/desativar). As ferramentas (`criacao/ferramentas.py`) e as rotas REST escrevem pela mesma porta.
- **Segurança por ativação** (substitui o "modo rascunho", MIGRACAO §6.4 revisto): tudo é real mas DORME; a automação nasce inativa e nada roda até ATIVAR. **Parede de ativação** (`cerebro/portao_ativacao.py`): um agente com instrumento de **ação irreversível** (`acao_irreversivel` no tipo) só ativa se a cadeia tiver `pausa_humano` **no nó anterior** — senão o app recusa (422). Pegadinha corrigida: o motor lê `pausa_humano` no NÓ, não na saída.
- **Conversa**: `ConversaCriacao` perdeu `rascunho`/`modo`/`estado`, ganhou `time_id` (migração `a1b2c3d4e5f6` derruba as 3 colunas). `loop.py` roda o turno (`create_react_agent`) sobre a sessão e devolve a fotografia do time; `rotas/criacao.py` iniciar/listar/obter/mensagens (sem aprovar/descartar). **Pegadinha resolvida:** o LangGraph roda tool calls em paralelo (threads) — como agora escrevem no banco na mesma sessão, uma **trava por turno** serializa-as (`montar_ferramentas`), senão quebra com "Session is already flushing".
- **Prompt único** (`prompt.py`): duas lentes — **engenheiro de processos** (mapeia fluxo, gargalos, erros; nunca encerra com ponta solta) + **profissional do ofício** (marketing/secretária/tesoureiro). Investiga antes de propor; sinaliza quando dá para ativar; régua de markdowns (AGE/ENTREGA/REPASSE/MATERIALIZA).
- **Interface** (`interface/app/criar/`): chat + canvas desenhando o **time real** (fotografia a cada turno), botão **"Ativar o time"** (mostra os problemas da parede), aviso de segredos pendentes, link para a tela do time. Sem "Aprovar e criar"/materializada.
- **Removido:** `materializar.py`, `rascunho.py`, endpoint `aprovar`.
- **Verificação:** 125 testes pytest verdes (parede de ativação, serviços, ferramentas sobre o time real, persistência, prompt). `tsc` + `eslint` verdes. **Validado ao vivo pelo maestro.**
- **Follow-ups (não bloqueiam):** consolidar as rotas REST de CRUD na porta única de `servicos.py`; refino fino da conversa (ritmo, construir em passos menores).

## FASE 10 — IA companheira de projeto  ✅ CONCLUÍDA (2026-06-07)
A parte "conversa viva que continua sobre o projeto" **já estava pronta**: a IA criadora e a companheira viraram **uma só** conversa eterna (Fase 9). Consultar o estado do projeto via tool use também já existe (`ver_time` + fotografia do time). Faltava só a **memória de longo prazo**, agora entregue.
- **Escopo remanescente (entregue):** memória de longo prazo (fatos/decisões/preferências) com **isolamento estrito entre projetos**, e o painel "O que eu sei deste projeto".
- **Abordagem DESTILADA, não vetorial (decisão do maestro 2026-06-07):** a IA cura o que vale lembrar (ferramentas `lembrar`/`recordar`/`esquecer`) e o conjunto — dezenas de memórias por projeto, não milhares — é injetado no contexto do modelo a cada turno. ZERO infra nova: sem pgvector, sem chave de embeddings, sem provedor extra (a Anthropic não tem embeddings). Evolui para vetorial depois, se um projeto crescer demais.
  - **Cérebro:** tabela `memorias_projeto` (migração aditiva `c3d4e5f6a7b8`), serviço `criacao/memoria.py`, três ferramentas no encaixe da criadora, injeção no `prompt.py`, memória exposta em `ConversaCriacaoLer`/`RespostaTurno`. Isolamento preso à conversa (o fio do projeto) + `organizacao_id` como parede dura. **134 testes pytest verdes** (9 novos: gravar/listar/buscar/esquecer, isolamento entre projetos, injeção no prompt).
  - **Interface:** painel "O que eu sei deste projeto" no canvas da conversa (`app/criar/[id]`), atualiza a cada turno. `tsc`+`eslint` verdes.
- **Spec visual/UX:** `docs/design/` — `app-companion.jsx` (README §6.6).

## FASE adicional — MCP e instrumentos restantes  ✅ ESCOPO DESTA FASE CONCLUÍDO (2026-06-06)
Conectar MCP (adiado da frente 5.6) + demais instrumentos do `PRODUTO.md` §13, no encaixe já provado. Ordem da janela entre a Fase 7 e a Fase 8: **7-A → 7-B → esta → Fase 8 (visual)**. Os instrumentos novos já nascem usando o cofre de segredos da 7-B.

**Escopo desta fase (decisão do maestro 2026-06-06): MCP + Banco de dados direto (SQL) + Gerar imagem — TODOS FEITOS.** Contas Google/MS (OAuth) e multimídia "de entendimento" (ler imagem/PDF, transcrever áudio) ficam para **fases próprias** depois (OAuth é grande; multimídia é entrada multimodal, outro mecanismo). Ritmo seguido: MCP primeiro, sozinho; depois SQL; depois imagem.

- **MCP ✅** (commit na branch): novo `instrumentos/mcp.py` (`conectar_mcp`). O encaixe ganhou `expandir_ferramentas(config)` opcional (`base.py`): um instrumento MCP expõe VÁRIAS ferramentas; o motor (`agente.py` `_ferramentas_de_instrumento`) usa todas no cinto, mantendo o caminho de ferramenta única para os demais. As chamadas assíncronas do MCP são embrulhadas SÍNCRONAS (`asyncio.run`, conexão por chamada) — motor síncrono intocado. Transporte `streamable_http` (padrão) ou `sse`; token de auth é campo secreto (cofre 7-B → `Authorization: Bearer`). "Acionar" testa a conexão e lista as ferramentas. Deps `langchain-mcp-adapters`+`mcp`. UI sem mudança (catálogo dinâmico). 68 testes pytest verdes (6 novos; conexão mockada — teste LIVE precisa de servidor MCP real).
- **Banco de dados direto (SQL) ✅** (commit na branch): `instrumentos/sql.py` (`banco_sql`). Config = componentes de conexão (host/porta/banco/usuário públicos + **senha secreta** no cofre 7-B + modo `ssl`); a IA passa SQL + parâmetros nomeados (`:nome`, evitam injeção). SELECT → linhas (teto 100); escrita → linhas afetadas (commit). Conexão por chamada (NullPool, `connect_timeout`). Falha de conexão → falha do instrumento (retentável); erro de SQL → volta à IA como dado. PostgreSQL via `psycopg` (campo `tipo_banco` pronto para outros). 74 testes pytest verdes (6 novos, contra o Postgres real). UI sem mudança.
- **Gerar imagem ✅** (commit na branch): `instrumentos/gerar_imagem.py` (`gerar_imagem`). Gera imagem via API da OpenAI (chave = campo secreto do cofre 7-B); salva o arquivo localmente e devolve o link, como o `gerar_pdf` (migra p/ Supabase Storage na fase de produção). Aceita `b64_json` ou download da `url`. Falha de transporte/5xx/429 retentável; 401/403 e sem-chave não. `provedor` pronto para outros. 77 testes pytest verdes (3 novos; chamada mockada — geração LIVE precisa de chave OpenAI paga). UI sem mudança.

## REFINOS pós-Fase 10 (validação ao vivo, 2026-06-09)
Ajustes nascidos do uso real do maestro (montar/testar times pela IA criadora). Todos em `main`, só interface salvo onde indicado, com `tsc`/`eslint` e pytest verdes.

- **Formulário de segredos dos instrumentos** (interface): a tela de Instrumentos do time trocou o "Configuração (JSON)" cru por um formulário gerado do tipo (`esquema_config` + `campos_secretos`): campos públicos por tipo (texto/número/sim-não/JSON/**enum como Select**), segredos como inputs de **senha** (cofre 7-B; nunca reexibidos; em branco = manter). Fecha a lacuna de "não havia onde digitar a senha".
- **URL do webhook visível e copiável** (interface): novo `components/url-copiavel.tsx` (bloco mono + botão copiar). A URL `{URL_CEREBRO}/webhooks/automacoes/{id}` aparece no canvas da conversa (seção Gatilho), na tela de detalhe da automação e no form de automações, com aviso "só funciona com o time ativo". (Antes ficava escondida no form de edição.)
- **UX da tela de conversa** (interface): o casco do app trava em `h-dvh` e a área abaixo do cabeçalho rola por dentro — a conversa não estica mais o documento; chat e canvas rolam por coluna. O campo "Responder à IA" virou textarea que cresce com as linhas (Enter envia, Shift+Enter quebra).
- **Aprovação humana por instrumento, não fixa por tipo** (cérebro + interface, merge `3697e74`): antes todo `chamar_api_rest`/`banco_sql`/`conectar_mcp` era irreversível por tipo e exigia portão — inviável para **consultas**. Agora a irreversibilidade é **resolvida por instância** (`instrumentos.exige_portao(tipo, config, override)`): REST deriva do `metodo` (GET=leitura, sem portão; POST/PUT/DELETE=escrita, com portão); SQL ganhou `somente_leitura` (o instrumento **recusa** escrita → sem portão); webhook-saída/WordPress seguem sempre com portão. Interruptor por instância `instrumentos.exige_aprovacao` (coluna nullable, migração `d4e5f6a7b8c9`: NULL=auto/True=sempre/False=nunca) sobrepõe a derivação — pode liberar até uma escrita, com aviso na UI + auditoria `instrumento.aprovacao_alterada`. A parede de ativação e a fotografia da criadora leem por instância; o prompt da IA só põe portão em ESCRITA. **Motor de orquestração intocado.** 146 testes pytest. (Ver `PRODUTO.md` §19.) **Pegadinha:** times criados ANTES disto têm o portão preso na cadeia — pedir à IA para remover quando for só consulta.

## FASE de Design hi-fi — realizar o handoff por inteiro  ✅ CONCLUÍDA (2026-06-09)
A Fase 8 aplicou só a MARCA (cores/fontes/tokens) e as Fases 9/10 entregaram as telas AI-first de forma funcional. Esta fase realizou o **handoff hi-fi** (`docs/design/`, fonte da verdade visual): o shell, os dashboards ricos e os refinos de tela. Feito **tela a tela**, cada passo validado ao vivo pelo maestro e mergeado em `main` (até `15b388a`).

**Reconciliar com o pivô:** o handoff é anterior ao pivô (mostra "modo rascunho + Aprovar e criar time"). Onde conflitar com a conversa eterna sobre o time real, **vale o paradigma atual** — o design é referência VISUAL, não de fluxo.

Ordem de execução (handoff §13, reconciliada):
1. **Shell de sidebar** (README §5) + header de conteúdo (breadcrumb) + gating por papel — substitui o header simples pela sidebar escura definitiva (246px, `#1A1730`). ✅
2. **Dashboard do time** (`/times/[id]` → hub rico): stat cards (gatilho / aguardando você / custo), cadeia visual, execuções recentes, grid de agentes. ✅ Inclui a **edição pelo dashboard** (decisão do maestro, abordagem híbrida): drawer do agente vira ver↔editar + cinto + criar/remover, e os **instrumentos editáveis num painel** — `components/formulario-agente.tsx` e `formulario-instrumento.tsx` compartilhados; cadeia continua na tela cheia; "Ajustar com a IA" em destaque.
3. **Inspeção de execução** (`app-execution.jsx`): timeline com dots de estado, passos expansíveis, painel de aprovação creme, legenda das 3 formas de espera, toast. ✅
4. **Painel da IA companheira** em 3 camadas — estado atual / últimas execuções / decisões lembradas (§6.6). ✅
5. **Telas placeholder reais:** Biblioteca, Uso e custos, Configurações (§6.7). ✅ (`area-em-breve.tsx`)
6. **Polimento transversal:** animações `rise` (framer-motion, respeita reduzir-movimento), toasts (sonner), favicon a partir do símbolo. ✅

## REFINOS 2026-06-10 (chaves/contabilização + logo da organização)
Em `main` (merges `c67e504` e `423d291`), validados ao vivo pelo maestro. Cérebro + interface, testes verdes; **DB head agora `f6a7b8c9d0e1`**.

- **Chaves de IA selecionáveis + contabilização da conversa + painel da consultoria.** (1) A IA de conversa (criadora/companheira — uma só desde o pivô) ganhou **modelo selecionável por organização** (`organizacoes.modelo_criadora`, migração `e5f6a7b8c9d0`; nulo = padrão Opus), escolhido na tela de Chaves; o tipo "companheira" saiu do cofre (era chave morta). (2) Os seletores de modelo (do agente e da conversa) só mostram modelos cujo **provedor tem chave** resolvível (própria/consultoria + fallback Anthropic do ambiente) — novo `GET /organizacoes/{id}/modelos-disponiveis`. (3) O uso da **IA de conversa** (Opus) passou a entrar nos totais de custo (antes invisível): `precos.resumir_uso` soma também as conversas e o `/uso/resumo` org-level inclui a conversa. (4) Novo **painel da consultoria** `GET /uso/consultoria` (admin da consultoria) somando o gasto na chave-mãe por organização; tela `/uso-consultoria` + link na sidebar. **Motor de orquestração intocado.**
- **Logo da organização.** `organizacoes.logo_url` (Text, migração `f6a7b8c9d0e1`) guarda o logo como **data URI** (imagem encolhida no navegador via canvas; sem Storage/multipart — migra p/ Supabase Storage no futuro sem mudar a coluna). Form de organização virou **modal** reusável (criar/editar: nome + logo com preview e "remover"); `components/avatar-org.tsx` (logo ou inicial) na lista de organizações e no rodapé da sidebar. Validação no cérebro: só `data:image/`, com teto de tamanho.

## FASE — Implantação em produção  ✅ CONCLUÍDA (2026-06-13)
O Batuta está **no ar em produção**, no domínio próprio, com HTTPS. **Pré-requisito da Mensageria CUMPRIDO:** já existe a URL pública HTTPS que o webhook do WhatsApp precisa.

**Arquitetura de produção:**
- **Railway** (projeto "batuta"), 2 serviços do repo `ti927/batuta`, cada um com Root Directory (`cerebro/` e `interface/`) e **Dockerfile** próprio (cérebro: python:3.13-slim + uv; interface: Node 22, Next standalone, `NEXT_PUBLIC_*` como build args). Região **US East** (mais perto do banco em São Paulo — Railway não tem região no Brasil). 1 réplica (agendador/fila em processo).
- **Banco:** o **Supabase atual** (sa-east-1 São Paulo) — reusado, sem migração; mesmas chaves (inclusive `COFRE_CHAVE_MESTRA`).
- **Domínio:** `batuta.team` (interface) e `api.batuta.team` (cérebro), via **Cloudflare** (DNS, CNAME flatten na raiz) com registros em **DNS only (cinza)**; HTTPS automático do Railway.
- **CORS** por ambiente (`INTERFACE_ORIGINS`); a interface fala com o cérebro em `https://api.batuta.team`.

**Gotchas resolvidos (importam p/ futuras mudanças):** (1) Supabase é IPv6 → ligar **"Enable Outbound IPv6"** no serviço Railway (senão `Network is unreachable`). (2) `NEXT_PUBLIC_*` são **congeladas no build** → mudar a URL do cérebro exige rebuild da interface. (3) Cloudflare: registros que apontam pro Railway têm que ser **DNS only (nuvem cinza)**, nunca proxied. (4) Latência: manter Railway em **US East** (perto do banco SP). Detalhe operacional completo na memória [[reference-producao-railway]].

**Limitação conhecida (follow-up):** `gerar_pdf`/`gerar_imagem` gravam em disco efêmero do Railway → migrar p/ Supabase Storage depois.

## FASE — Mensageria de mão dupla (Telegram, depois WhatsApp)  🟢 FASE 1 NO AR — pendências enfileiradas
> **Plano detalhado e durável em `docs/MENSAGERIA-PLANO.md`** (esta seção é o resumo). Lição que originou
> o desenho: a memória `feedback_canais-sao-instrumentos`.

**STATUS (2026-06-14): Fase 1 NO AR e validada ao vivo** (merge em `main`, deploy Railway, 181 testes,
núcleo intocado). Entregues e em produção: **Milestone 1** (instrumento `enviar_telegram`, Conversa/sessão,
webhook + roteamento conversacional, conectar canal, inbox + transferência para humano) e **Milestone 2 —
Fases I** (debounce de rajada + teto de gasto/máx. turnos → passa para humano), **J** (timeout: cutuca 1x e
encerra, vigia no agendador), **G** (guarda-corpo anti prompt-injection) e **H** (áudio→texto via Whisper).

**FILA DE IMPLANTAÇÕES — aprovadas (a ordem é do maestro):**
1. ✅ **Contabilização de uso de IA por CATEGORIA** (APROVADA · IMPLEMENTADA · NO AR 2026-06-14, commits
   `e9c6138`+`d8571ce`, 187 testes verdes, migração `msg00uso0001` aplicada, deploy Railway saudável). Toda
   chamada de IA paga carrega `origem` **e** `categoria` (`execucao` / `conversa` / `mensageria` /
   `transcricao`); `/uso/resumo` e `/uso/consultoria` somam a mensageria e expõem `por_categoria` (no painel
   da consultoria, dentro de cada organização). Fechou os furos: mensageria (turno do agente) e Whisper agora
   aparecem nos painéis — coluna `uso` (JSONB) em `mensagens_conversa`; Whisper contabilizado por minuto.
   Carimbo na BORDA (núcleo congelado intocado). Categoria `instrumento` (gerar_imagem) ficou de fora →
   virou o item 2 desta fila.
2. ✅ **Contabilização da categoria `instrumento` — gerar_imagem** (APROVADA · IMPLEMENTADA 2026-06-14).
   Fechou o ÚLTIMO furo: o `gerar_imagem` consome IA paga (OpenAI, cobrada **por imagem**) e não era
   contabilizado.
   - **Desafio:** o custo de um instrumento nasce **dentro do `executar_agente`** (núcleo congelado,
     `agente.py`), e o contrato `executar(config, args) -> dict` não reporta uso. Capturá-lo pelo motor
     exigiria tocar o núcleo — proibido.
   - **Caminho REAL (melhor que o livro-razão que eu havia planejado; descoberto lendo `agente.py`):** o
     motor já devolve `instrumentos_acionados` — a lista de NOMES de ferramenta acionadas, e cada nome
     embute o id do instrumento (`{nome}_{id8}`, ver `_nome_de_ferramenta`). Então a contabilização é
     **100% na borda, sem tabela nova, sem migração, sem carimbar config**: o novo módulo
     `cerebro/medicao_instrumentos.py` casa esses nomes com o cinto do agente e gera entradas de `uso`
     (categoria `instrumento`, custo por imagem) que entram no MESMO `uso` do passo (`disparo.py`) e do
     turno da mensageria (`servico.py`) — logo nos mesmos painéis (`precos.resumir_uso`). `precos` ganhou
     `custo_por_imagem(modelo, tamanho)` + tabela de preços; categoria `instrumento` no agregador; rótulo
     "Instrumentos com IA (imagens)" em `lib/uso.ts`. **Origem = `organizacao`** (o `gerar_imagem` usa a
     chave do PRÓPRIO instrumento, no cofre 7-B — não a chave-mãe da consultoria), então aparece em
     `/uso/resumo` (visível ao usuário) e corretamente NÃO em `/uso/consultoria`.
   - **Verificado:** testes de `custo_por_imagem` + do helper de borda; suíte verde; núcleo
     `agente.py`/`cadeia.py` sem diff.
3. ✅ **Unificação de chaves e credenciais** (pedido do maestro · IMPLEMENTADA 2026-06-14, commit `7111106`,
   206 testes, sem migração; push/redeploy pendentes de aval). Dois cofres separados confundiam, e o
   `gerar_imagem` exigia a chave OpenAI num 2º lugar. Decisões do maestro: *unificação + tela única* (migrar
   os fallbacks `.env` do Railway p/ o cofre fica para depois) e *reusar a chave da org* (com override por
   instrumento). Parte 1 (borda): instrumentos declaram `chave_compartilhada=(campo,servico)`
   (gerar_imagem→openai, busca_web→tavily); a injeção é em `segredos_instrumento.anexar_aos_instrumentos`
   (ponto único chamado pelo frozen `cadeia._carregar_cinto` e pela mensageria) lendo `llm.chaves_atuais()`;
   `chaves.py` resolve `tavily` no pool; a origem da imagem segue a chave real. Parte 2: tela única
   **"Chaves e credenciais"** (seção A chaves de serviço c/ Tavily; seção B inventário de credenciais de
   instrumento com rotação inline — `cerebro/rotas/credenciais.py`). Núcleo intocado. Detalhe em
   `~/.claude/.../memory/reference_chaves-unificadas.md`.
   - ✅ **A seção B FOI SUBSTITUÍDA (2026-06-15):** ao validar, o maestro achou o "inventário de credenciais
     por-instrumento-por-time" confuso. A conversa evoluiu para a **Caixa-forte de Credenciais** (item logo
     abaixo), JÁ ENTREGUE E EM PRODUÇÃO — `inventario-credenciais.tsx` removido e `cerebro/rotas/credenciais.py`
     reescrito como o CRUD do cofre.
4. ✅ **FASE — Caixa-forte de Credenciais** (CONCLUÍDA, VALIDADA AO VIVO E EM PRODUÇÃO — 2026-06-15, merge
   `9dd93e4`; migração `crd00cofre001`; ~228 testes; núcleo intocado). Substituiu a "seção B" (inventário) por
   um cofre de **credenciais nomeadas, tipadas e referenciadas** — resolveu a confusão da seção B E o desenho
   à prova de futuro (MCP, Google Drive/OAuth, Nano Banana). E2E ao vivo: credencial WordPress na caixa-forte →
   apontada num instrumento → publicou rascunho real usando o segredo central. Plano dos 8 passos e progresso
   em `docs/CAIXA-FORTE-PLANO.md`. Desenho abaixo, mantido como registro:

   **Os três baldes de autenticação** (toda auth que um instrumento pode precisar cabe aqui):
   - **Balde 1 — Chave de provedor (pool institucional, JÁ EXISTE):** uma por serviço, compartilhada, com
     queda org→consultoria→legado. OpenAI/Anthropic/Google/Tavily. Implícita (o motor usa) ou reusada por
     instrumento via `chave_compartilhada`. *Predição:* **Nano Banana** (imagem do Google) cai aqui inteiro —
     reusa a chave `google` do pool; instrumento novo só declara `chave_compartilhada=(campo,"google")`. Zero
     infra nova. Provedor novo = mais um nome na lista de serviços.
   - **Balde 2 — Credencial nomeada estática (A CAIXA-FORTE NOVA):** o usuário cria entradas nomeadas
     ("WordPress Blog", "Banco Produção", "Bot de Vendas"); troca/rotaciona num lugar só; instrumentos
     **apontam** para a credencial. Cobre WordPress (usuário+senha-app), SQL (usuário+senha), token de bot do
     Telegram, REST com token, **MCP com token/header**.
   - **Balde 3 — Conta conectada por OAuth (MESMA tabela da caixa-forte, `tipo` diferente):** autoriza uma
     vez por consentimento, o sistema renova o token sozinho. Google Drive, Gmail, Microsoft, **MCP com OAuth**.
     NÃO será construído agora — mas o desenho não pode travá-lo.

   **Princípio à prova de futuro (a decisão central):** uma credencial é um **saco nomeado, tipado e cifrado
   de campos** — `{nome, tipo, organizacao_id, dados_cifrados (JSON), expira_em?}` — e o instrumento **aponta**
   para uma credencial do tipo certo, somando só a sua config **não-secreta** (URL, método, nome do banco).
   Nada de colunas fixas tipo "senha" ou "usuário+senha": o `tipo` (declarado no código, como `TipoInstrumento`)
   define quais campos e qual UX (formulário de colar × botão "Conectar" do OAuth). Instrumento futuro com
   formato de segredo inédito = novo `tipo` + campos no JSON, **sem mudar o banco**. OAuth cabe porque a
   credencial pode ser preenchida por fluxo (não só colada) e atualizada pelo sistema (refresh).

   **Tela final "Chaves e credenciais"** (renome cancelado — o nome volta a fazer sentido): **Seção A** =
   chaves de serviço (pool do balde 1, como hoje). **Seção B (reescrita)** = a caixa-forte: lista de
   credenciais nomeadas que o usuário cria, com "usado por N instrumentos" e trava ao apagar credencial em uso.
   No formulário do instrumento, o campo de segredo vira "usar uma credencial da central" (seletor, filtrado
   pelo tipo) **OU** valor próprio inline (**híbrido** — retrocompatível: instrumentos já no ar não quebram).
   **Dois níveis + toggle "compartilhável" (decisão do maestro 2026-06-15):** segredo pode ser da organização
   ou da consultoria (`organizacao_id` nulo); chave/credencial de consultoria só serve às organizações se
   marcada `compartilhavel` (balde 1 = entra na reserva automática; balde 2 = aparece no seletor — escolha
   explícita). Chaves de consultoria existentes nascem compartilháveis (retrocompatível). Detalhe e passo a
   passo em `docs/CAIXA-FORTE-PLANO.md`.

   **Gargalos endereçados:** (1) referência, não cópia → "usado por" + trava no delete; (2) o par
   usuário+senha anda junto (credencial guarda o conjunto da conexão, não senha solta); (3) custo honesto =
   **tem migração** (tabela `credenciais`, cifrada com a mesma chave-mestra do cofre 7-B) + resolução por
   referência **na borda** (núcleo congelado). **Fora de escopo:** credencial por **usuário-final** (cada
   cliente conectar o próprio Drive dentro de um atendimento — é da conversa, não da org). Detalhe vivo em
   [[reference-chaves-unificadas]].
5. ✅ **FASE — Chave de IA por provedor (unificação)** (CONCLUÍDA · NO AR 2026-06-15, migração
   `una00prov001`, merge `d674bb5`; 228 testes verdes). Removeu a dimensão de papel `executora`/`conversa` da
   chave: a chave passou a ser **uma por provedor** ("este provedor tem credencial?"); a escolha de IA fica
   só no **modelo** da conversa (`Organizacao.modelo_criadora`) e de cada **agente** (`Agente.modelo_ia`).
   Acabou o cadastro em dobro e a "pegadinha da imagem". **Núcleo intocado** (só a fronteira de resolução em
   `chaves.py`). Migração consolidou em produção (5→4 linhas, zero conflito) e dropou `tipo_ia`. Os 5 passos
   (migração+reindexa / `chaves.py`+`rotas/chaves_api.py` sem papel / `criacao.py`+`organizacoes.py` por
   provedor / interface sem seletor de papel / testes reescritos + e2e) foram entregues. **Validado ao vivo:**
   a IA de conversa via OpenAI respondeu e editou um instrumento. Plano e lições em
   `docs/CHAVE-POR-PROVEDOR-ESTUDO.md`. **Lição:** a migração (drop de coluna) rodou ANTES do deploy → o prod
   ficou momentaneamente com schema novo + código velho (resolução de chave falhava) até o redeploy reconciliar;
   para drops futuros, subir o código que não usa a coluna ANTES de dropá-la. Correção de teste: o `conftest`
   passou a esvaziar `chaves_api` por teste (banco real tem chaves de consultoria).
   - ✅ **Sub-melhoria — `gerar_imagem` com campos guiados** (NO AR 2026-06-15, merge `f551952`, 232 testes).
     No e2e da imagem, os campos `modelo`/`tamanho` eram **texto livre** → usuário digitava valores inválidos
     (`1024x102`, modelos inexistentes), e o default `dall-e-3` falha em contas que só têm `gpt-image-1`.
     Correção: `modelo`/`tamanho` viraram `Literal` (a UI já os renderiza como **dropdown**), default passou a
     `gpt-image-1`, `model_validator` valida o par modelo×tamanho com mensagem clara já ao salvar, e os campos
     ganharam `title` (rótulo amigável; o frontend lê o `title` do schema). Princípio geral: **campo de
     conjunto fechado = `Literal`/enum, nunca texto livre.** **Validado ao vivo:** o agente do Telegram gerou
     uma imagem real (gatinho, servida em `api.batuta.team/arquivos/...png`). **NB:** o agente no chat esconde o
     erro técnico (persona) e às vezes nem retenta a ferramenta — o botão "Testar" do instrumento é o
     diagnóstico confiável (mostra o erro real via 502). Detalhe na memória.
6. ✅ **Fase K — polimento de atendimento** (CONCLUÍDA · NO AR 2026-06-16, merge `6af0fd2`, 239 testes).
   Tudo na borda, **núcleo congelado, SEM migração**. (a) **Horário comercial:** campos declarados na
   `ConfigTelegram` (ativar, início/fim HH:MM, só dias úteis, mensagem fora do horário); fora do horário a
   borda responde automático e NÃO aciona a IA (fuso fixo UTC−3, sem `tzdata`). (b) **Saudação/transparência:**
   enviada uma vez no 1º contato de cada conversa (nasce ligada, editável/desligável). (c) **Métricas:**
   `GET /times/{id}/conversas/metricas` (volume, % handoff, tempo médio de 1ª resposta, custo de IA) + faixa de
   cards na inbox. (d) **Status de entrega** já existia (`MensagemConversa.entregue`). Lição reforçada: os
   campos novos do instrumento só aparecem após reiniciar o cérebro (processo velho serve schema velho) —
   `--reload` no dev evita. Campos declarados na Config persistem (model_dump descarta não-declarados).
7. ✅ **Aprovação do portão por canal (Telegram)** (IMPLEMENTADA · NO AR 2026-06-16, merge `52431bc`,
   migração `apv00canal001`, 265 testes). O portão de aprovação (`pausa_humano`) passou a ser resolvível
   **também pelo Telegram**, coexistindo com a tela (vale a 1ª resposta): a automação aponta um canal de
   aprovação (`automacoes.aprovacao_instrumento_id`); ao pausar, a borda amarra a conversa do aprovador à
   execução (`Conversa.execucao_id`) e a resposta de entrada religa o fluxo (`retoma`). **NB:** será
   **ABSORVIDA pela FASE — Automações como grafo** (a config de aprovação migra para o NÓ com portão, no
   inspector; a coluna por-automação será aposentada — resolve também o atrito do destinatário).
8. ✅ **FASE — Automações como grafo (construtor visual)** — **NO AR EM PRODUÇÃO (merge `bf6066f`,
   2026-06-17); Salvar validado ao vivo**. Substituiu a lista linear pelo construtor de grafo (React Flow),
   adaptou o motor ao novo `cadeia` (lista de nós tipados), e **absorveu a aprovação por canal** (config no
   NÓ com portão). **Pendente:** arrastar (React Flow), QA completo em prod, e aplicar o drop adiado da
   coluna `aprovacao_instrumento_id`. Detalhes na seção própria abaixo. **Próximas:** (9) WhatsApp, (10) Biblioteca.
9. 📋 **Fase 2 — WhatsApp** (mesmo desenho + provedor + janela de 24h/templates).
10. 📋 **Biblioteca** (RAG da organização; plano de 10 passos aprovado, `docs/BIBLIOTECA-DECISAO.md`).

O `PRODUTO.md` prevê que os agentes conversem com pessoas por mensageria (§10/§111/§126/§14). Hoje a
espera-por-humano é respondida **na tela do Batuta**, e o Batuta só sabe *enviar* (instrumentos de mão
única). Falta a **mão dupla**: a pessoa manda mensagem, o agente responde, a pessoa replica, o agente
reage — em laço. Esta fase fecha a lacuna.

**Correção de rota (2026-06-13):** uma 1ª tentativa criou um **"ambiente de Canais" no nível da
organização** (tabelas `canais`/`identidades_canal` + página própria) seguindo o antigo
`docs/CANAL-MENSAGERIA-PLANO.md`. O maestro **rejeitou e mandou reverter** — a intenção real é
**canal = INSTRUMENTO** no cinto do agente. O trabalho ficou preservado na branch `canais-mensageria`.
A seção anterior deste arquivo (provedor **Evolution**, "canal do Líder", onboarding por QR) está
**superada** por este novo desenho.

**Faseamento (decisão do maestro):** **Fase 1 = Telegram com TODAS as soluções de atendente de IA**
(profissional); **Fase 2 = incorporar WhatsApp** (mesmo desenho + provedor + janela de 24h/templates).

**Princípio (núcleo congelado):** o canal é um **instrumento** (`enviar_telegram`/`enviar_whatsapp`,
molde `cerebro/instrumentos/webhook_saida.py`, token = campo secreto do cofre 7-B), e em cima dele uma
**camada fina de conversação na borda** coordena os turnos. **Não toca** `cerebro/orquestracao/cadeia.py`
nem `agente.py`; reusa a espera-por-humano (`responder`), a fila (`criar_execucao`/`fila.enfileirar`), o
agendador (sweeper de timeout) e a infra de chaves (Whisper via OpenAI).

**O novo conceito de 1ª classe:** uma **Conversa (sessão)** — tabelas novas `conversas` +
`mensagens_conversa` (aditivas; o motor não muda de esquema) — com estado
(aberta→bot_respondendo→aguardando_resposta→humano_assumiu→fechada). Inbox, transferência para humano,
debounce, timeout, tetos e métricas penduram nessa sessão.

**Decisões batidas:** suportar **os dois** formatos (conversacional = 1 agente em papo natural com
histórico por turno; e fluxo com etapas = cadeia com pausa/retoma), começando pelo conversacional;
inatividade = **cutucar uma vez e depois encerrar**; teto de gasto estourado = **passar para um humano**.

**Escopo da Fase 1 (todas as soluções de atendente):** instrumento de envio; webhook de entrada por
instrumento + roteamento; Conversa/sessão; mão dupla (conversacional e fluxo); transferência para humano +
inbox; áudio→texto (Whisper); debounce/rate-limit/teto de gasto/máx. turnos; anti prompt-injection +
transparência + sandbox; timeout + nudge (job no agendador); horário comercial, status de entrega,
métricas. **Detalhe passo a passo (Milestones A–K) em `docs/MENSAGERIA-PLANO.md`.**

**Pré-requisitos do maestro:** bot de teste no BotFather + token (regenerar os tokens que vazaram no chat
antes de uso real); chave OpenAI no cofre (para a transcrição de áudio). Pré-requisito de infra **já
cumprido**: URL pública HTTPS (`api.batuta.team`).

**Definition of Done (Fase 1):** mandar mensagem (texto ou áudio) ao bot → o agente responde; rajada vira
um turno; a conversa aparece na inbox e um operador pode assumir/devolver; inatividade gera nudge e depois
encerra; estourar o teto passa a conversa para humano; suíte verde; núcleo `cadeia.py`/`agente.py` sem
diff.

## FASE — Automações como GRAFO (construtor visual + motor adaptado + aprovação no nó)  ✅ NO AR E VALIDADA AO VIVO EM PRODUÇÃO (2026-06-17)

> **Fontes da verdade:** o handoff de design **`docs/design_handoff_automacoes_grafo/`** (`README.md`,
> `SPEC.md` = formato do `cadeia`, `LANGGRAPH.md` = mapa visual→motor, `app-team-automacoes.jsx` +
> screenshots) e o plano detalhado em **`~/.claude/plans/temos-um-problema-pra-replicated-noodle.md`**.
> Esta seção é o resumo durável no BUILD-PLAN.

> **Status (2026-06-17): VALIDADA AO VIVO em produção** pelo maestro — montar/Salvar, **nó inicial**,
> **arrastar**, **bifurcação/loop**, **Rodar**, e o **portão aprovado por Telegram + pela tela** funcionam.
> **285 testes** verdes; `tsc`/`eslint`/`next build` limpos. `main`=`64d0088`. **PENDENTE (1 item):** quando
> o maestro autorizar, recriar e aplicar o **drop** `apv00drop001` (`automacoes.aprovacao_instrumento_id`,
> hoje órfã — a aprovação vive no nó). Banco = produção → confirmar antes.
>
> **A saga do "nó inicial" (whack-a-mole) e a correção DEFINITIVA (commits `77687fd`→`9254296`):** o erro
> "nó inicial ausente" voltava porque "quem é o início" morava em **3 lugares** (`cadeia.inicial`, a flag
> `n.inicial` por nó, a saída do nó gatilho) com **regras de conserto DIFERENTES** no front e no motor —
> cada fix mexia num só e voltava. **Raiz resolvida:** fonte ÚNICA = `cadeia.inicial`; o front ganhou
> `normalizarCadeia` (em `automacao-builder/nucleo.ts`) que **ESPELHA** `grafo._completar` do cérebro e é
> aplicada em **ponto único** (todo `setCadeia` do construtor passa por ela + no load + antes de salvar);
> flag e saída do gatilho viraram **derivadas**. As **arestas que sumiam** (cordão do gatilho + bifurcações
> além da 1ª) eram **handle bounds** desatualizados do React Flow após o fix do arrastar → resolvido com
> `useUpdateNodeInternals` (+`ReactFlowProvider`). O **arrastar** (#015 "node not initialized") foi
> resolvido com `useNodesState`/`applyNodeChanges` + reconciliação-em-render preservando `measured`.
>
> **LIÇÃO 1 — verifique qual código produção roda, não adivinhe:** parte do "fix que não fixava" era
> **deploy defasado** — a mensagem de erro vista era de uma versão ANTIGA. Agora `GET /saude` reporta o
> commit no ar (`RAILWAY_GIT_COMMIT_SHA`); confirmado por WebFetch que prod == HEAD do fix. Ver
> `memory/reference_verificar-deploy-prod.md`.
> **LIÇÃO 2 — QA local contaminado:** workers órfãos do `uvicorn --reload` no Windows serviam bytecode
> velho; valide em deploy LIMPO. Ver `memory/feedback_qa-local-contaminado-deploy-limpo.md`.

> **Como ficou (2 desvios do plano, ambos para proteger a produção no ar — banco = produção):**
> (1) **Sem migração de dados destrutiva.** Em vez de converter as automações em produção (o que quebraria
> o código antigo ainda no ar), o motor **NORMALIZA na leitura** (`grafo.normalizar`, idempotente, lê o
> formato antigo e o novo); cada automação migra de forma preguiçosa ao ser re-salva pelo construtor. A
> migração `gra00grafo001` ficou **só aditiva** (coluna `passos_execucao.no_id`, nullable) — já aplicada.
> (2) **Drop da coluna `aprovacao_instrumento_id` ADIADO** para depois de estável (a migração `apv00drop001`
> foi REMOVIDA deste deploy; recriar e aplicar quando confirmado). Mantendo a coluna, código novo e antigo
> convivem no mesmo schema → rollback do deploy é só de código, sem downgrade de banco.
> Canvas: **React Flow (`@xyflow/react`)** confirmado pelo maestro. Núcleo: `agente.py` intocado.

**Por que (o problema):** a aba Automações nasceu como **lista linear** (1 cartão por agente, 1 saída)
para acelerar a prova do core. Ao montar times com vários agentes, múltiplas saídas, bifurcações e loops,
isso virou gargalo e não comunica a topologia. O motor (`PRODUTO.md §14`, Fase 4) **já executa** grafo
com bifurcação, loops e portão — falta a **TELA** para desenhá-lo.

**Verdade técnica (apurada no código, registra para não repetir o engano do handoff):** o motor do Batuta
**NÃO é LangGraph nativo** — é um motor próprio em Python (`orquestracao/cadeia.py::executar_cadeia`:
caminha pelos nós, roteia via `_escolher_saida` com LLM Haiku, pausa retornando `aguardando_humano`,
retoma em `mensageria/retoma.py`; `MAX_PASSOS=25`). O `create_react_agent` do LangGraph é usado só para UM
agente rodar suas ferramentas (`orquestracao/agente.py`). O `LANGGRAPH.md` é educativo/aspiracional; o
próprio §6 manda **NÃO reescrever a orquestração**.

**Decisões do maestro (2026-06-16):** (1) **adaptar** o motor atual ao novo formato de grafo — **não**
migrar para StateGraph/checkpointer/interrupt nativos; (2) **integrar a aprovação por canal** nesta
reforma: a config de aprovação passa a viver **no nó com portão** (inspector), substituindo a coluna
por-automação `aprovacao_instrumento_id` (item 7 da fila acima) — resolve de forma coesa o portão por
Telegram (inclusive o atrito do destinatário, que passa a ser explícito por portão).

**Novo formato do `cadeia` (JSONB) — `SPEC.md §2`:** de **dict por-agente** (`{inicio, nos:{agente_id:
{saidas:[{rotulo,quando,destino}], pausa_humano}}}`) para **lista de nós tipados** (`{inicial,
nos:[{id,tipo,ref,gate,aprovacao,x,y,saidas:[{id,rotulo,destino,tone}]}]}`). Tipos de nó: **gatilho**,
**agente**, **roteador** (classificação sem agente — novo), **fim**. `tone`/`x`/`y` são **cosméticos** (o
motor ignora); o `rotulo` é a **chave de roteamento** (mantém-se `quando` como descrição opcional). O nó
tem `id` próprio separado do `ref` (agente) → **o mesmo agente pode aparecer em vários nós** (novo).

**Faseamento (cada fase = investigar/implementar/verificar + DoD; suíte verde entre fases; ordem sugerida
1→2→3→5→4→6):**
1. **Fundação no cérebro:** `orquestracao/grafo.py` (novo: `normalizar`, `converter_linear_para_grafo`,
   `indexar`); **migração de dados** idempotente convertendo as automações em produção para o novo shape;
   coluna `passos_execucao.no_id` (nullable) para a retomada localizar o nó pausado por id; `esquemas.py`
   aceita/expõe o novo `cadeia`.
2. **Adaptar o motor:** `cadeia.py` (`validar_cadeia` + `executar_cadeia` indexando por id de nó;
   resolve agente por `ref`; ignora `gatilho`; `fim`/sem-saída = encerra; `gate` no lugar de
   `pausa_humano`; nó **roteador** só classifica); `retoma.py` (localiza o nó pausado por `no_id`);
   `disparo.py` (grava `no_id`); `portao_ativacao.py` (parede no novo shape). Testes do motor.
3. **Caminho da IA criadora:** `montar_cadeia` aceita grafo **simplificado** e o backend `normaliza`
   (a IA não cuida de x/y/ids/gatilho/fim); `criacao/servicos.py` opera no novo shape; `criacao/prompt.py`
   reescreve cadeia/bifurcação/portão (`gate`, `rotulo`); `_snapshot_time` expõe o novo formato. Os **dois
   caminhos (manual e IA)** produzem o MESMO `cadeia`.
4. **Construtor visual (React Flow / `@xyflow/react`):** substitui `automacoes-cliente.tsx` por um
   `AutomacaoBuilder` (canvas full-bleed; nós custom Gatilho/Agente/Roteador/Fim com handles de entrada/
   saída; arestas `CondEdge` com rótulo + cor por `tone`, curva de loop; inspector 348px com editor de
   saídas + toggle de portão; pan/zoom/enquadrar; gating por papel). Tipos `Cadeia/NoCadeia/SaidaCadeia`
   reescritos em `lib/api.ts`.
5. **Consumidores read-only adaptados:** `inspecao-execucao.tsx` (botões do portão a partir do nó pausado
   por `no_id`), `dashboard-cliente.tsx` (`CadeiaHorizontal`), `criar/[id]/criacao-cliente.tsx`
   (`CadeiaVertical`), `automacao-detalhe-cliente.tsx` (`inicial`).
6. **Aprovação por canal no nó (absorve o item 7 da fila):** o nó `gate` carrega
   `aprovacao:{instrumento_id, destinatario}`; `mensageria/aprovacao.py::vincular_pausa` lê a config do nó
   pausado (não mais da automação); inspector do nó configura "pedir aprovação por" (tela/canal) +
   destinatário; a coluna `automacoes.aprovacao_instrumento_id` é aposentada (drop ADITIVO depois que o
   código parar de usá-la). O restante (correlação `Conversa.execucao_id`, roteamento da resposta →
   `retoma`, ack, coexistência com a tela) **já existe** e permanece.

**Princípios/cuidados:** o redesenho **toca o parser do motor** (antes "congelado") — é evolução
autorizada; `agente.py` (laço react de UM agente) **permanece intocado**. Gatilho continua tendo
`tipo_gatilho`/`configuracao_gatilho` na `Automacao` como fonte da verdade do agendador/webhook (o nó
`gatilho` é reflexo). Mudança de shape toca muitos lugares (listados no plano) → fazer por fase, nunca
meio-quebrado. Migração de dados pede confirmação do maestro (banco = produção).

**Definition of Done:** abrir uma automação real (migrada) no construtor mostra o mesmo fluxo; montar
bifurcação + loop + portão visualmente e salvar/reabrir idêntico; disparar segue o ramo certo nos dois
casos; o portão pausa e é resolvido pela **tela** OU pelo **Telegram** (canal configurado no nó);
a IA criadora também monta o grafo; suíte verde; `tsc`/`eslint` limpos; `agente.py`/laço de agente sem diff.

---

## FASE — Biblioteca: a base de conhecimento da organização (§9)  📋 PLANEJADA — APROVADA, aguarda execução
O `PRODUTO.md` §9 prevê a **Biblioteca** ("segundo cérebro") — mas ela **caiu num vão** e nunca foi implementada (hoje só há um placeholder em `/biblioteca`; não há tabela). O maestro **revisou o conceito**: é uma **base de conhecimento da ORGANIZAÇÃO inteira** (todos os times acessam, não é por-time) de **documentos gerais** (PDF, Word, planilhas, texto — não só markdown), que os agentes **consultam** durante a execução. Esta fase fecha essa lacuna. A decisão arquitetural está fechada em **`docs/BIBLIOTECA-DECISAO.md`** e o pano de fundo técnico em **`docs/ARQUITETURA.md`**; o **plano de implementação detalhado (10 passos) está aprovado** e aguarda o sinal do maestro para começar.

**Decisão arquitetural (fechada):**
- **Busca = RAG** (pgvector + embeddings OpenAI `text-embedding-3-small`, 1536 dims). Full-text foi descartado (qualidade insuficiente no domínio financeiro/contábil em português; possível complemento híbrido no futuro, não na v1). Não contradiz a "memória destilada sem vetor" da Fase 10: lá são poucas memórias curtas que cabem no contexto; aqui são milhares de pedaços de documento que não cabem — vetor é o jeito de selecionar o que cabe.
- **Escopo:** organização inteira + **tags livres** para filtrar (não cria "biblioteca por time").
- **Ingestão assíncrona** (extrai texto → fatia → gera embeddings → salva), com a UI mostrando o estado de cada documento (pendente/processando/pronto/falhou).
- **Consulta pelo agente:** novo **instrumento `consultar_biblioteca`** — encaixa no sistema de instrumentos **sem tocar no motor** (padrão já validado). Só lê (`acao_irreversivel=False`).
- **Fora da v1 (deliberado):** OCR (PDF escaneado); escrita pelo agente na Biblioteca (só humano cura); versionamento; permissões por documento; citação inline automática.

**Refinos vindos da leitura do código (o doc de decisão externo não os via):**
- O contrato de instrumento só recebe `(config, args)` — sem `Session`/`organizacao_id`. → O `consultar_biblioteca` recebe o **`organizacao_id` carimbado na sua `config` no momento da criação**, e **resolve a chave OpenAI sozinho em runtime** (cofre por org → consultoria → `OPENAI_API_KEY` do ambiente). Motor e carregador de cinto intocados.
- A fila atual (`fila.py`) é acoplada a `Execucao`/`rodar_execucao`. → A ingestão usa um **trabalhador próprio `fila_biblioteca.py`**, no mesmo padrão (`FOR UPDATE SKIP LOCKED` sobre `biblioteca_documentos` em `pendente`), iniciado no lifespan do `main.py` ao lado de `fila`/`agendador`.
- **Storage via httpx** (espelha `supabase_admin.py`, sem SDK) contra a REST de Storage do Supabase. **Upload é multipart** (`UploadFile`/`FormData`) — a API hoje é só JSON.

**Pré-requisitos de painel (o maestro faz, eu guio na hora):** (1) bucket privado **`biblioteca`** no Supabase Storage; (2) extensão **`vector`** habilitada no Postgres do Supabase; (3) **chave OpenAI** disponível para os embeddings (chave-mãe da consultoria no cofre com `provedor=openai`, ou `OPENAI_API_KEY` no Railway) — necessária mesmo que os agentes usem Anthropic.

**Plano de implementação (10 passos, cada um investigar/implementar/verificar + DoD, um por vez com aprovação):** 1) schema (2 tabelas + pgvector + bucket); 2) endpoints de gestão (upload/listar/editar tags/excluir, sem ingestão); 3) tela `/biblioteca`; 4) extração de texto (pdf/docx/xlsx/csv/txt/md); 5) fatiamento; 6) embeddings (com contabilização de custo); 7) trabalhador de ingestão; 8) instrumento `consultar_biblioteca`; 9) teste ponta a ponta com o motor real; 10) refino e auditoria.

**Tabelas previstas:** `biblioteca_documentos` (`organizacao_id`, `nome`, `tipo_arquivo`, `tamanho_bytes`, `storage_path`, `tags[]`, `estado_ingestao`, `mensagem_erro`, `criado_por_id`) e `biblioteca_pedacos` (`documento_id`, `organizacao_id`, `ordem`, `texto`, `embedding vector(1536)`, `tokens`, `metadados`). Isolamento por organização em toda query e no path do Storage. **Núcleo de orquestração congelado** — estende, não altera.

**Definition of Done:** documentos reais subidos pela tela são ingeridos automaticamente (viram `pronto` com pedaços e embeddings); um agente com `consultar_biblioteca` no cinto responde citando os documentos da organização; isolamento por org provado; custo de embedding contabilizado no painel; tudo sem tocar no motor.

---

## FASE — Busca/leitura na web (Exa + Tavily extract + Firecrawl)  ✅ NO AR (2026-06-19, merge `c8687e0`)
A descoberta era rasa (`busca_web`/Tavily → título+link+**trecho**) e não havia como **ler o artigo completo** nem **buscar por significado**. Entregue como TRÊS instrumentos novos, todos no molde do `cerebro/instrumentos/busca_web.py` (Config com campos guiados `Literal`/`Field`, `executar` httpx, política de falha do encaixe, `acao_irreversivel=False` → sem portão), reusando o **pool de chaves** via `chave_compartilhada` e **sem migração, núcleo intocado**:
- **`busca_exa`** — busca **semântica** (Exa, `POST /search`, auth `x-api-key`): traz ângulos mais diversos (ataca a "mesma pauta"). Config: tipo_busca/categoria/recência/domínios/qtd. Serviço de pool `exa`.
- **`ler_site`** — leitura de página via **Tavily `/extract`** (auth Bearer), **reusando a MESMA chave `tavily`** do `busca_web`. Config: profundidade/formato/máx. caracteres. Não lê páginas de JavaScript.
- **`ler_site_firecrawl`** — leitura robusta via **Firecrawl `/v2/scrape`** (auth Bearer): lê até sites de JavaScript. Config: só-conteúdo-principal/máx. caracteres. Serviço de pool `firecrawl`.

**Antes dos três (merge `83436dc`):** o próprio `busca_web` (Tavily search) ganhou **controles configuráveis** na Config — `topico`/`recencia`/`profundidade`/`pais`/`incluir_dominios`/`excluir_dominios` (campos `Literal`/`Field` → dropdowns) — para o usuário **padronizar/otimizar** a busca e atacar a "mesma pauta" sem trocar de instrumento. Defaults = comportamento antigo (zero regressão); `executar` monta o corpo condicionalmente (ex.: `country` só no tópico geral). Gatilho confirmado no banco: o "Caçador de Pauta" repetia o mesmo cluster (Serasa/inadimplência) por falta de recência/tópico.

`chaves.SERVICOS` ganhou `exa` e `firecrawl` (cadastráveis em "Chaves e credenciais"; exigem chave do cofre, sem fallback de `.env`); o **formulário de instrumento é genérico** → os campos da Config aparecem sozinhos, **sem mexer no front**. `busca_web` renomeado para "Busca na web (Tavily)". A IA criadora aprendeu **descobrir (busca) × ler (site)**. Testes: +21 (suíte 381). **Pré-req operacional:** o maestro cadastra as chaves Exa e Firecrawl no cofre (contas externas).

---

## FASE — Capacidades avançadas de web (Firecrawl)  📋 BACKLOG (registrado 2026-06-19, não iniciar sem o sinal do maestro)
O "skill" oficial da Firecrawl revela capacidades além da leitura simples (que já temos no `ler_site_firecrawl`). Cada uma vira um instrumento futuro plugável, no mesmo molde, reusando a chave `firecrawl` do pool, sem migração e sem tocar o núcleo. O pacote CLI/skills/workflows da Firecrawl é para **agente de terminal** e **não se aplica** ao runtime do Batuta (agentes LangGraph + instrumentos HTTP) — registramos só as capacidades de API:
- **`interagir_site`** (Firecrawl `/interact`) — clicar, preencher formulário, navegar/logar numa página viva. Capacidade nova; "age" na página → trataria como **escrita** (com portão de aprovação).
- **`varrer_site`** (Firecrawl `/crawl` + `/map`) — descobrir URLs e extrair um site inteiro. **Casa com a Biblioteca** (ingerir um site como base de conhecimento da organização).
- **`ler_documento`** (Firecrawl `/parse`) — extrair texto de PDF/DOCX/XLSX. **Sobrepõe** o `extrair_texto` já previsto na Biblioteca (`docs/BIBLIOTECA-DECISAO.md`) — avaliar reuso antes de duplicar.
- **Refino opcional do `ler_site_firecrawl`:** expor `waitFor` (esperar o JS) e `timeout` para páginas muito pesadas (hoje ficam no padrão).

**Não iniciar sem o sinal do maestro.**

---

## FASE — Agente dono do fluxo (sinergia motor × markdown)  ✅ NO AR (2026-06-18, merge `17cc55b`)

**Gatilho (execução `8056ae5a`):** um agente Revisor cujo markdown manda "pedir o porquê ao reprovar" não perguntava nada — e a mensagem que ele enviava no portão **sumia das Conversas**. Diagnóstico: o agente rodava **cego** para a própria topologia (`executar_agente` não recebia as `saidas` do nó), então uma **LLM roteadora separada adivinhava** o ramo pela prosa; no portão, a resposta do humano ia direto pro roteador e **o agente não rodava de novo**. Em vários pontos o motor decidia o FLUXO no lugar do agente ("escravização de agentes", nas palavras do maestro). Decisão tomada: **o agente vira dono das decisões de fluxo; os trilhos de segurança/produto ficam intactos.**

**Princípio:** o agente decide o fluxo; o motor executa e só mantém trilhos de segurança visíveis (teto de custo, anti-injeção, horário comercial, `MAX_PASSOS`, cancelamento, debounce). Onde o motor decidia o ramo/quando-anda, o agente passa a decidir — informado das saídas e declarando a escolha.

Quatro etapas, **sem migração**, **338 testes verdes**:
1. **Outbound nas Conversas** (`mensageria/aprovacao.py::vincular_pausa`): o que o agente apresenta no portão passa a ser gravado na thread (`papel="agente"`, idempotente por `passo_id`) — antes só vivia em memória e a conversa ficava pela metade.
2. **Agente enxerga as saídas e DECLARA o ramo** (`orquestracao/agente.py`): com 2+ saídas, `executar_agente` injeta a ferramenta `seguir_para(rotulo)` (enum dos rótulos) + um apêndice de caminhos, e devolve `ramo_escolhido`. Nó de 1 saída segue direto.
3. **Cadeia usa a declaração** (`orquestracao/cadeia.py`): segue o ramo que o agente declarou, **sem chamar a LLM roteadora**; `_escolher_saida` vira **fallback** (não declarou, rótulo inexistente, automação antiga).
4. **Portão conversacional** (`mensageria/retoma.py` + `servico.py`): ao retomar um portão de nó-agente com 2+ saídas, **re-roda o agente** com a resposta da pessoa (em vez de casar a palavra). Declarou o ramo → o fluxo anda; não declarou (perguntou de volta) → segue `aguardando_humano`. Trilho anti-loop `MAX_RODADAS_GATE` (8) cai no roteador mecânico após o teto; a borda não duplica o ack quando o agente já falou pelo canal.

**Compatibilidade:** 1 saída, gate-roteador, gate só-de-tela e execuções antigas seguem pelo caminho mecânico (fallback preservado). **Núcleo tocado sob autorização explícita do maestro.** QA real só em prod (fila compartilhada): reprovar pelo Telegram e o agente perguntar o porquê (caso `8056ae5a`).

---

## FASE — Comportamento do fluxo CONFIGURÁVEL (perfil + avançado); portão obedece a mensageria  ✅ NO AR (2026-06-19, merge `582f6b1`)

**Gatilho:** o maestro percebeu que as regras do motor/mensageria **mudam conforme a natureza do fluxo** (processo interno ≠ acionar cliente externo) e que elas viviam **fixas no código ou na config do CANAL** — então todo fluxo no mesmo bot herdava as mesmas regras, e o portão (que opera por mensageria) **furava** essas regras (a pergunta do agente não saía no Telegram; a conversa ficava aberta pra sempre). Regra-mãe (memória `feedback-corrigir-cobrindo-todos-cenarios`): **corrigir cobrindo TODOS os cenários; se a capacidade é por mensageria, as regras GERAIS prevalecem — uniformemente.**

**Princípio:** o usuário configura o comportamento **por FLUXO**, com uma **fonte única** que resolve a cascata `global < canal < PERFIL do fluxo < ajustes do fluxo < nó`. As regras deixaram de ser fixas e o portão passou a ser uma conversa de mensageria de primeira classe.

Cinco etapas, **sem tocar o núcleo de orquestração** (`agente.py`/`cadeia.py` intocados além de já receberem `saidas`):
1. **Fonte única** — `Automacao.configuracao` (JSONB; migração ADITIVA `cfg00fluxo001`) + `mensageria/config.py` (`resolver_config` cascata, `PERFIS`, defaults globais, `CAMPOS`/`painel_config`).
2. **Borda lê do resolver** — `servico.py`/`sweeper.py` trocam `instrumento.configuracao` por `resolver_config` (sem regressão).
3. **Portão por canal obedece o ciclo** — `_rodar_turno`/`_turno_de_portao`: a borda entrega (corrige Telegram), `aguardando_ate` em `vincular_pausa` (corrige "aberto pra sempre"), teto = anti-loop, `portao_forma` conversa×direto, sweeper/`_passar_para_humano` cancela/estaciona a execução conforme o config; tela inalterada (retoma refatorado: `avancar_apos_gate`/`localizar_no_pausado`/`permitir_conversa`).
4. **API + UI** — `GET /config/fluxo` (perfis/botões, fonte única) + `configuracao` no CRUD; botão **"Fluxo"** na aba Automações (Tipo de fluxo + Avançado, `interface/components/automacao-builder/config-fluxo.tsx`).
5. Suíte (**352**) + tsc/eslint/build verdes → migração aditiva (aplicada antes do deploy) → deploy.

**Botões expostos** (grupos): espera & encerramento; limites (turnos/teto); atendimento (saudação/horário); portão (forma/abandono). **Internos (trilhos):** tokens, fuso, temperatura, debounce, histórico, `max_passos`/`modelo_roteador`. **Perfis:** Processo interno, Atendimento ao cliente, Disparo externo, Personalizado.

**Endurecimento pós-QA (2026-06-19), cobrindo TODOS os cenários do turno:**
- **`fix(portão)` `355e948` — honrar a decisão do agente mesmo SEM texto de chat** (gatilho: execução `fbac8111`, "o motor entra no meio e o agente não faz porra nenhuma"). A borda **descartava o turno** quando o agente decidia o ramo (`seguir_para`) **sem** escrever resposta → o fluxo travava e a conversa ficava `"aberta"` (que o sweeper nunca varre). Correção geral em `_rodar_turno`/`_turno_de_portao`: entrega no canal **só se houver texto**, mas **honra o ramo mesmo sem texto** (conta o turno, avança o fluxo e dá um retorno curto de confirmação); turno totalmente vazio → `aguardando_resposta` (o sweeper governa). Cobre os **4 desfechos**: pergunta de volta / roteia-com-texto / roteia-sem-texto / nada. O prompt do agente também passou a pedir uma confirmação curta ao chamar `seguir_para`. Regra-mãe (memória `feedback-corrigir-cobrindo-todos-cenarios`).
- **`fix(execuções)` `f8efa02` — inspeção em largura padrão + atualização AO VIVO após o portão.** A tabela de duas colunas agora ocupa a largura padrão (`max-w-[1000px]`) e a lista de passos **atualiza sozinha** depois do portão: o poll parava em `aguardando_humano` — que é uma **PAUSA** retomável por fora (Telegram), **não** um estado final — então só atualizava com refresh. Agora o poll só para nos estados **FINAIS** (`concluida`/`falhou`/`cancelada`); `aguardando_humano` continua sendo acompanhado.

---

## FASE — Duplicar um time inteiro  ✅ NO AR (2026-06-20, merge `ce420fa`)

**Pedido do maestro:** um "Duplicar time" análogo ao "Duplicar automação", para criar **variações** de um time que já funciona. Decisões de produto: **escopo = mesma organização** e **a cópia HERDA a memória da IA companheira**.

`POST /times/{id}/duplicar` (schema `DuplicarTime {nome}`, **acesso admin** — duplicar cria um time) + módulo isolado [`cerebro/duplicacao_time.py`](cerebro/duplicacao_time.py), tudo numa transação atômica, **sem migração e sem tocar o núcleo** (reusa `grafo.normalizar`/`validar_cadeia`/`agendador`):
- Recria o **grafo de propriedade** (agentes, instrumentos, cinto N:N, automações) com **ids NOVOS** e **REMAPEIA as referências internas** da `cadeia` — `ref` de agente e `aprovacao.instrumento_id` —, cobrindo o **formato legado** (em que o `id` do nó é o próprio agente_id, e `inicial`/`destino` também). Normaliza→remapeia→normaliza→valida contra o time NOVO.
- **Segredos:** inline copiado direto (mesma `COFRE_CHAVE_MESTRA`); credencial nomeada mantém a referência (mesma org). **Canais (Telegram/WhatsApp) nascem DESCONECTADOS** — sem token, sem `webhook_secret`, sem credencial — para dois times nunca brigarem pelo mesmo bot (um webhook por bot).
- **Memória da IA herdada:** cria uma `ConversaCriacao` nova amarrada ao time novo (copia o histórico) e duplica as `MemoriaProjeto` ("decisões lembradas").
- **Automações nascem inativas** (não disparam em dobro); **runtime NÃO é copiado** (execuções, conversas de atendimento, uso) — cópia limpa por construção.
- **Front:** botão+modal "Duplicar" na lista de times (`interface/app/organizacoes/[id]/times-cliente.tsx`), molde do duplicar-automação; no sucesso navega para o time novo.

**393 testes** (`test_duplicar_time.py`, 12: grafo completo, remapeamento novo+legado, segredo copiado, canal desconectado, memória herdada, runtime não copiado, deep-copy isolado, matriz de acesso). tsc/eslint/build verdes. QA ao vivo em prod: duplicar um time → conferir agentes/instrumentos/automação + "decisões lembradas" + canal "a conectar".

**Pós-QA (merge `57b1b4e`, 395 testes):** o maestro duplicou um time e a aprovação do portão "travou". Diagnóstico (exec `4f913949`): NÃO foi a duplicação (remapeamento correto, portão no canal do próprio time) — foi **reuso do mesmo bot** do time original no canal da cópia. Um bot do Telegram entrega para UM webhook só, então a resposta "aprovado" caiu no canal do time ORIGINAL (tratada como conversa) e a execução copiada nunca retomou. **Correção de raiz (cobre todos os cenários):** `ativar-canal` ([rotas/mensageria.py](cerebro/rotas/mensageria.py)) agora **recusa (409)** conectar um canal cujo bot já é usado por outro instrumento, com recado para criar um bot próprio — um time duplicado é obrigado a ter o seu bot. Borda, sem migração.

---

## FASE — Memória do agente (fichas por assunto, governadas pelo markdown)  📋 APROVADA — FASE FUTURA (não iniciar sem o sinal do maestro; ideação 2026-06-20)

**Dor:** os fluxos estão ficando complexos e surge a demanda de **agentes que lembram**. Hoje cada execução é **stateless** (comportamento 100% dos markdowns; nada de runs passados — [agente.py:196](cerebro/orquestracao/agente.py#L196)). O que existe é de outra natureza: `memorias_projeto` é da **IA criadora** (notas sobre o time para conversar com o consultor) e a **Biblioteca** são documentos da org que o agente *lê*. Falta: **o agente aprender com o próprio trabalho** (ex.: lembrar de um cliente já atendido, não repetir pauta).

**Decisões (ideação com o maestro):** dor = **continuidade** ("não se repetir / lembrar do cliente"); **controle no MARKDOWN** (a política — quando pesquisar, criar vs. editar, o que é relevante — é escrita pelo consultor no markdown; sem portão de aprovação separado; coerente com [[feedback-sem-prompt-base-agentes]]); escopo **por agente**; formato **ficha por assunto** (upsert: cria ou edita, mantém enxuto); supervisão por **tela** (ver/editar/apagar) como rede de segurança.

**Desenho:** memória = capacidade ligada por agente (interruptor `agentes.memoria_ativa`), exposta como **duas ferramentas injetadas no runtime** (mesmo molde do `seguir_para`, [agente.py:222](cerebro/orquestracao/agente.py#L222), **sem tocar o motor de cadeia**): `pesquisar_memoria(assunto)` e `registrar_memoria(assunto, conteudo)` (upsert por (agente, assunto)). Não vira instrumento de cinto porque `executar(config,args)` não conhece o agente nem tem sessão; o `executar_agente` já tem o `agente` em mãos. Tabela nova **`memorias_agente`** (molde de `memorias_projeto`; FK `agente_id` CASCADE) + módulo `cerebro/memoria_agente.py` (funções puras reusadas por ferramentas/rotas/tela). **Migração aditiva, núcleo intocado.** A duplicação de time **não** copia as memórias (runtime/aprendizado), só o interruptor.

**Fora da v1:** busca semântica/embeddings (começa por assunto, lógica "destilada"), memória de time/org, teto/expiração automática, portão de aprovação. **Decisões e desenho registrados na memória do projeto** (`project_memoria-do-agente-fase-futura`); ao retomar, reabrir o plano de 7 passos a partir daí.

---

## FASE — Redesenho da tela de login (split logo+form / mascote)  ✅ NO AR (2026-06-20, merges `8ca6e1e`+`2549593`)

**Pedido do maestro (mockup):** a `/login` deixou de ser uma coluna central (símbolo SVG provisório + texto + form) e virou **duas colunas full-height** ([app/login/page.tsx](interface/app/login/page.tsx)): **esquerda** (`bg-background` = #fafaf7) com a logomarca `public/logo-lockup.png` + o formulário (`LoginCliente`, lógica de auth intocada); **direita** (`bg-card` = #ffffff) com o mascote `public/mascote-completo.png`. `next/image`; no mobile empilha (mostra logo+form, oculta o painel do mascote). Tokens de cor batem exatos com os hex pedidos (`globals.css:68,70`).

**Fix pós-deploy (`2549593`):** as colunas encolhiam para o conteúdo — quando deslogado o `layout.tsx` põe o `children` direto no `<body>` que é `flex md:flex-row`, e o `<main>` (item flex) não crescia. `flex-1 w-full` no `<main>` faz as duas metades ocuparem 50/50 da largura total. Só frontend, sem migração, sem tocar auth. tsc/eslint/build verdes.

---

## FASE — Instrumentos de Instagram (publicar, métricas, comentários)  ✅ NO AR (2026-06-21, merges `f2f7617`+`7d07ab8`+`4fe3794`)

Pedido do maestro (passou na frente da fila). API = **"Instagram API with Instagram Login"** (`graph.instagram.com`): conta Profissional + app na Meta no fluxo de **casos de uso** → **"Gerenciar mensagens e conteúdo no Instagram"** → config ativa **"API com login do Instagram"** (NÃO usar "Outro", que a Meta vai descontinuar). Conexão por **token colado + renovação automática** (decisão do maestro), NÃO o OAuth de redirecionamento — o token do painel já nasce de 60 dias. Entregue em 4 fases, **sem migração** (o `expira_em` da caixa-forte já existia reservado), **núcleo intocado**, **434 testes**:

- **F0 — Fundação:** novo tipo de credencial **`instagram`** (`tipos_credencial.py`): campos `token` (segredo) + `ig_user_id` (identidade, **auto-preenchido** via `/me`). `cerebro/instagram_tokens.py` (puro, httpx/`FalhaInstrumento`): `validar(token)` (GET /me → ig_user_id) e `renovar(token)` (GET /refresh_access_token, `ig_refresh_token`, **sem app secret**). `credenciais_cofre.gravar_com_validacao_ig` (valida no salvar, preenche o id, fixa `expira_em≈60d`) + `gravar_token_renovado` (escrita pelo SISTEMA). As 4 rotas de credencial traduzem token recusado em **422 claro**.
- **F1 — Renovação automática:** `agendador.renovar_tokens_instagram` (job diário 03:30 BRT, `id=instagram_token_refresh`): renova as credenciais `instagram` com `expira_em` em ≤10 dias; commit por credencial (falha isolada). Reusa o `BackgroundScheduler` (1 réplica).
- **F2 — Publicar + métricas:** `publicar_instagram` (foto/Reels/Stories/carrossel; 3 passos contêiner→FINISHED→media_publish; **acao_irreversivel** → portão; **toda falha NÃO-retentável** porque `media_publish` não é idempotente e a orquestração reexecuta em falha retentável). `instagram_insights` (leitura: conta + posts recentes com curtidas/comentários). **A legenda NÃO usa `campo_mensagem`** (é conteúdo publicado, não mensagem de canal — alinha ao WordPress).
- **F3 — Comentários:** `instagram_ler_comentarios` (leitura) + `instagram_responder_comentario` (responder/ocultar/reexibir/apagar; irreversível → portão; falha não-retentável).

Todos reusam a credencial `instagram` (Config com `token`+`ig_user_id`, casamento validado por `test_tipos_credencial`). **URL de mídia pública aceita pronta** (sem Supabase Storage no MVP). **Caveat (a própria Meta avisa):** rastrear **hashtags e insights avançados** (alcance/impressões) exige o setup **"API com login do Facebook"** (`graph.facebook.com`) — sub-fase futura. **Pré-reqs manuais do maestro:** permissões + conta como **Testador** (aba Funções) + **Gerar token** no painel; depois criar a credencial "Instagram" no Batuta e pôr os instrumentos no cinto do agente.

**Fase 4 — DM mão dupla (canal como o Telegram): FORA DE ESCOPO por ora** (decisão do maestro 2026-06-21). É a mais cara (webhook da Meta + assinatura `X-Hub-Signature-256` + **app PUBLICADO** + integração da camada de mensageria + App Review para terceiros). Plano completo preservado em `~/.claude/plans/`.

---

## FASE — Pós-QA do Instagram + Supabase Storage  ✅ NO AR (2026-06-21, sem migração, núcleo intocado)

QA ao vivo da publicação revelou e corrigiu (tudo no ar):
- **Dropdown de instrumentos agrupado por categoria** (`categoria` em cada `TipoInstrumento` + `<optgroup>` no `formulario-instrumento`; grupos Instagram/Web/Conteúdo/Mensageria/Sites e blogs/Integrações e dados).
- **IA criadora ensinada a rotina de ação irreversível com aprovação** (`criacao/prompt.py`): um nó-portão APRESENTA e ESPERA — nunca executa; jamais pôr o instrumento de escrita no MESMO nó do portão; estrutura `[preparar+apresentar → gate] → [executar sem gate]`; publicar exige URL pública + legenda decididas ANTES.
- **Fix no motor** (`retoma._retomar_conversando_tela`): o portão-conversa repassava ao próximo nó o texto curto da rodada ("aprovado!") em vez do conteúdo APRESENTADO (URL+legenda) → o publicador ficava sem a mídia ("concluída" sem postar). Agora repassa o apresentado.
- **Supabase Storage** (resolve a limitação conhecida da implantação): `gerar_imagem`/`gerar_pdf` sobem para um **bucket público `arquivos`** (`arquivos.salvar()`; cria o bucket sozinho; reusa `SUPABASE_URL`+`SUPABASE_SERVICE_ROLE_KEY`; fallback p/ disco em dev) → URL **pública e durável** (o `/arquivos` do Railway era efêmero → "Not Found" → a Meta não baixava a imagem).

---

## FASE — Montar imagem (composição a partir de fotos)  ✅ NO AR (2026-06-22, validada ao vivo — arte profissional em 211s)

Pedido do maestro: gerar a arte de um post com a FOTO dele (fundo transparente) + modelos de estilo + tema. Novo instrumento **`montar_imagem`** (`cerebro/instrumentos/montar_imagem.py`), aditivo, **sem migração**, núcleo intocado:
- Usa o endpoint de **EDIÇÃO/composição** da OpenAI (`/v1/images/edits`, **multipart**): baixa as URLs e **anexa os BYTES** em `image[]` (até 16; a 1ª é a mais preservada). gpt-image-2 / qualidade alta.
- **GENÉRICO de propósito:** args = `prompt` + `imagens_url` (em ordem). O instrumento NÃO sabe o que é "foto da pessoa" vs "modelo" — **o elo vive no MARKDOWN do agente** (decisão do maestro: instrumento burro, inteligência no markdown; senão precisaria 1 instrumento por tipo de montagem). A IA criadora foi ensinada a escrever esse elo (`criacao/prompt.py`).
- Catálogo (`gerar_imagem.CATALOGO_IMAGEM`) ganhou **4:5** (1024x1280 / 1536x1920, feed do Instagram) + 5:4.
- **Timeout do edit = 600s** (`TIMEOUT_EDICAO_S`): montagem de 9 imagens em qualidade alta leva ~3,5 min; o teto de 120s herdado do `gerar_imagem` MATAVA toda tentativa (3 retentativas × 2 chamadas do agente ≈ 13 min sem arte). Timeout agora é falha **NÃO-retentável** (não re-sobe os MB).
- Contabilizado como instrumento pago (`medicao_instrumentos.TIPOS_PAGOS`). Fotos por URL hoje; quando a **Biblioteca** existir, virão de lá.
- **Vigia** `cerebro/diagnostico_imagem.py`: grava no Storage (nome fixo por instrumento) EXATAMENTE o que vai pra OpenAI + bytes anexados por imagem (prova anexo vs URL); leitura via `scripts/ler_diagnostico_imagem.py`. Ligado em `montar_imagem` + `gerar_imagem`.

---

## FASE — Robustez de execução: sweeper de presas + botão Cancelar  ✅ NO AR (2026-06-22, sem migração)

Gatilho: uma execução ficou presa em `em_andamento` para sempre (worker travado SEM restart do processo; o `fila._recuperar_orfas` só roda no BOOT).
- **Sweeper periódico** `fila.recuperar_execucoes_presas` (agendador `IntervalTrigger` 120s, `id=execucao_sweeper`): execução `em_andamento` sem progresso além de 15 min (**heartbeat** = `max(iniciada_em, último passo concluído)` — NÃO mata cadeia longa que progride) vira `falhou`. Complementa o `_recuperar_orfas` do boot.
- **Botão "Cancelar execução"** na tela de DETALHE (`inspecao-execucao.tsx`; só estado não-final + `podeOperar`). O endpoint `POST /execucoes/{id}/cancelar` já existia — faltava expor onde o usuário acompanha (antes só na lista global).
- `scripts/inspecionar_exec.py` = dump read-only de execução (passos + cinto), p/ diagnóstico.
- **Causa raiz ✅ RESOLVIDA** (2026-06-22, merge `57df437`): `construir_modelo` (`orquestracao/llm.py`) agora põe **`timeout=TIMEOUT_IA_S` (300s)** no ChatAnthropic/ChatOpenAI/ChatGoogleGenerativeAI — generoso para uma geração cheia (até MAX_TOKENS num modelo lento), mas FINITO: a conexão pendurada vira falha rápida em vez de travar o trabalhador. O sweeper segue como backstop.

---

## FASE — Webhook: criadora correta + URL por automação  ✅ NO AR (2026-06-22)

Gatilho: a IA companheira dava info errada sobre webhook (dizia gatilho "manual" quando já era "webhook"; mandava procurar a URL no painel do time, onde ela NÃO fica). O webhook **já é por automação** no backend (`POST /webhooks/automacoes/{id}`) e a URL **já aparece na tela da automação** (nó Gatilho → drawer) — faltava a criadora saber e o conceito ficar claro:
- `criacao/prompt.py`: seção **"Gatilhos e webhook"** — gatilho é **POR AUTOMAÇÃO** (não do time; um time tem várias); não afirmar o tipo de memória (conferir no retrato do time); a URL é por automação, aparece pronta ao abrir a automação (nó Gatilho), só dispara se ativa.
- Dashboard do time: **removido o card "Gatilho"** do Início (com 2+ automações um card único não tem sentido — qual URL mostraria?). Gatilho/webhook vivem só na aba Automações → nó Gatilho → drawer.
- **Lição registrada na memória:** PERGUNTAR ao maestro antes de criar/alterar UI (eu pus a URL num card da home por conta própria — erro). Backend/bug segue direto; UX/UI não.

---

## FASE — Consolidação da navegação: tudo do time em `/times/[id]` + sidebar em 2 blocos  ✅ NO AR (2026-06-22, merge `f33c8d1`, 100% frontend, sem migração)

Gatilho: o maestro se confundia porque os mesmos dados de um time apareciam **tanto nas abas de
`/times/[id]` quanto em páginas independentes de topo**. A URL do webhook, em particular, só vivia na
página solta `/automacoes/[id]` — que ele não achava. Decisão: **tudo que diz respeito a um time vive
nas abas de `/times/[id]`; páginas independentes com dados de time deixam de existir.**

- **URL do webhook no lugar natural:** no drawer do nó **Gatilho** (aba Automações). `automacoes-cliente.tsx`
  passa a URL real `{URL_CEREBRO}/webhooks/automacoes/{id}`; `automacao-builder/inspector.tsx` renderiza
  com `UrlCopiavel` (botão copiar). Antes só vivia na página solta.
- **Removidas as páginas independentes** `app/execucoes/` (lista global cross-time) e
  `app/automacoes/[id]/` (detalhe avulso). Execuções e automações se acessam pelas abas do time
  (`/times/[id]/execucoes`, `/times/[id]/execucoes/[execId]`, `/times/[id]/automacoes`). No editor da
  automação, link **"Ver execuções"** → aba Execuções do time. (NÃO existe `/agentes` nem `/automacoes`
  raiz.)
- **Sidebar em DOIS BLOCOS** (`components/sidebar.tsx`): **Organização** (Início → sub-links *Gerenciar
  Times* `/organizacoes/[id]` e *Gerenciar Organizações* `/organizacoes`; lista de Times; Biblioteca;
  Uso e custos; e — só admin da org — Acesso e papéis, Chaves e credenciais, **Configurações da
  organização**) e **Consultoria** (Chaves/Uso/**Configurações da consultoria**), bloco **visível só ao
  `admin_consultoria`**. "Criar com a IA" mantido no topo; item "Execuções" global removido.
- **Configurações split por escopo:** "da organização" reusa `/configuracoes` (relabel); "da
  consultoria" é a nova `app/configuracoes-consultoria/page.tsx`. Ambas placeholders `AreaEmBreve`.
- **`/criar`:** o formulário "Criar um time novo" agora vem **antes** da lista de conversas (não
  precisa rolar até o fim).
- **Breadcrumb** (`cabecalho-conteudo.tsx`): rótulos casados com a sidebar; corrigido bug pré-existente
  (`/uso-consultoria` caía em "Uso e custos").
- Endpoints do backend e dados intocados (só a casca de página saiu). `npm run build` + `eslint` verdes.
- **Docs atualizados:** `docs/ARQUITETURA.md` §9 (telas/sidebar) e `PRODUTO.md` §8 (o time é um espaço
  fechado — tudo dele se gerencia na própria área).

---

## FASE — Parede de aprovação vira config GLOBAL da org + fim do switch por instrumento  ✅ NO AR (2026-06-22, merge `4407e79`, migração aditiva `prd00parede01`)

Gatilho: o maestro questionou a config de portão que aparecia em TODO instrumento ("Aprovação humana
antes de agir"). Estudo confirmou DOIS portões que se confundiam: (A) o switch por instrumento — que
NÃO pausava nada, só alimentava a parede de ativação — e (B) o portão do NÓ (o que realmente pausa,
`cadeia.py` lê `no.get("gate")`). Decisão: remover (A) e tornar a parede uma config GLOBAL da org.

- **Coluna `organizacoes.parede_ativacao`** (Boolean default TRUE; migração aditiva `prd00parede01`).
  Default TRUE = comportamento atual preservado.
- **`portao_ativacao.validar` = PONTO ÚNICO**: se a org desligou a parede → retorna `[]` (ativa sem
  exigir nó-portão). Cobre a rota de ativação E a IA criadora numa só mudança.
- **Fonte única de irreversibilidade** `instrumentos.acao_irreversivel(tipo, config)`; removido
  `exige_portao` e o override `exige_aprovacao` do fluxo. Coluna `instrumentos.exige_aprovacao` FICA
  no banco (ignorada) — rollback trivial, sem migração destrutiva. Webhook segue reversível.
- **Rota** `PUT /organizacoes/{id}/parede-ativacao` (admin; auditada `organizacao.parede_ativacao`).
- **Front:** instrumento sem o dropdown de aprovação; **nova página org-scoped**
  `/organizacoes/[id]/configuracoes` (1ª config global da org) = switch da parede (com aviso de risco)
  + **seletor de modelo de conversa MOVIDO de Chaves para cá** (pedido do maestro). Sidebar/breadcrumb
  apontam pra ela; removida a `/configuracoes` plana.
- O **portão do nó (B)** segue intacto para pausar manualmente onde quiser.
- 465 testes verdes; build + eslint + ruff (arquivos tocados) limpos. **Docs:** PRODUTO §19 + ARQUITETURA §9.

---

## FASE — Edição in-place do time + seletor de ícone buscável  ✅ FEITA (2026-06-22, branch `lapis-editar-agente`)

Objetivo do maestro: **editar o time inteiro navegando o mínimo possível entre abas** — flagrou um
problema, corrige ali mesmo. 100% frontend; sem backend/banco/endpoint novo (reusa os drawers e
endpoints existentes). Validado ao vivo.

- **Lápis (agente) + badges do cinto (instrumentos), em 3 lugares:** o **nó da automação**, o **card
  da aba Agentes** e a **linha do passo da inspeção de execução**. O lápis abre o `DrawerAgente`
  flutuante; cada instrumento do cinto vira **badge clicável** que abre o `DrawerInstrumento` — tudo
  sem trocar de aba. Badges com limite + "+X mais" (abre o agente = cinto completo). As páginas
  dessas telas passaram a carregar o cinto de cada agente + o catálogo de tipos para alimentar os
  drawers. Padrão visual unificado (linhas com borda, ícone na cor da marca); na execução o lápis é
  um ícone discreto à direita (onde ficava o ícone de ferramenta, agora removido por redundância).
- **UX do drawer de instrumento (compartilhado):** ao **Salvar** NÃO fecha mais sozinho (fica aberto
  até fechar à mão); ao criar, passa de "criar" para "editar" o recém-criado (`onSalvou` devolve o
  instrumento). **Conectar canal** também parou de fechar: a aba Instrumentos não remonta mais a si
  mesma a cada edição (removida a `key` de versão que zerava o estado local; a lista atualiza pelas
  props no `router.refresh`).
- **Seletor de ícone do instrumento → dropdown buscável:** fechado ocupa 1 linha (mostra o ícone
  atual); abre no clique/foco; filtra ao digitar; fecha no clique-fora/Esc. Catálogo curado ampliado
  de **62 → 371** ícones. **A busca alcança a biblioteca INTEIRA do FA-free** (~2.500): seção "Mais
  da biblioteca" carregada **sob demanda** (`lib/icones-completo` via `import()` dinâmico em
  `lib/icones-externos`, singleton) → **chunk separado (~1,5 MB)** que só baixa quando se busca ou
  renderiza um ícone fora dos curados. Bundle principal segue leve (tree-shaking dos curados);
  `IconeInstrumento` resolve curado na hora e os demais sob demanda (Wrench enquanto carrega).
  openai/claude/hugging-face entraram nos curados.
- tsc + eslint + build verdes a cada passo.

---

## FASE — IA de conversa lida com credenciais nomeadas  📋 BACKLOG (anotado 2026-06-21, não iniciar sem o sinal do maestro)

Gatilho: na entrega dos instrumentos de Instagram, a IA criadora **monta** o agente/automação e
**aplica o portão certo** (deriva de `acao_irreversivel`, sem lista fixa), mas **não pluga o
token** — por princípio, ela nunca toca em segredo. O token fica **"pendente"** e o humano finaliza
na tela do instrumento (cola o token OU aponta para a credencial nomeada já criada). Vale para
QUALQUER instrumento com segredo, não só Instagram. Duas partes:
1. **Barato:** expor `tipos_credencial_aceitos` (e talvez `categoria`) no catálogo da criadora
   (`criacao/ferramentas.py::catalogo_de_instrumentos`) → ela orienta "use uma credencial do tipo X".
2. **Maior:** a criadora APONTAR o instrumento para uma credencial existente — `configurar_instrumento`/
   `editar_instrumento` aceitarem `credencial_id`; `criacao/servicos.configurar_instrumento` validar
   (reusar `rotas/instrumentos._validar_credencial`) e setar; dar à criadora visão das credenciais da
   org (tool `listar_credenciais` ou no snapshot do `ver_time`); atualizar `criacao/prompt.py`.
   **Só REFERENCIA por id — não viola a regra de a IA não tocar segredo.** Resultado: agente de
   Instagram (ou WordPress/Telegram) sai 100% pronto, sem o passo manual de ligar a credencial.

---

## FASE — Instagram self-serve: OAuth "Conectar Instagram"  ✅ NO AR (2026-06-30, deploys `2d9c937` + `e5360f9`, sem migração, núcleo intocado)

Gatilho: o instrumento de Instagram só servia contas adicionadas como **testador** (app em modo dev; teto ~50 + token colado por conta). Ao seguir o App Review, o formulário da permissão `instagram_business_basic` escancarou o muro: o screencast/descrição exigem que o **analista conecte a PRÓPRIA conta** por um fluxo no app — que o token colado não tem. Decisão do maestro: **construir o OAuth agora** (o teto de testadores estoura rápido).

**Feito (validado ao vivo em prod):** `cerebro/instagram_oauth.py` (monta a URL de consentimento e troca `code`→token curto→token de 60 dias; `www.instagram.com/oauth/authorize`; reusa `/me` e a política de falha do `instagram_tokens`) + `cerebro/rotas/instagram.py` (`POST /organizacoes/{id}/instagram/iniciar` operador+, devolve a URL com `state` cifrado pelo cofre; `GET /instagram/oauth/callback` PÚBLICO, valida o `state` via `cofre.decifrar_temporario` [Fernet+TTL], revalida o papel, faz **UPSERT** da credencial `instagram` da org — reconexão da mesma conta atualiza, não duplica — e redireciona de volta) + botão **"Conectar Instagram"** no formulário de credencial (só na org; colar token segue como alternativa). `force_reauth=true` na URL (deixa ESCOLHER a conta, não reusa a sessão do navegador). Reusa o tipo de credencial `instagram`, o cofre e o job de refresh do agendador. Config em produção: **redirect URI** na Meta (card "4. Configurar o login da empresa") + **3 vars no Railway** (`INSTAGRAM_APP_ID` = ID do app do IG `1726589371819141`, ≠ App ID Meta; `INSTAGRAM_APP_SECRET`; `INSTAGRAM_REDIRECT_URI`). **Teste ao vivo:** 2 contas conectadas só pelo OAuth (@jmanfrini atualizou a credencial existente; @arrastafaca, testadora nova) + gerar imagem→publicar com sucesso.

**Falta:** completar e enviar o App Review (fase própria abaixo) — o OAuth destrava justamente o screencast do fluxo de conexão que o analista precisa reproduzir. Ver `project-instagram-oauth-app-review-fase-futura`.

---

## FASE — Aprovação pela tela não perde o conteúdo apresentado  ✅ NO AR (2026-06-23, merge `9bce290`, sem migração)

Gatilho: exec `132bcaa6` publicou no WordPress a fala do agente ("Artigo aprovado! Seguindo…") em vez do artigo. Raiz (mesmo bug recorrente do fix de 2026-06-21, ainda não fechado): `retoma._retomar_conversando_tela` usava a heurística `veio_de_canal` — ao aprovar, o agente-portão também confirmava pelo Telegram, e a borda descia essa confirmação no lugar de `ultimo.saida` (o artigo apresentado). Pelo Telegram funcionava (o caminho por canal repassa o histórico); só a TELA quebrava. Correção: unifica os 4 caminhos — pós-aprovação segue SEMPRE `ultimo.saida` + a resposta. Teste de regressão `test_tela_aprova_e_agente_confirma_no_canal_nao_perde_o_conteudo`. Lição [[feedback-bug-recorrente-fonte-de-verdade]].

## FASE — IA companheira diagnostica execuções que deram problema  ✅ NO AR (2026-06-23, merge `8424263`, sem migração, núcleo intocado)

Objetivo: o maestro pergunta NO APP por que uma automação falhou/parou, sem ter que abrir o projeto. Novo `cerebro/diagnostico_execucao.py` (analisador puro de LEITURA, fonte única) reúne os fatos e roda verificações DETERMINÍSTICAS → `avisos[]` (`ia_sobrecarregada` / `falha_instrumento` / `portao_sem_entrega` [agente do portão sem canal no cinto] / `canal_sem_token` / `aprovacao_pendente_normal` / `webhook_disparou_alvo` [segue 1 hop, mesma org] / preso / …); nunca vaza segredo, trunca textos. 2 tools em `criacao/ferramentas.py` (`listar_execucoes` + `diagnosticar_execucao`, escopadas ao time) + seção no `prompt.py` (liderar pelos avisos, traduzir sem jargão, seguir o webhook_alvo, aplicar a correção do próprio time com as tools de edição que já tinha). `scripts/inspecionar_exec.py` imprime os mesmos avisos. Validado em prod (read-only): `2ca7768e`→hop→`ef903d73`. Decisões do maestro: explica + corrige o que dá (sem reexecutar); cross-team só mesma org + resumo.

## FASE — Resiliência a 529 (retentativa com backoff nas chamadas de IA)  ✅ NO AR (2026-06-24, merge `d8552df`, sem migração)

`construir_modelo` (`orquestracao/llm.py`, ponto único de toda construção de modelo) passa a fixar `max_retries=6` nos três provedores (Anthropic/OpenAI/Google) → numa sobrecarga transitória (529/5xx/429) a chamada faz retentativa com backoff (~20-40s, abaixo do timeout de 300s e do sweeper de 15min), em vez de derrubar a execução. Fecha a pendência da exec `132bcaa6`.

## FASE — Ação CANCELAR no portão de aprovação (tela + Telegram)  ✅ NO AR (2026-06-24, merge `5c69613`, sem migração)

O portão só tinha aprovar/reprovar (reprovar faz loop/refaz); faltava ENCERRAR para quem, depois de reprovar N vezes, não quer mais tentar. Insight de desenho: cancelar **não** é uma 3ª saída do grafo (toda automação teria que desenhá-la; no canal conversacional o AGENTE escolheria a saída, quando quem decide é o humano) — é uma **ação reservada da BORDA**, terminal, detectada de forma determinística ANTES do agente/roteador, uniforme nas duas superfícies, reusando o caminho de abandono que já leva uma execução pausada a `cancelada`. Helper ÚNICO `aprovacao.cancelar_execucao` (cancela + desvincula a conversa; idempotente; sem commit) usado pela rota `/cancelar` (corrige lacuna: agora desvincula a conversa do portão) e pelo canal (`COMANDOS_CANCELAR={"cancelar","/cancelar"}` no 1º statement de `_turno_de_portao`; match da mensagem INTEIRA por igualdade → feedback "cancela o 3º parágrafo" não dispara; ack ⛔, sem rodar o agente). Front: botão "Cancelar o fluxo" no `PainelAprovacao`. Permissão: tela = operador+, canal = aprovador configurado.

## FASE — O instrumento é a verdade: destino do Telegram configurado prevalece sobre o markdown  ✅ NO AR (2026-06-25, merge `b8d44ca`, sem migração, núcleo intocado)

Gatilho: exec `d179dd90` — o agente-portão mandou a aprovação para o chat escrito no MARKDOWN, divergente do destinatário configurado no instrumento, sem nada na tela avisando qual prevalece. Levantamento (pente fino nos **18 instrumentos**): existe **um só** ponto de sobreposição Config↔Args em todo o catálogo — `enviar_telegram` (`destinatario_padrao` vs `destinatario`); nos outros 17, a config (conexão/credencial/ajuste) e os args da IA (`mensagem`/`prompt`/`consulta`/`sql`/`url`, que nem aparecem no formulário) são complementares. Correção (decisão do maestro — **o instrumento é a verdade, não o markdown**): (1) `enviar_telegram.executar` inverte a precedência → `destino = config.destinatario_padrao or args.destinatario` (config vence; só cai no args quando o campo está vazio). Seguro no modo conversacional — a borda usa `telegram.enviar`, que monta a config com destino VAZIO e passa o contato em args (verificado em `servico.py` + `telegram.py`). Campo reformulado ("Destinatário"). (2) Front: aviso geral (`Aviso variant=info`) acima dos campos de **todo** instrumento — "o que você preenche aqui vale; o agente não troca pelo texto dele". Novo `test_enviar_telegram.py` (config-vence / fallback / conversacional / sem-destino). Follow-up registrado: "quem recebe o Telegram" ainda mora em dois lugares (destino do envio = instrumento; aprovador do portão = nó) — candidato a unificar (derivar o aprovador do portão do destinatário do instrumento) [[feedback-bug-recorrente-fonte-de-verdade]].

## FASE — Páginas legais + submissão do app à Meta (App Review do Instagram)  🟡 EM ANDAMENTO (2026-06-26)

**Objetivo:** publicar o app de Instagram na Meta para atender **contas REAIS de clientes** (Acesso Avançado), o que exige passar pela **Análise do app (App Review)**. Hoje as permissões estão em Acesso Padrão (só contas de teste).

**Feito:**
- **Páginas legais públicas** (merge `2fb532b`, 100% frontend): `/privacidade`, `/termos`, `/exclusao-de-dados` em batuta.team (Server Components estáticos; casco `interface/components/pagina-legal.tsx` com rolagem própria — o `<body>` deslogado é `h-dvh overflow-hidden`; constantes do controlador em `interface/lib/legal.ts`; rotas liberadas em `lib/supabase/proxy-sessao.ts`; rodapé de links na `/login`). Conteúdo reflete o inventário REAL de dados (Supabase, Railway, IA Anthropic/OpenAI/Google, Tavily/Exa/Firecrawl, Resend, Telegram, Meta/Instagram; Whisper não retém áudio cru; segredos cifrados). Exclusão de dados = **página de instruções** (sem callback OAuth por ora). **Ressalva:** modelo factual, não é aconselhamento jurídico.
- **Controladora alinhada à JMF** (merge `c551ca6`): o app foi **verificado na Meta** sob **JMF TREINAMENTOS E CONSULTORIA LTDA - ME** (CNPJ `56.923.834/0001-23`), o CNPJ próprio do maestro — não a Lure (1º dado informado). A controladora citada na política **tem de bater** com a empresa verificada, senão a Meta reprova por divergência → as 3 páginas foram trocadas de Lure→JMF (basta editar `lib/legal.ts`).

**Estado na Meta (App Review) — 🟢 QUASE ENVIANDO (atualizado 2026-07-07):** empresa **VERIFICADA** (JMF); app Live. **Ambiente de teste montado** (org "Testes Meta"; login do analista criado por script — `scripts/criar_login_analista.py`, papel operador, verificado por login real; @arrastafaca conectada via OAuth; agente com os 4 instrumentos de Instagram + 3 automações "Instagram - Postar/Responder/Métricas"). Na tela "Enviar para a análise do app": **Verificação, Configurações, Tratamento de dados e Instruções para o analista** ✅; **Uso permitido** com as **4 descrições + 4 vídeos** subidos (basic=conectar credencial, content_publish=publicar, manage_insights=métricas, manage_comments=ler+responder). Falta só o registro das **2 chamadas de API de teste** (insights + comentários) — já feitas ao rodar as automações, mas a Meta leva **até 24h** para marcar `1/1`; aí o "Enviar para análise" acende. O card de comentários tem exigência extra (vídeo com usuário comentando + resposta; descrição com link do post + palavras-chave). Guia com todos os textos/roteiros/instruções finais em `Instruções_meta.md`.

**Tratamento de dados (preenchido):** controlador = **JMF** (Brasil); operadores = Supabase + Railway + Anthropic + OpenAI (EUA); sem repasse a autoridades; posturas de minimização/legitimidade marcadas; URLs de privacidade + exclusão de dados.

**Relacionado / fases FUTURAS (pós-aprovação):** o **"Conectar Instagram" (OAuth)** destrava o screencast do fluxo de conexão. Dois gaps da IA criadora descobertos ao montar o time de teste, a revisitar depois: (1) dar-lhe ferramenta p/ **várias automações por time** — hoje o tooling é 1-por-time via `_obter_ou_criar_automacao`, embora DB **e** UI ("Nova automação") suportem N; (2) **webhook de comentários em tempo real** — hoje o agente só sabe de comentário sob demanda/agendado (sem push; é preciso rodar a automação de responder).

---

## FASE — Claude Sonnet 5 (opção + novo padrão da IA de conversa)  ✅ NO AR (2026-06-30, deploy `4a0a5e4`, sem migração)

A Anthropic lançou o **Claude Sonnet 5** (`claude-sonnet-5`) — o Sonnet mais agêntico, perto do Opus 4.8 por bem menos custo (US$3/15 vs US$5/25). Entrou no catálogo de modelos (conversa + agentes: `orquestracao/modelos_ia.py` + `interface/lib/modelos.ts`, listas espelhadas) e virou o **PADRÃO da IA de conversa** (`MODELO_CRIADORA` em `criacao/loop.py`, era Opus 4.8; quem escolheu Opus à mão continua). A IA criadora passou a recomendá-lo aos agentes que monta (`criacao/prompt.py`). Como é da geração "adaptive thinking" (igual ao Opus 4.8), REJEITA `temperature` → entrou em `MODELOS_SEM_TEMPERATURA` (`orquestracao/llm.py`). Preço no /uso mantido no padrão (US$3/15, resolve pela família "sonnet"; o introdutório US$2/10 até 31/08 super-estima ~33%, aceitável num painel informativo). Prova real: chamada à Anthropic no `claude-sonnet-5` respondeu OK (sem 400). Decisões do maestro: entrar como opção **e** virar o padrão da conversa; preço padrão (sem manutenção).

## FASE — Canal de Telegram: crachá (webhook_secret) em coluna + status/alcance na tela  ✅ NO AR (2026-07-06, deploys `2428d48` + `ba17982`, migração aditiva `whk00secret001`)

Gatilho (recorrente): o maestro tinha de **RECONECTAR o canal a cada ajuste**. Investigação (`inspecionar_exec.py` + leituras read-only do banco de prod + `getWebhookInfo`/`getMe` dos 6 bots): TODOS os envios saíram `entregue=True` (o Batuta **nunca falhou em ENVIAR**); o "bot não me manda nada" era **destinatário que não deu /start** no bot (ex.: PRO → chat `604459409`, id diferente e INTENCIONAL — flexibilidade do produto). O bug do "reconectar" era o `webhook_secret` (crachá do webhook de ENTRADA) morando dentro do JSONB `configuracao`: como não é campo do schema, **toda edição da config** — o PUT de `rotas/instrumentos.py` **E a IA de conversa** (`criacao/servicos.py`) — o apagava → canal aparecia "Desconectado". Múltiplas fontes de verdade [[feedback-bug-recorrente-fonte-de-verdade]].
- **Fix (fonte única):** `webhook_secret` vira **COLUNA** em `instrumentos` (migração `whk00secret001` + backfill do JSON→coluna, sem stripar o JSON p/ rollback seguro); `ativar-canal` grava na coluna, a validação de entrada e o status "conectado" leem a coluna; nenhum caminho de edição de config a toca → **editar nunca mais desconecta**. De brinde, o crachá deixa de vazar para o frontend. Teste de regressão (PUT preserva o crachá). Ação única do maestro: reconectar 1x os 4 canais que já tinham perdido (COF Blog/PRO/CAP/InstaBot); PES/EST corrigidos pelo backfill.
- **Feature (decisão do maestro = "automático ao salvar"):** o drawer do instrumento de Telegram mostra **selo de status** de conexão + faz **checagem de ALCANCE** ao abrir/salvar (`GET /mensageria/{id}/alcance` → `telegram.checar_alcance` via `getChat`, NÃO envia nada): se o bot não alcança o destinatário, avisa para pedir que a pessoa inicie conversa com o bot. `alcancavel=None` quando não dá para consultar (sem alarme falso).

---

## FASE — "Criar com a IA": organização ativa vira fonte única (cookie)  ✅ NO AR (2026-07-07, deploy `9afacf8`, sem migração, 100% frontend)

Gatilho: ao montar o time de teste do App Review, a IA criadora criava o time na **organização errada** (a 1ª da lista, "Lure Consultoria") mesmo com outra selecionada na sidebar. Causa raiz (múltiplas fontes de verdade [[feedback-bug-recorrente-fonte-de-verdade]]): a sidebar guardava a "org ativa" em estado local **não persistido** (começando em `organizacoes[0]`), e o `/criar` tinha **outro** estado local independente, também em `organizacoes[0]` — a troca na sidebar nunca chegava ao `/criar`. Fix: a org ativa vira um **cookie** (`batuta_org_ativa`, novo `interface/lib/org-ativa.ts`): a sidebar grava ao trocar; a sidebar (layout) e o `/criar` leem no servidor como valor inicial, validado contra as orgs do usuário. Sobrevive a navegação **e** refresh; as duas pontas concordam. Verificado: `npm run lint` + `npm run build` verdes.

---

## FASE — Portão por canal: aprovador derivado do instrumento + retomada tardia  ✅ NO AR (2026-07-09, deploy `71af7df`, sem migração, núcleo intocado)

Gatilho: exec `18e42293` parou no portão para sempre. Causa raiz — **duas fontes de verdade para "quem aprova"** [[feedback-bug-recorrente-fonte-de-verdade]]: o instrumento `enviar_telegram` **envia** o pedido para `destinatario_padrao` (604459409, desde "o instrumento é a verdade" de 2026-06-25), mas o nó do gate **esperava** aprovação de `no.aprovacao.destinatario` (5175352629, campo à parte que divergiu). O artigo ia para um chat e o sistema esperava em outro → a resposta "aprovado" virava conversa conversacional órfã ("aprovado, encaminhando", falso) e a execução ficava `aguardando_humano` eterno. É o **follow-up que a memória previu** em 2026-06-25 (35 conversas históricas ao 5175352629 com o mesmo padrão).
- **Fix 1 (fonte única):** `aprovacao._destino_efetivo` deriva o aprovador do `destinatario_padrao` do instrumento (`no.aprovacao.destinatario` só como fallback); `vincular_pausa` usa isso → envio e espera no MESMO chat. **Auto-cura as automações atuais, sem migração.** Frontend: o campo de destinatário do portão no `inspector.tsx` vira derivado/somente-leitura (mostra o destino do canal).
- **Fix 2 (retomada tardia):** `servico.registrar_entrada` religa uma resposta tardia a um portão `aguardando_humano` cujo aprovador derivado é o contato — mesmo após o sweeper ter encerrado a conversa. Novo `aprovacao.execucao_parada_do_contato`.
- **Fix 3 (estacionar):** unifica as 2 chaves de abandono do portão (`acao_ao_encerrar` do sweeper + `portao_acao_abandono` do turno) numa só; default vira **`estacionar`** (execução parada e retomável; perfil `disparo` segue `cancelar`). Sweeper não cancela quando estacionar; despedida do portão mais suave.
- Verificação: **527 testes** (+4 novos: derivação, fallback, reconexão tardia, estacionar/cancelar) + lint/build front. Pendência de dado: a exec `18e42293` presa é destravada aprovando pela TELA (publica o artigo).

---

## FASE — Tipo de fluxo confiável + automação nasce como "Processo interno"  ✅ (2026-07-09, sem migração, núcleo intocado)

Gatilho: o maestro estranhou que um fluxo "Processo interno" (esperado ~15 min) só cutucou depois de ~60 min (exec `18e42293`). Investigação: o motor **RESPEITA** o Tipo de fluxo (`resolver_config` aplica o perfil na cascata `global<canal<perfil<ajustes<nó`; sweeper e relógio do portão leem daí). A causa do "60 min" foi que **aquela automação tinha `configuracao={}`** (nunca teve tipo salvo) → rodou no **padrão geral** (60/30). Dois enganos na tela agravavam: (a) mostrava "Atendimento" como se estivesse escolhido mesmo sem nada salvo; (b) valores do "Avançado" (`ajustes`) venciam o tipo sem aviso nem reset. E **toda automação nascia sem perfil** (IA criadora + create manual). O Fix 3 do portão NÃO interfere (mexeu só na ação de abandono, não nos tempos). Decisões do maestro: deixar o tipo confiável na tela + automação nasce "Processo interno".
- **Backend (nasce com tipo):** `mensageria/config.py::PERFIL_PADRAO = "interno"` (fonte única). Plantado em `criacao/servicos.py` (`_obter_ou_criar_automacao` e `definir_automacao`) e no create manual `rotas/automacoes.py` (só quando ausente — respeita perfil explícito). Duplicar já copiava. **Não retroage** sobre automações legadas (config vazia segue no padrão geral até o maestro escolher).
- **Frontend (tela honesta), `config-fluxo.tsx`:** (a) seletor não finge mais "Atendimento" quando nada foi salvo — mostra "Padrão geral (nenhum tipo escolhido)" + aviso, e os defaults viram os globais; (b) resumo sempre visível em português claro ("cutuca em X min; encerra Y depois" + comportamento do portão); (c) no "Avançado", cada campo é marcado `herdado do tipo`/`ajustado` com "voltar ao padrão" (remove de `ajustes`) + "Restaurar padrões do tipo". `automacoes-cliente.tsx`: nova automação inicia `{perfil:"interno"}` (editar carrega o real). Tudo com dados de `/config/fluxo`, sem mudança de backend.
- Verificação: **532 testes** (+5 novos: nasce interno pela IA e pela rota; rota respeita perfil explícito; `config_da_automacao` do padrão rende timeout=30/nudge=15) + lint/tsc/build front. Obs.: a exec `18e42293` já está `cancelada` (aprovar pela tela não vale mais; publicar = re-disparar).

---

## FASE — Portão avisa o humano o que vai acontecer (derivado do Tipo de fluxo)  ✅ (2026-07-09, sem migração, núcleo intocado)

Gatilho: o maestro pediu que o Batuta **transmita ao humano as regras do fluxo** no portão por canal (Telegram), derivadas do Tipo de fluxo. Pergunta dele: "código ou markdown?" → **código**: os avisos de cutucar/encerrar são do sweeper (o markdown não os alcança), e fixar "X min" no markdown seria uma 2ª cópia do parâmetro que desatualiza ao trocar o Tipo de fluxo (múltiplas fontes de verdade) [[feedback-bug-recorrente-fonte-de-verdade]]. Em código a mensagem é derivada do parâmetro real, uniforme em toda automação.
- **`mensageria/config.py` (fonte única):** `URL_APP="batuta.team"`; `aviso_expectativa_portao(conf)` (o aviso do PEDIDO: prazo `timeout+nudge` + destino da aprovação; `None` se não encerra por inatividade) e `complemento_nudge_portao(conf)` (cauda do cutucar), ambos variando estacionar↔cancelar; `DESPEDIDA_PORTAO_MSG` reescrita citando o app + nova `DESPEDIDA_PORTAO_CANCELA_MSG`.
- **`mensageria/aprovacao.py::vincular_pausa`:** passa a enviar UM aviso de expectativa junto da pausa (`_avisar_expectativa`), **à prova de falha** (roda no `try` de disparo/retoma que marca `falhou` — o envio nunca propaga; sem token não envia) e **idempotente por passo**. Bônus: `_registrar_apresentado` passou a deduplicar pelo seu próprio marcador (`origem="execucao"`), não só por `passo_id` (o aviso compartilha o passo).
- **`mensageria/sweeper.py`:** nudge e despedida de portão usam as mensagens novas (estacionar cita o app; cancelar avisa o cancelamento).
- Verificação: **536 testes** (+4 novos: aviso estacionar com prazo+app e idempotente; cancelamento no perfil `disparo`; sem timeout não avisa; envio à prova de falha). Núcleo/tela intocados; sem migração.

---

## FASE — IA criadora gerencia VÁRIAS automações por time + duplicação sem confundir a IA  ✅ (2026-07-12, sem migração, núcleo intocado)

Gatilho: o maestro notou que a IA criadora/companheira só mexia numa automação por time (`.first()`), embora banco+tela já suportem N — pior, o prompt JÁ dizia "há várias, confira no retrato", mas o retrato mostrava uma só e as ferramentas editavam só a primeira → a IA reescrevia a existente / "não via" a 2ª. Agravante do maestro: as DUPLICAÇÕES podem confundir a IA (o time duplicado copiava a conversa LITERAL, com ids do time original embutidos → a IA "criei X" e não achava; e duplicar automação no mesmo time deixava a cópia invisível ao `.first()`). Decisões (AskUserQuestion): duplicação = conversa recomeça limpa + herda a memória durável + nota; com várias e pedido vago, a IA pergunta qual.
- **Parte 1 — IA ciente de N automações (`criacao/`):** `_snapshot_time` devolve `automacoes` (lista com id/nome/tipo_gatilho/ativa) mantendo `automacao`=primeira (canvas de /criar intocado). `servicos.resolver_automacao(time, automacao_id, permitir_criar)` = fonte única de "qual" (por id / única / cria-a-primeira / recusa-listando quando ambíguo). Novas `servicos.criar_automacao`/`renomear_automacao`; `definir_cadeia`/`definir_gatilho` por `automacao_id`. Ferramentas novas `criar_automacao`/`renomear_automacao` e `montar_cadeia`/`definir_gatilho`/`ativar_time`/`desativar_time` aceitam `automacao_id` (com várias e sem id → erro com a lista → a IA pergunta). `prompt.py` alinhado. `rotas/criacao.py` sincroniza TODAS as automações pós-turno. (Remover automação fica só na tela — é destrutivo: cascateia o histórico.)
- **Parte 2 — duplicação (`duplicacao_time.py`):** a nova ConversaCriacao nasce com `mensagens=[]` (recomeça limpa, mata os ids stale na origem) + herda a MemoriaProjeto (texto) + grava uma memória de proveniência ("Time duplicado de 'X'."). Duplicar automação no mesmo time já é resolvido pela Parte 1 (a IA vê todas e edita por id).
- Verificação: **541 testes** (+5 novos: cria 2ª sem sobrescrever; edita/ativa por id sem tocar a outra; pedido ambíguo pede qual; renomear; + duplicação recomeça limpa herdando memória). Núcleo/tela/migração intocados.

---

## FASE — Webhook de comentários do Instagram em tempo real (GAP 2)  ✅ (2026-07-12, migração aditiva, núcleo intocado)

Gatilho: o maestro perguntou se o webhook de comentários dependia de um novo tipo de uso na Meta (não: usa a permissão `instagram_business_manage_comments` já enviada) e pediu um plano cobrindo todas as bordas, usos e problemas do usuário. Hoje só se lia comentário sob demanda (`instagram_ler_comentarios` por `media_id`); faltava o "ele sabe na hora". Decisão de arquitetura: comentário é **evento discreto → gatilho** (não a borda de `Conversa`); a Meta entrega os comentários de TODAS as contas conectadas numa URL única do app → um **receptor faz o fan-out**. Aprovação flexível (portão opcional por nó, decisão do maestro); teto/filtros configuráveis; a conta é escolhida pelo humano na tela (a IA criadora não aponta credencial — v1-A).
- **Backend:** `rotas/instagram_webhook.py` (GET handshake de verificação; POST valida `X-Hub-Signature-256` do app secret e faz fast-ack; em 2º plano resolve conta por `ig_user_id`→`resumo` da credencial, aplica anti-loop [só comentário de topo; ignora a própria conta], acha automações que casam os filtros, deduplica+teto e dispara via `criar_execucao`+`fila`). `instagram_webhook.py` (helpers puros: assinatura, verify token, extrair comentários, montar entrada rotulada, `inscrever_conta`). Modelo `EventoComentarioInstagram` + migração **`igc00coment001`** (tabela `eventos_comentario_instagram`: dedupe por `(comment_id, automacao_id)`, teto por janela, auditoria). Novo `tipo_gatilho="comentario_instagram"` (registrado em `criacao/ferramentas.py`+`orquestracao/grafo.py`+`_validar_gatilho`); config `{credencial_id, midias, palavra_chave?, teto_por_hora?}`. Callback do OAuth (`rotas/instagram.py`) inscreve a conta (best-effort). Reusa `instagram_responder_comentario`.
- **Duplicação:** `duplicacao_comum.sanear_gatilho_duplicado` (helper único em `duplicacao_time.py` + `rotas/automacoes.py::duplicar`) — o gatilho de comentário nasce "a conectar" na cópia (zera `credencial_id`, mantém filtros), como o canal nasce sem token, para a cópia não disparar na conta do original.
- **Frontend:** 4º card "Comentário do Instagram" no nó de gatilho (`inspector.tsx`) com conta (dropdown das credenciais da org), quais posts (todos/específicos), palavra-chave, teto e dica do portão; plumbing de `credenciaisInstagram` do Server Component (`page.tsx`) até o inspector; `salvar()` barra ativar sem conta.
- Verificação: **562 testes** (+17 do receptor: assinatura, handshake, dedupe, anti-loop, fan-out, teto, conta inexistente, helpers; +2 OAuth [inscreve/inscrição falha não derruba]; +2 duplicação) + tsc/eslint/build front. FALTA operação do maestro p/ funcionar: `INSTAGRAM_WEBHOOK_VERIFY_TOKEN` no Railway + assinar o campo `comments` no painel da Meta (`https://api.batuta.team/instagram/webhook`) + Acesso Avançado do App Review (até lá só contas testadoras).
- **✅ VALIDADO AO VIVO (2026-07-12):** o maestro fez a operação (verify token + campo `comments`) e testou — comentou de outra conta e a automação disparou e respondeu. Dois fixes no caminho: (1) `975572a` — a MESMA conta em VÁRIAS orgs: o receptor pegava a credencial por `.first()` e olhava uma org só → `_credenciais_da_conta` devolve TODAS e o fan-out casa a automação pela credencial que o gatilho aponta em qualquer org; (2) conta conectada ANTES do recurso não estava inscrita no `subscribed_apps` (inscrita à mão; o callback do OAuth já inscreve daqui pra frente).

---

## FASE — Instagram: ler post + instrumento de VISÃO + padrão de nomes  ✅ (2026-07-12, sem migração, núcleo intocado)

Gatilho: o maestro notou que o agente respondia comentários **sem enxergar** a imagem do post (só o texto do comentário). A corrente comentário→contexto→resposta precisava de duas peças novas.
- **`instagram_ler_post`** (só leitura): dado o `media_id` (que o gatilho de comentário entrega), lê a **legenda + a URL da imagem** (`media_url` p/ foto, `thumbnail_url` p/ vídeo/reels) + link/contadores. É o elo que dá contexto ao agente. Merges `3d7f1c3` + `c24ac08` (a URL da imagem).
- **`descrever_imagem`** — instrumento de VISÃO **multi-provedor** (OpenAI/Claude/Gemini): imagem entra → TEXTO sai (o oposto do gerar/montar imagem). Usa `construir_modelo(config.modelo).invoke([HumanMessage(content=[...])])` com o **bloco multimodal agnóstico do langchain v1** (`{type:image,base64,mime_type}`) — sem ramificar por provedor; a chave vem do contexto `usar_chaves` pelo provedor do modelo. Reusa `montar_imagem._baixar` + sniff de magic-bytes (mime real, recusa não-imagem); tetos 8 imagens/~5 MB; erro claro sem chave. **Filtro por chave (pedido do maestro):** o campo de modelo é marcado `json_schema_extra={"ui":"modelo_ia"}`; o formulário genérico de instrumento passa a buscar `/organizacoes/{id}/modelos-disponiveis` e renderiza o dropdown **agrupado por provedor, só com os que têm chave** (mesma UX do seletor do agente). Medição: em `TIPOS_PAGOS`; `precos.custo_por_descricao` (flat/imagem por família, informativo); origem derivada do provedor do modelo. Merge `aa1a97f`. Ver [[project-descrever-imagem-visao-multiprovedor]].
- **Padrão de nome de instrumento "Serviço: ação"** (`61c8d7d`): os nomes exibidos estavam soltos (3 formatos na família Instagram). Padroniza os instrumentos de um serviço (Instagram/Telegram/WordPress) como "Serviço: ação"; genéricos seguem com a ação limpa. Documentado em `instrumentos/base.py`. Só muda o `nome_exibicao` — `tipo`/lógica iguais, nada quebra.
- Verificação: **576 testes** (+9 do `descrever_imagem`, +4 do `ler_post`) + tsc/eslint/build front. Sem migração.

---

# Encerramento

As fases da Etapa 2 são detalhadas no formato investigar/implementar/verificar **à medida que executadas** (MIGRACAO §6.3). O `MIGRACAO.md` é o documento de transição; quando tudo estiver refletido nos documentos vigentes, ele vai para `docs/historico/` — registro da decisão, não apagado.
