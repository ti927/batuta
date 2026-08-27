# Batuta — Arquitetura do sistema (retrato técnico para decidir a Biblioteca)

> Documento autossuficiente, escrito para um Claude **sem acesso ao código** entender como o
> Batuta está construído hoje e ajudar a decidir a melhor arquitetura para a **Biblioteca** (uma
> base de conhecimento que ainda não existe). O contexto da decisão está na **seção 12**, no fim —
> as seções 1–11 dão o pano de fundo. Estado de referência: produção no ar, `main` recente, banco
> migrado. Português é o idioma do produto e do código (nomes de tabela/variável em PT).

---

## 1. O que é o Batuta

Plataforma onde uma pessoa **não-técnica** monta **times de agentes de IA** que executam tarefas
reais de uma empresa, encadeando agentes em fluxos. Metáfora condutora: o usuário é o **maestro**, os
agentes são a **orquestra**. Vocabulário oficial do produto (usado inclusive no código):

- **Organização** — a empresa (espaço isolado onde tudo dela vive).
- **Time** — unidade de trabalho dentro de uma organização; tem um **Líder** e quantos **Agentes** forem necessários.
- **Líder / Agente** — executores de IA; a diferença é só o campo `papel`. Cada time tem no máximo um Líder.
- **Instrumentos** — capacidades concretas que um agente pode invocar (chamar uma API, rodar SQL, gerar PDF…). São as "ferramentas" no cinto do agente.
- **Gatilhos** — o que dispara um fluxo (manual, agendamento/cron, webhook de entrada).
- **Biblioteca** — o "segundo cérebro": base de conhecimento que os agentes consultam. **Ainda não implementada** (é o objeto desta análise — seção 12).

É uma ferramenta **interna de uma consultoria** (a "Lure"): a consultoria monta e opera os times para
seus clientes. Não é um SaaS self-service ainda.

---

## 2. Stack tecnológica

**Cérebro (backend)** — pasta `cerebro/`, Python **3.13**, gerenciado por `uv`:
- **FastAPI** (API REST) + **uvicorn**.
- **LangGraph** 1.2.x (motor de orquestração de agentes) + **langchain-anthropic / langchain-openai / langchain-google-genai** + **langchain-mcp-adapters**.
- **SQLAlchemy 2** + **psycopg** (Postgres) + **Alembic** (migrations).
- **APScheduler** (agendamento), **cryptography/Fernet** (cofre de segredos), **fpdf2** (PDF), **httpx**, **pyjwt[crypto]** (validação de JWT).

**Interface (frontend)** — pasta `interface/`, **Next.js 16** (App Router) + **React 19** + **TypeScript** + **Tailwind v4** + componentes estilo shadcn + ícones **lucide-react**; **@supabase/ssr** + **@supabase/supabase-js**, **framer-motion**, **sonner** (toasts).

**Infra gerenciada:**
- **Supabase** (PostgreSQL + Auth + Storage). Projeto na região **US East (us-east-1)**, co-locado com o Railway — migrado de São Paulo em 2026-07-20; o projeto antigo de SP foi apagado.
- **Railway** (hospedagem do cérebro e da interface, via Docker). Região **US East**.
- **Cloudflare** (DNS do domínio `batuta.team`).

---

## 3. As duas partes e a fronteira

O sistema tem duas metades que conversam por uma API REST:

- **Cérebro** = backend. **Dono de todos os segredos** (chaves de IA, credenciais de instrumentos, connection string do banco). Só ele fala com o banco e com os provedores de IA.
- **Interface** = frontend. Nunca fala com o banco nem com provedores de IA direto — **sempre** passa pelo cérebro.

**Autenticação:** toda rota de negócio exige `Authorization: Bearer <JWT do Supabase>`. O cérebro
valida o token **localmente** via JWKS (chaves públicas ES256 do Supabase) — sem segredo
compartilhado. Exceção: os **webhooks de entrada** (`POST /webhooks/...`) são públicos (é assim que
um gatilho externo dispara um fluxo). A interface manda o token de dois contextos:
- no **navegador** (ilhas-cliente) via `interface/lib/api.ts`;
- no **servidor** (Server Components/SSR) via `interface/lib/cerebro-servidor.ts`.

A interface aponta para o cérebro pela env `NEXT_PUBLIC_CEREBRO_URL` (em produção, `https://api.batuta.team`).

**Terceira peça (2026-08): o Batuta-MCP.** Um **2º serviço de backend** (mesmo repositório, mesmo banco)
expõe o Batuta como **servidor MCP** que o **claude.ai do próprio consultor** aciona para operar a
plataforma (criar/ajustar/diagnosticar times) na **assinatura dele** — 44 ferramentas, **login real por
consultor** e escopo por papel. Roda na raiz de um domínio próprio (as `.well-known` do OAuth exigem raiz);
o cérebro fica intocado (única exceção aditiva: um reconcílio periódico no agendador). A IA **nunca** recebe
segredo. Ver [`docs/MCP-BATUTA.md`](MCP-BATUTA.md).

---

## 4. Modelo de dados (PostgreSQL via SQLAlchemy + Alembic)

Todas as tabelas carregam `id` (UUID), `criado_em`, `atualizado_em`. Toda tabela de negócio se liga,
direta ou indiretamente, a uma **Organização** — é o que sustenta o isolamento. Tabelas (arquivo
`cerebro/modelos.py`):

**Núcleo do produto:**
- **`usuarios`** — `nome`, `email`, `auth_id` (o `sub` do JWT do Supabase; nulo até aceitar convite), `ativo`.
- **`organizacoes`** — `nome`, `dono_id`, `modelo_criadora` (modelo de IA da conversa, nulo = padrão Opus), `logo_url` (logo como *data URI*).
- **`times`** — `organizacao_id`, `nome`, `descricao`.
- **`agentes`** — `time_id`, `nome`, `papel` (`lider`|`agente`), **4 markdowns** (`agent_md`, `skill_md`, `tools_md`, `soul_md`) que definem 100% do comportamento, `modelo_ia` (qual LLM; nulo = padrão Haiku). Índice parcial garante ≤1 Líder por time.
- **`instrumentos`** — `time_id`, `nome`, `tipo`, `configuracao` (JSONB, campos não-secretos), `exige_aprovacao` (tri-estado: NULL=automático/True=sempre exige portão humano/False=nunca).
- **`agente_instrumentos`** — N:N, o "cinto": quais instrumentos cada agente pode usar.
- **`automacoes`** — `time_id`, `nome`, `tipo_gatilho` (manual|cron|webhook), `configuracao_gatilho` (JSONB), **`cadeia`** (JSONB: o grafo de agentes com bifurcação), `ativa` (nasce `false`).
- **`execucoes`** — `automacao_id`, `estado` (`aguardando`|`em_andamento`|`aguardando_humano`|`concluida`|`falhou`), `entrada`, `resultado`, timestamps. **A própria tabela é a fila** (ver §5).
- **`passos_execucao`** — `execucao_id`, `ordem`, `agente_id` (SET NULL p/ preservar histórico), `entrada`, `saida` (JSONB; inclui `uso` = tokens por chamada + origem da chave), `estado`. É o que permite inspecionar a orquestração passo a passo.

**Identidade e acesso:**
- **`membros`** — `usuario_id` × `organizacao_id` + `papel` (`admin`|`operador`|`observador`). Fonte de permissão; um usuário pode ser membro de várias orgs com papéis distintos.
- **`convites`** — `email`, `organizacao_id`, `papel`, `status`. Ninguém se autoinscreve; um admin convida, o convidado aceita e vira Membro.
- **`auditoria`** — quem/o quê/quando/em qual recurso (ações sensíveis). `recurso_id`/`organizacao_id` são UUID soltos (não-FK) para sobreviver à exclusão do recurso.

**Cofre (segredos cifrados — Fernet):**
- **`chaves_api`** — chaves de LLM. `organizacao_id` (nulo = **chave-mãe da consultoria**, o fallback), `tipo_ia` (`executora`|`criadora`|`companheira`), `provedor` (`anthropic`|`openai`|`google`), `valor_cifrado`, `ultimos4` (nunca reexibe o valor). Índice único por (org, tipo, provedor).
- **`segredos_instrumento`** — um campo secreto de um instrumento (ex.: senha de app do WordPress). `instrumento_id`, `campo`, `valor_cifrado`. Vive separado da `configuracao` em claro.

**IA criadora/companheira:**
- **`conversas_criacao`** — `organizacao_id`, `titulo`, **`mensagens`** (JSONB, histórico append-only), `time_id` (o time que a conversa cria/mantém). É o "fio eterno" do projeto (ver §7).
- **`memorias_projeto`** — memória de longo prazo da IA sobre um projeto: `conversa_id`, `organizacao_id`, `categoria` (`fato`|`decisao`|`preferencia`), `conteudo` (texto). **Abordagem DESTILADA, sem vetor** (ver §7 e §12 — é o precedente que conflita com RAG).

> **Não existe nenhuma tabela de "Biblioteca".** Apesar de o `MIGRACAO.md` antigo listá-la como
> parte do "modelo de dados do core", ela nunca foi criada. (Ver §11–12.)

---

## 5. O motor de orquestração (o core validado)

Construído sobre **LangGraph**. É o coração validado do produto. **[Atualizado 2026-07-26]** A regra
antiga era "estendê-lo, nunca alterá-lo" (núcleo congelado); hoje o motor **evolui por decisão dirigida**
(`MIGRACAO.md §6.1`) — muda quando o produto exige, de forma formal/aditiva/aprovada, nunca por reescrita
cega. **Fato que este retrato precisa deixar claro:** existem hoje **dois runtimes** que rodam agente —
*este* motor (cria `Execucao`/`PassoExecucao`, deixa rastro inspecionável) e o **motor de conversa** da
mensageria (`mensageria/servico.py`, que chama `executar_agente` **por fora** e **não** cria execução).
Essa dualidade é o alvo do **Programa de Unificação de Estado** (`docs/UNIFICACAO-ESTADO.md`, prioridade
nº 1): colapsar os dois numa **timeline única com memória entre turnos**.

- **Agente isolado** (`orquestracao/agente.py`): o comportamento vem **100% dos 4 markdowns** (não há prompt-base escondido). Monta o prompt a partir dos markdowns, dá ao agente o **cinto** (instrumentos) como *tools*, e roda via `create_react_agent` do LangGraph. Mede tokens (`usage_metadata`).
- **Cadeia por BIFURCAÇÃO** (`orquestracao/cadeia.py`): a `cadeia` (JSONB da automação) é um grafo onde, ao terminar um passo, **o próprio agente escolhe uma de várias saídas** — ele declara o ramo pela ferramenta `seguir_para(rotulo)` (injetada quando o nó tem 2+ saídas; o `rotulo` é um *enum* dos rótulos). A LLM roteadora (`_escolher_saida`) só entra de **fallback** (agente não declarou, rótulo inexistente, automação antiga). Loops são permitidos (com guarda de máximo de passos). Não é uma fila linear, nem um roteador adivinhando na frente do agente.
- **Espera-por-humano** (a peça mais delicada): um nó pode ter `gate`. A execução **pausa** (estado `aguardando_humano`, salvo no banco — sobrevive a reinício) e **retoma** quando um humano responde — na **tela** (`POST /execucoes/{id}/responder`) ou pelo **canal** (Telegram já no ar). O portão é **conversacional**: ao chegar a resposta, **o próprio agente roda de novo** (com a resposta + suas saídas; desde a **Fatia 4.3**, **retomando do estado salvo** por checkpointer nativo — não re-deriva do zero, cf. `REMODELAGEM-MOTOR.md §5`) e decide — pode **perguntar de volta** (segue pausado) ou **declarar o ramo** via `seguir_para` (o fluxo anda), honrando o que o markdown dele manda; a LLM roteadora só entra de fallback (gate-roteador, 1 saída, execução antiga ou teto anti-loop `MAX_RODADAS_GATE`). O que o agente apresenta ao humano fica registrado na thread de **Conversas** (`mensageria/aprovacao.py::vincular_pausa`). **Portão POR CANAL** é uma conversa de mensageria de primeira classe: a resposta passa pela mesma máquina de turno da borda (entrega, relógio de inatividade, teto, sweeper que cancela/estaciona a execução) — `mensageria/servico.py::_turno_de_portao`.
- **Comportamento do fluxo CONFIGURÁVEL** (`mensageria/config.py`): as regras de mensageria/portão (espera, teto, saudação, horário, forma do portão, encerramento) não são fixas — `resolver_config` resolve a cascata `global < canal (instrumento) < PERFIL do fluxo < ajustes do fluxo < nó`. Fonte ÚNICA lida pela borda (servico/sweeper/portão), exposta na UI por `GET /config/fluxo` (perfis: interno/atendimento/disparo/personalizado). `Automacao.configuracao` guarda `{perfil, ajustes}`.
- **Fila** (`fila.py`): pool de N≈3 trabalhadores em threads; o claim é `SELECT ... FOR UPDATE SKIP LOCKED` na própria tabela `execucoes` (sem broker externo). Todo gatilho **enfileira** (`aguardando` → worker pega). No boot, execuções `em_andamento` órfãs viram `falhou`.
- **Agendador** (`agendador.py`): APScheduler `BackgroundScheduler`, fuso `America/Sao_Paulo`. Relógio em memória reconstruído do banco no startup e re-sincronizado no CRUD de automações. Só dispara se `ativa=true`.
- **Gatilhos**: **manual** (botão, sempre roda — testa qualquer fluxo), **agendamento/cron** (formulário guiado, sem jargão cron), **webhook de entrada** (`POST /webhooks/automacoes/{id}`, público; o corpo vira a entrada).
- **Disparo** (`orquestracao/disparo.py`): `criar_execucao` (enfileira) + `rodar_execucao` (o worker executa). Resolve as **chaves de IA** na fronteira e as fixa num *context var* (`usar_chaves`) — o grafo não sabe de onde a chave vem.
- **Parede de ativação** (`portao_ativacao.py`): uma automação com agente que tem instrumento de **ação irreversível** só pode ser **ativada** se houver `pausa_humano` no nó anterior (senão 422). É a proteção: tudo nasce real mas **dorme** até o consultor ativar.

Lifespan do FastAPI (`main.py`) sobe a fila e o agendador no boot e os desliga no shutdown. **Por isso o cérebro roda em 1 réplica** (escalar duplicaria os gatilhos agendados).

**A conexão do checkpointer tem de falhar rápido (2026-08-26).** O `PostgresSaver` usa um
`ConnectionPool` aberto no boot. O padrão do psycopg **não valida a conexão ao emprestar**, e o pooler
do Supabase mata conexão ociosa do lado dele: o pool entregava uma conexão morta e a primeira leitura do
checkpointer esperava resposta **para sempre** — prendendo um atendimento inteiro em "bot respondendo",
antes mesmo de o agente rodar (sintoma característico: **zero checkpoints** gravados na thread). Três
defesas, hoje travadas por teste: `check=ConnectionPool.check_connection`, keepalive TCP de 30 s e
`statement_timeout` de 20 s (+ `max_idle` de 120 s). O princípio: **numa peça à prova de falha, "demorar
para sempre" é pior que falhar** — falhar cai no modo legado, que atende.

**Fail-safe não pode ser mudo (2026-08-26).** O lifespan também prepara o checkpointer da memória de
conversa (`orquestracao/memoria_conversa.preparar()`), à prova de falha: se ele não subir, a conversa cai
no modo legado e o atendimento continua. Em agosto essa proteção escondeu uma regressão por **três dias**
— o checkpointer caiu, ninguém soube, e com ele foi junto a trava nativa de ação irreversível. A regra que
saiu daí, e que vale para todo fallback do projeto: **degradar é aceitável, degradar em silêncio não.**
Todo caminho degradado precisa de (a) evento no banco de logs, (b) vigia que destrave o que ficou preso e
(c) recado honesto a quem estava esperando. Materializações: o evento `memoria.checkpointer_indisponivel`;
o carimbo `memoria: duravel|legado` em cada passo de conversa; `sweeper.varrer_turnos_presos` (turno de
mensageria que começou e não voltou — a conversa ficava presa **para sempre**, porque o vigia de
inatividade só olhava quem esperava o contato); e os eventos `turno.iniciado`/`turno.concluido`/
`turno.morreu`. Ver o capítulo `operacao/sinais-e-diagnostico` da Central.

**Nenhum elo sem limite de rede, e todos vigiados (2026-08-27).** A rede entre o Railway e o pooler do
Supabase **congelou por ~30 min** (bytes parados em trânsito, sem erro, sem fechamento): uma consulta
aterrissou 15 min atrasada na mesma transação, três turnos destravaram no mesmo instante e o app inteiro
pareceu morto — com `/saude` verde, porque ele só lê memória. Duas respostas estruturais:
1. **O engine principal (`db.py`) ganhou a mesma blindagem do checkpointer** — `pool_pre_ping`,
   `pool_recycle=300`, `connect_timeout`, keepalives, `statement_timeout=60 s` e **`tcp_user_timeout=30 s`**
   (o único knob que corta envio sem confirmação, o modo de falha exato do congelamento). Um elo congelado
   agora vira erro honesto em segundos, não meia hora de silêncio.
2. **O vigia dos ELOS (`saude_elos.py`)**: sonda ativa de cada ligação da corrente — banco, checkpointer,
   provedores de IA com chave (GET /models, grátis), cada canal Telegram (`getMe` + `getWebhookInfo`, que
   conta os erros do Telegram ao ENTREGAR pra gente), Meta, Storage, borda pública, serviço MCP e os
   motores internos (fila, agendador, vigia da mensageria — heartbeat `ULTIMA_VARREDURA_EM`). Estado por
   elo com erro **traduzido** (rede × credencial × quota), evento em toda transição (`elo.caiu`/`elo.voltou`/
   `elo.reconectado`), **auto-cura nos elos de banco** (2 falhas seguidas → `engine.dispose()` /
   reconstrução do pool) e reconexão por botão (`POST /saude/elos/{id}/reconectar`, admin da consultoria).
   A interface expõe tudo em **`/status`** (poll do cache em `GET /saude/elos`; o selo da sidebar linka).
   Sondas nunca gastam token de IA nem tocam API de cliente (instrumentos testam sob demanda, no
   Construtor). Complemento na mensageria: **guarda do turno atrasado** (o estado fresco da conversa é
   reconferido antes de entregar/escrever — turno que destrava tarde é descartado com evento
   `turno.descartado`, nunca entregue numa conversa fechada) e tetos do vigia separados (chat 8 min;
   portão 30, porque a retomada de fluxo pode legitimamente levar 300 s × 6 de IA).

---

## 6. Instrumentos (capacidades plugáveis)

`instrumentos/base.py` define um **registro de tipos**: cada tipo é uma subclasse de
`TipoInstrumento` que declara `tipo`, `nome_exibicao`, `descricao`, um schema de **Config** e de
**Args** (Pydantic), `campos_secretos` (vão pro cofre) e `acao_irreversivel`. Os tipos se
auto-registram ao importar o pacote. O agente recebe cada instrumento do cinto como uma *tool* da
LLM (via `definicao_para_ia()`).

Tipos implementados quando este retrato foi escrito (8): **REST** (`chamar_api_rest`), **SQL**
(`banco_sql`, com `somente_leitura`), **webhook de saída**, **busca na web** (Tavily), **gerar PDF**
(fpdf2), **gerar imagem** (OpenAI), **WordPress** (publicar post), **MCP** (conectar a servidores MCP).
*(A lista cresceu bastante desde então — Instagram, vídeo, visão, mensageria, conector declarativo. A
fonte da verdade é o registro em `cerebro/instrumentos/`, não esta enumeração.)*

A irreversibilidade é resolvida **por instância** (`exige_portao(tipo, config, override)`): ex.: REST
GET = leitura (sem portão), POST/PUT/DELETE = escrita (com portão); o interruptor `exige_aprovacao`
sobrepõe. Falhas de instrumento têm **retentativa com backoff** e nunca "morrem em silêncio".

**Duas falhas de instrumento, dois caminhos (2026-08-26).** Uma exceção (`FalhaInstrumento`) derruba ou
desvia o fluxo; mas há um segundo caminho, mais traiçoeiro: o instrumento **devolve a falha como dado**
(`{"ok": false, …}`, ex.: HTTP 4xx do REST/conector) para o agente decidir o que fazer. Esse caso não
mudava estado nenhum e **não deixava rastro** — o agente narrava sucesso e a execução parecia limpa. Hoje
o resultado com `ok: false` também entra em `erros_instrumentos` (com `origem="resposta"`), e o
diagnóstico o levanta como aviso mesmo numa execução "concluída".

**Endereço do conector não sai com buraco (2026-08-26).** No conector, um campo de `destino="url"`
substitui um `[colchete]` no endereço. Se, depois da substituição, sobrar algum `[campo]`, a operação
**falha na hora** nomeando o campo (não-retentável) — antes a chamada saía com o colchete literal, o
serviço respondia 404 e o agente inventava a explicação. O irmão silencioso desse erro **não** dá para
o motor detectar: um campo no destino errado (`query` num POST cujo corpo leva os dados) faz o serviço
responder *sucesso* com o dado ausente — só documentação e revisão de montagem pegam, e é por isso que
o capítulo `instrumentos/construir-conector` da Central passou a ensinar o par sintoma→causa.

**Saída HTTP para host escolhido pelo usuário: `cerebro/http_saida.py`.** REST, conector, webhook e
WordPress passam por uma porta única que (a) numa falha de **rota** refaz a chamada uma vez amarrada a
IPv4 — um host com endereço IPv6 e sem rota até ele fazia a chamada morrer com `ENETUNREACH` mesmo
havendo IPv4 alcançável, porque o erro que sobra é o da última tentativa — e (b) traduz o erro de rede
para linguagem humana, nomeando o host. Instrumentos de serviço fixo (Telegram, Instagram, OpenAI,
Firecrawl, Tavily) seguem com o cliente HTTP direto.

**Material de conexão vindo do cofre (2026-08-22).** Além de segredos escalares (um token, uma senha),
um instrumento pode receber material de conexão mais rico por referência a uma credencial nomeada. O
caso que motivou isso é a **API bancária**: ela exige um **certificado digital de cliente** no aperto de
mão TLS (mTLS) e, quase sempre, um **token de acesso de vida curta** emitido apresentando esse mesmo
certificado. Duas peças estruturais saíram daí:
- `TipoInstrumento.campos_secretos_opcionais` — segredo que só existe para quem precisa; vazio **não** é
  pendência (senão todo REST/conector nasceria "faltando certificado").
- `CampoCredencial.interno` — campo da credencial que **não** vai para a Config de instrumento nenhum
  (dado de exibição, ou material que só a borda usa, como a URL do token).

O token é obtido e renovado **pela borda**, em `segredos_instrumento.anexar_aos_instrumentos` — o mesmo
ponto onde o token do Google já é renovado —, porque o agente não teria como carregar um token de uma
chamada para a seguinte (cabeçalho é configuração fixa). Ver `certificados.py`, `oauth_mtls.py` e o
capítulo `segredos/certificado-digital-mtls` da Central.

> **Para a Biblioteca, o ponto-chave:** "o agente consultar a base de conhecimento" encaixa
> naturalmente como **um novo tipo de instrumento** (ex.: `consultar_biblioteca`) no cinto — sem
> tocar no motor. É o mecanismo de extensão pensado para isto.

---

## 7. As IAs e as chaves

Existem **três papéis de IA** (o cofre modela os três), mas hoje só dois operam:

- **IA executora** = os **agentes** do time. Cada agente escolhe seu `modelo_ia` (Anthropic/OpenAI/Google; padrão `claude-haiku-4-5`). É o que roda nos fluxos.
- **IA de conversa (criadora = companheira)** = **uma única conversa que nunca termina** (`criacao/loop.py`), na qual o consultor monta e ajusta o time conversando. Ela escreve no **time real** via `criacao/servicos.py` (cria/edita Time/Agente/Instrumento/cinto/Automação). Modelo padrão **Opus** (`MODELO_CRIADORA`), configurável por organização (`organizacoes.modelo_criadora`). Tem **memória de longo prazo** (`memorias_projeto`) que ela mesma cura (ferramentas `lembrar`/`recordar`/`esquecer`).

**Cofre de chaves multi-provedor** (`chaves.py`): resolve a chave na ordem **chave da organização →
chave-mãe da consultoria → `ANTHROPIC_API_KEY` legada do ambiente**. A interface tem tela para
cadastrar chaves por org (e por tipo de IA), e só oferece modelos cujo provedor tem chave resolvível.

**Contabilização de tokens** (`precos.py`): cada passo grava `uso` (modelo, tokens, **origem** da
chave: própria/consultoria/legado); há `GET /uso/resumo` (por org/time) e `GET /uso/consultoria`
(painel do admin da consultoria, soma o gasto na chave-mãe entre orgs).

> **PRECEDENTE IMPORTANTE PARA A BIBLIOTECA:** a memória de longo prazo da IA (`memorias_projeto`) foi
> deliberadamente feita **DESTILADA, sem vetor/embeddings** — decisão do maestro. O raciocínio: um
> projeto acumula **dezenas** de memórias curtas (fatos/decisões), que cabem no contexto do modelo, então
> a recuperação é por recência/filtro simples. **Esse caso é diferente do da Biblioteca**, que será uma
> base de **muitos documentos longos** — onde a busca semântica (RAG) costuma ser necessária. O conflito
> entre esse precedente e o que a Biblioteca pede é justamente o ponto a decidir (§12).

---

## 8. Auth, papéis e cofre

- **Supabase Auth** (login por e-mail/senha; convites por e-mail via Resend). O cérebro valida o JWT por JWKS (ES256). `usuario_atual` resolve o `Usuario` pelo `auth_id`.
- **Papéis** (por organização, tabela `membros`): **observador** (vê) < **operador** (cria/edita/dispara) < **admin** (destrói, mexe em acesso/chaves). Aplicado em todas as rotas via helpers (`_comum.py`).
- **Admin da consultoria**: lista de e-mails numa env (`CONSULTORIA_ADMINS`) — quem gere a chave-mãe e vê o painel de uso da consultoria. Distinto de admin de organização.
- **Cofre**: Fernet com `COFRE_CHAVE_MESTRA` (env, nunca no banco). Cifra `chaves_api` e `segredos_instrumento`; o valor nunca volta à interface (só `ultimos4`).

---

## 9. Frontend (Next.js 16)

Padrão fixo: cada tela é um **Server Component** que busca no cérebro (`buscarCerebro`, `cache:
no-store`) + uma **ilha cliente** (`"use client"`) que muta via `lib/api.ts` e dá `router.refresh()`.
`proxy.ts` na raiz (no Next 16 substitui o middleware) cuida da sessão Supabase e protege rotas.

O shell é uma **sidebar** escura, separada em **dois blocos**:
- **Organização** (todo usuário da org): Início (`/`) com sub-links **Gerenciar Times**
  (`/organizacoes/[id]`) e **Gerenciar Organizações** (`/organizacoes`); a lista de **Times**;
  Biblioteca; Uso e custos; e — só para admin da org — Acesso e papéis, Chaves e credenciais,
  Configurações da organização (`/organizacoes/[id]/configuracoes`).
- **Consultoria** (visível **só ao `admin_consultoria`**): Chaves da consultoria, Uso da consultoria,
  Configurações da consultoria (`/configuracoes-consultoria`).
- Acima dos dois blocos, o botão de destaque **Criar com a IA** (`/criar`).

**Tudo de um time vive em `/times/[id]`, em abas:** Início (dashboard), Agentes, Instrumentos,
Automações, Execuções (com o detalhe em `/times/[id]/execucoes/[execId]`) e Conversas. **Não existem
mais páginas soltas de execução nem de automação** — `/execucoes` (lista global) e `/automacoes/[id]`
(detalhe avulso) foram removidas; execuções e automações se acessam pelas abas do time. A URL do
**webhook** de uma automação aparece no drawer do nó **Gatilho** (aba Automações). `/biblioteca`,
`/uso` e `/configuracoes-consultoria` são placeholders "em breve" (`components/area-em-breve.tsx`).

**Aprovação humana (portão).** Duas peças distintas: (1) o **portão do nó** na cadeia (`gate` no nó —
`orquestracao/cadeia.py` lê `no.get("gate")` e pausa em `aguardando_humano`) é o que de fato pausa;
(2) a **parede de ativação** (`portao_ativacao.validar`, ponto único usado pela rota de ativação e
pela IA criadora) recusa ativar uma automação cujo agente faz ação irreversível sem um portão antes.
A parede é uma **config GLOBAL da organização** (`organizacoes.parede_ativacao`, default TRUE; liga/
desliga em **Configurações da organização**, rota `PUT /organizacoes/{id}/parede-ativacao`). A
irreversibilidade é derivada do tipo+config do instrumento (`instrumentos.acao_irreversivel`) — **não
há mais interruptor de aprovação por instrumento**.

---

## 10. Implantação (produção)

- **Railway**, projeto com **2 serviços** do mesmo repo, cada um com Dockerfile próprio: `cerebro/` (python:3.13 + uv; no start roda `alembic upgrade head` + uvicorn) e `interface/` (Node 22, Next `output:"standalone"`; as `NEXT_PUBLIC_*` entram como **build args**, congeladas no build). Região **US East**, **1 réplica**.
- **Banco:** Supabase em **US East**, co-locado com o Railway (migrado de São Paulo em 2026-07-20 — a latência caiu muito). A conexão é pelo **pooler** (`aws-0-us-east-1.pooler.supabase.com`), o que dispensou o "Outbound IPv6" que a conexão direta de SP exigia.
- **Domínio:** `batuta.team` (interface) e `api.batuta.team` (cérebro), via **Cloudflare** (DNS only). HTTPS automático do Railway.
- **Storage:** o **Supabase Storage está disponível mas ainda NÃO é usado**. Hoje os instrumentos `gerar_pdf`/`gerar_imagem` gravam em **disco efêmero** do Railway (o arquivo some no próximo deploy — limitação aberta). **O pgvector do Supabase está disponível** (Postgres), caso se opte por RAG.

---

## 11. Estado do projeto

- **Etapa 1 (núcleo)** validada: orquestração ponta a ponta (times, agentes, instrumentos, cadeia com bifurcação, espera-por-humano, gatilhos, fila, medição).
- **Etapa 2**: papéis/identidade, cofre de chaves e de segredos, identidade visual, IA criadora (conversa eterna), memória de longo prazo, refinos (modelo da conversa selecionável, painel de uso), logo da organização, e a **implantação em produção** (acima) — tudo concluído.
- **Falta:** (a) **Mensageria (WhatsApp)** — o canal do Líder (provedor decidido: Evolution API por QR); (b) **a Biblioteca** — objeto desta análise.

---

## 12. O PROBLEMA DA BIBLIOTECA (a decisão a tomar)

### O que é (requisito, já revisado pelo maestro)
A **Biblioteca** é uma **base de conhecimento da ORGANIZAÇÃO** (todos os times da org acessam — **não**
por time, como dizia a especificação antiga). É composta de **documentos gerais** (PDF, Word, txt,
planilhas… **não** só markdown). Os **agentes consultam** esse acervo para decidir e responder com base
no conhecimento da empresa. No futuro pode ser **mão dupla** (o agente também alimenta a base) — mas há
uma **decisão de produto em aberto**: o agente escreve direto ou um humano revisa antes de virar
permanente? (a recomendação registrada é exigir revisão, para a base não degradar).

### As 4 peças técnicas de "uma base de documentos que a IA consulta"
1. **Guardar os arquivos** — upload e armazenamento dos documentos (candidato natural: **Supabase Storage**, já disponível, persistente; nível organização).
2. **Extrair o texto** — converter cada arquivo em texto pesquisável (PDF→texto, docx→texto…). PDFs escaneados/imagem exigiriam **OCR** (complexidade extra).
3. **Recuperar o trecho certo** na hora da consulta — **o fork central**:
   - **Busca por significado (RAG / embeddings):** fatiar os documentos em pedaços, gerar **embeddings** (vetores de significado) e guardá-los (o **pgvector** do Supabase serve); na consulta, achar os pedaços semanticamente mais próximos da pergunta. É o padrão da indústria para IA consultar documentos; entende sinônimo/contexto. **Custo:** uma chamada de embeddings por pedaço (ex.: OpenAI `text-embedding-3-*`) — exige uma chave de embeddings (o cofre já comporta) e processamento na ingestão.
   - **Busca por palavra-chave / full-text:** o full-text search nativo do Postgres acha documentos pelos termos. Sem embeddings, sem custo de IA, mais simples — mas **literal** (não entende sentido), perde qualidade conforme a base cresce.
   - **Híbrido / faseado:** começar por palavra-chave e evoluir para RAG; ou combinar os dois (full-text + reranking semântico).
4. **O agente consultar** — expor isso como um **novo tipo de instrumento** (`consultar_biblioteca`) no cinto do agente: o agente faz uma pergunta, recebe os trechos relevantes (e a fonte), e responde com base neles. **Encaixa no mecanismo de extensão existente, sem tocar no motor.**

### O que dá para reusar (já existe)
- **Supabase Storage** (disponível, não usado ainda) para os arquivos.
- **pgvector** no mesmo Postgres do Supabase, se for RAG.
- **Cofre de chaves** multi-provedor — comporta a chave de embeddings (provedor OpenAI já é suportado no schema).
- **Sistema de instrumentos** — a consulta vira um tipo novo, plugável.
- **Fila/trabalhadores** — a ingestão (extrair texto + gerar embeddings) pode rodar como trabalho assíncrono.
- **Isolamento por organização** — o padrão de toda tabela carregar `organizacao_id`.

### A tensão a resolver
Há um **precedente explícito contra vetores**: a memória da IA criadora foi feita **destilada, sem
embeddings**, por decisão do maestro (cabia no contexto, eram poucas memórias). A Biblioteca é um caso
**diferente** (muitos documentos longos), onde RAG costuma ser o caminho — mas reabrir essa decisão tem
implicações de **custo**, **complexidade** e **manutenção** que valem ponderar.

### Perguntas em aberto para a consultoria externa decidir
1. **Abordagem de busca:** RAG (semântico, melhor qualidade, custo+complexidade) × full-text (simples, literal) × híbrido/faseado? Vale o RAG para o volume e o uso reais desta consultoria?
2. **Tipos de documento e OCR:** começar só com texto extraível (PDF nativo, docx, txt, md) e deixar OCR (PDF escaneado/imagem) para depois?
3. **Quem escreve (decisão §19):** v1 só humano cura (agentes só leem) e a escrita pelo agente vem depois, com revisão? Ou já fazer mão-dupla?
4. **Escopo:** org-wide (decidido) — mas faz sentido permitir **marcar** documentos por time/assunto para a consulta filtrar? 
5. **Custo:** qual orçamento aceitável de embeddings/armazenamento? Provedor de embeddings (OpenAI? outro)?
6. **Ingestão:** síncrona no upload ou assíncrona pela fila? Re-indexar quando um documento muda?

> Restrições do projeto a respeitar em qualquer proposta: para a Biblioteca, **encaixar como extensão**
> (ex.: um instrumento) sem precisar mexer no motor — e, de modo geral, o motor **evolui só por decisão
> dirigida** (`MIGRACAO.md §6.1`), nunca por alteração avulsa; **isolamento por organização**; **segredos
> só no cérebro/cofre**; a interface só fala com o cérebro; produção é 1 réplica do cérebro (cuidado com
> trabalho pesado de ingestão bloqueando — usar a fila).
