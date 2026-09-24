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
- **`instrumentos`** — `time_id`, `nome`, `tipo`, `configuracao` (JSONB, campos não-secretos).
- **`agente_instrumentos`** — N:N, o "cinto": quais instrumentos cada agente pode usar.
- **`automacoes`** — `time_id`, `nome`, `tipo_gatilho` (manual|cron|webhook), `configuracao_gatilho` (JSONB), **`cadeia`** (JSONB: o grafo de agentes com bifurcação), `ativa` (nasce `false`).
- **`execucoes`** — `automacao_id`, `estado` (`aguardando`|`em_andamento`|`aguardando_humano`|`concluida`|`falhou`), `entrada`, `resultado`, **`pendencias`** (ramos da onda que ainda não rodaram quando a execução pausou), **`dados`** (a *ficha*: os valores nomeados que atravessam o grafo), **`dono`/`dono_ate`** (quem está mexendo nela agora, com prazo — a trava entre superfícies, §5) e **`espera_ate`** (quando a espera por humano vira alarme), timestamps. **A própria tabela é a fila** (ver §5).
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
- **Cadeia como GRAFO, caminhada por ONDAS** (`orquestracao/cadeia.py`): a `cadeia` (JSONB da automação) é um grafo dirigido, e desde 2026-08-31 o motor **não** tem ponteiro único — ele percorre uma **frente** de ramos. Ao terminar um passo, o agente declara pela ferramenta `seguir_para(rotulos: list)` **todas** as saídas cuja condição foi atendida (o rótulo é um *enum*, a IA não inventa caminho), e todas rodam. Dois ramos que reencontram o mesmo nó **na mesma onda** o rodam **uma vez**, com os textos juntos (junção implícita — sem ela, um Y publicaria em dobro). Cada saída tem um **papel** (`grafo.TIPOS_SAIDA`: `condicional | erro | senao`), lido pelo motor. A LLM roteadora (`_rotear_por_llm`) só entra de **fallback** (agente não declarou, rótulo inexistente, automação antiga) e **pode devolver nenhuma** — nada casando, o ramo termina com o motivo no rastro, nunca mais na primeira saída em silêncio. Loops são permitidos, com teto de passos **por execução** (soma as retomadas).
- **A ficha da execução** (`orquestracao/ficha.py` + `execucoes.dados`): entre nós trafega texto, mas os **dados** trafegam na ficha — valores nomeados que chegam ao prompt de **todos** os nós. Nasce com a entrada do gatilho (que antes morria no nó 1), cresce pela ferramenta `anotar` e **atravessa a pausa de aprovação**. Vai na **mensagem do turno**, não no prompt de sistema (ali invalidaria o cache de prompt). Destrava a **regra exata** na seta (`saidas[].regra` — quem compara é o motor, não a IA; `None` = indecidível devolve a escolha ao agente, nunca vira "não" calado) e o nó **`cada`** ("Para cada item"), que abre um ramo por item de uma lista — por isso a junção implícita é chaveada por `(ramo, nó)`.
- **Espera-por-humano** (a peça mais delicada): quem pausa é o **AGENTE**, chamando o instrumento `pedir_aprovacao` (`pausa_para_humano` no contrato do encaixe) — desde 2026-08-31 **não há mais `gate` no nó** nem parede de ativação. A execução **pausa** (estado `aguardando_humano`, salvo no banco — sobrevive a reinício) e **retoma** quando um humano responde — na **tela** (`POST /execucoes/{id}/responder`) ou pelo **canal** (Telegram já no ar). Ao chegar a resposta, **o mesmo agente roda de novo** (retomando do estado salvo por checkpointer nativo, thread `execucao:nó` — não re-deriva do zero) e decide: pode **perguntar de volta** (segue pausado), **pedir aprovação outra vez** ou **declarar os ramos** via `seguir_para` (o fluxo anda). O canal por onde o pedido saiu e o destinatário ficam no PASSO (`saida.aprovacao`), e é isso que `mensageria/aprovacao.py::config_aprovacao` lê para amarrar a conversa de quem aprova — antes essa config vinha do nó. **Aprovação POR CANAL** é uma conversa de mensageria de primeira classe: a resposta passa pela mesma máquina de turno da borda (entrega, relógio de inatividade, teto, sweeper que cancela/estaciona a execução) — `mensageria/servico.py::_turno_de_portao`.
- **UM DONO POR EXECUÇÃO** (`orquestracao/dono.py`, 2026-09-21): a espera-por-humano tem **duas portas** (tela e canal) e, até esta data, cada uma tinha a sua trava, invisível para a outra — a tela olhava `execucoes.estado`, o canal marcava `conversas.estado`. Em 21/09 as duas entraram na mesma execução com 1m45s de diferença, abriram o **mesmo thread do checkpointer** (`{execucao}:{nó}`, endereço que as duas montam igual) e o checkpoint **bifurcou** (dois filhos do mesmo pai, o mesmo `step` — visível em `checkpoints`); a tela leu o estado no meio de três chamadas de ferramenta em voo e a Anthropic recusou o histórico pela metade (400 `tool_use` sem `tool_result`), matando uma execução de quase 4 h. Agora quem vai mexer **pega o dono primeiro** (`tomar`, UPDATE condicional único — a atomicidade é do banco): `dono` é a SUPERFÍCIE (`tela`|`canal`|`fila`), porque é o que a tela consegue mostrar em português, e retomar pelo mesmo lugar já é serializado por outros meios. `dono_ate` é o prazo, renovado pelo mesmo batimento de `atividade` que alimenta o vigia de presas — processo que morre segurando não troca o caos por paralisia. Quem chega segundo recebe **recusa honesta** (409 com frase pronta na tela; recado no canal e a mensagem fica reenviável). `rodar_retomada` confere a posse **antes de consumir** a resposta do humano: sem posse, volta à fila com a resposta intacta (`retomada.adiada`). Detalhe em `docs/FALHAS-DO-MOTOR.md`.
- **TODA ESPERA POR HUMANO TEM PRAZO** (`orquestracao/espera.py`, 2026-09-21): `aguardando_humano` era o **único** estado "em andamento" sem vigia — o relógio dela morava em `conversas.aguardando_ate`, então aprovação pedida só pela tela (sem canal amarrado) ficava parada **para sempre, em silêncio** (a mais velha encontrada em produção tinha 90 dias). Agora a execução carrega `espera_ate` (`teto_espera_humano_min`, 24 h, 0 = desligado, na cascata de `mensageria/config.py`) e o vigia `esperas_humanas` (job de 300 s, carimbado em `vigias.py` → sonda `vigia_execucoes` do `/status`) **avisa uma vez e zera o campo**. Ele **não encerra nada**: esperar dias por uma aprovação é legítimo; o que não era é ninguém saber. O tempo de parada vem do **fim do passo que pausou**, não de `espera_ate` menos o prazo — derivar do prazo fazia o aviso dizer "parada há 24 h" para uma parada há 90 dias.
- **Espera-por-TEMPO** (nó `esperar`, 2026-09-03): o nó que segura o fluxo por minutos/horas/dias **reusa a máquina da pausa por aprovação** — `execucoes.pendencias` guarda os ramos que ainda não rodaram, a ficha atravessa, e o que muda é só quem solta: em vez de uma pessoa, o vigia `fila.soltar_esperas_vencidas` (job de 30 s) devolve a execução de `aguardando_tempo` para `aguardando` quando `execucoes.retomar_em` vence. Por viver no BANCO, reinício do servidor não perde espera. É `TIPO_ESTRUTURAL` (não roda IA) mas **deixa passo** no rastro (`tipo="espera_tempo"`), e a numeração continua via `disparo._ordem_ja_gravada` — sem isso a inspeção teria dois "passo 1". Espera sem tempo definido **segue adiante avisando**, em vez de parar para sempre.
- **Limites do fluxo — custo e tempo** (`orquestracao/prazo.py` + `cadeia.py`): três tetos **opcionais** (0 = desligado), na mesma cascata de `mensageria/config.py`: `teto_usd_execucao`, `teto_min_passo` (com ajuste **por nó**) e `teto_min_execucao`. O de custo soma `precos.custo_de_entrada` dos passos — a **mesma** conta da aba Uso. O do passo é um ContextVar (padrão do `atividade`/`usar_chaves`) que o agente consulta no `_turno_interrompido`, o ponto único que já barrava ações depois de falha irreversível ou pedido de aprovação; ele para **entre** ações, não no meio de uma (Python não mata thread com segurança), e a documentação promete exatamente isso. Custo e tempo **atravessam a pausa**: `custo_ja_gasto` e `tempo_ja_trabalhado_s` reconstroem o já-gasto dos passos gravados. O de tempo conta **trabalho**, não relógio — contar relógio mataria, na retomada, a execução que esperou dias por uma aprovação.
- **Disjuntor de falhas** (`orquestracao/circuito.py`, 2026-09-03): automação que roda **sozinha** e falha 3× seguidas é desativada, com aviso pelo canal do time. `apos_falha` é o **funil único** do caminho de erro (os três sítios que terminam em `falhou` chamam só ele, então aviso e disjuntor nunca se separam). A contagem é **derivada das execuções**, não um contador guardado: com três caminhos de falha, um contador incrementado em três lugares um dia dessincroniza — derivando, o pior caso de esquecer um caminho é disparar mais tarde, nunca desligar o que não devia. Não contam: disparo `manual` (tem gente olhando) e falha causada pelo próprio Batuta (`interrompida_pelo_batuta`, marcada no boot e no vigia de presas) — sem isso, três deploys em dias seguidos desligariam as automações do cliente.
- **Operação da execução** (Onda 4): `execucoes.desenho` congela a **foto do grafo** no disparo (`grafo.desenho_que_roda` é a fonte única dos quatro leitores — motor, retomada, aprovação, diagnóstico), então editar a automação não muda o caminho de uma execução em curso; `POST /execucoes/{id}/rodar-de-novo` cria execução **nova** herdando desenho, ficha e a entrada exata do passo (histórico não se reescreve); `POST /automacoes/{id}/testar-no` roda **um** passo com entrada de mentira (`execucoes.teste_de_no` → `executar_cadeia(so_um_passo=True)`), acionando os **instrumentos reais** — e `origem="teste"` fica fora da conta do disjuntor, porque testar tem de ser seguro.
- **Comportamento do fluxo CONFIGURÁVEL** (`mensageria/config.py`): as regras de mensageria/espera (prazo, teto, saudação, horário, forma da aprovação, encerramento) não são fixas — `resolver_config` resolve a cascata `global < canal (instrumento) < PERFIL do fluxo < ajustes do fluxo < nó`. Fonte ÚNICA lida pela borda (servico/sweeper/portão), exposta na UI por `GET /config/fluxo` (perfis: interno/atendimento/disparo/personalizado). `Automacao.configuracao` guarda `{perfil, ajustes}`.
- **NENHUM LIMITE SECRETO** (`mensageria/config.py`, desde 2026-09-14 / `e4e498b`): limite não vive como constante de módulo. `max_passos` (era o fixo `cadeia.MAX_PASSOS`) e os prazos do vigia de turno preso (eram fixos no `sweeper`) entraram na cascata; `resumo_dos_limites(conf)` é a **redação única** dos limites efetivos em português, servida por `GET /config/fluxo` (por perfil) e por `POST /config/fluxo/limites` (perfil + ajustes, endpoint puro) — o front não reescreve as frases, senão divergiriam. Um teste (`test_todo_limite_aparece_na_tela`) quebra se um limite novo não ganhar botão. Ao disparar, `explicacao_limite_portao` diz **o quê / quanto / onde muda / que nada se perdeu**, e sai evento `portao.limite_atingido` nível `error`.
- **Uma régua por propósito, sem dupla contagem:** `teto_usd` (conversa) conta só a IA que CONVERSA — `servico._custo_de_conversa` exclui `categoria == 'instrumento'`; gerar imagem/vídeo é trabalho do FLUXO e responde ao `teto_usd_execucao`. `Conversa.custo_acumulado_usd` segue sendo o TOTAL honesto (é o que a inbox mostra); quem o teto lê é `medir_conversa`. Antes, três imagens de um carrossel (US$ 0,50) estouravam sozinhas o teto da conversa inteira.
- **O portão tem UMA régua nas duas superfícies:** `portao_max_rodadas` (idas-e-vindas daquele nó, via `retoma.rodadas_no_gate`) vale na tela **e** no canal. Antes o canal contava turnos/custo da conversa — duas verdades para a mesma regra. Atingido o limite, o canal NÃO emudece: o agente explica e a resposta segue pelo caminho mecânico (`_processar_aprovacao`), como na tela.
- **SILÊNCIO DO PORTÃO VIRA ALARME** (`retoma.alertar_portao_indeciso`): turno de portão que termina sem escolher ramo **e** sem pedir aprovação, num nó com 2+ saídas condicionais, era indistinguível de "ele perguntou de propósito" — e a execução ficava parada para sempre. Repetindo (≥2 rodadas seguidas sem decidir), sai `portao.indeciso` nível `error` nomeando o agente e os rótulos ignorados. A causa é quase sempre **markdown que não conhece as saídas do nó** — por isso a regra entrou também no prompt da criadora, nas docstrings do MCP e na Central (`automacoes/condicoes-e-ramos`).
- **FALHA NÃO CONTAMINA O QUE NÃO ERROU**: um 400 de **protocolo** (`llm.historico_invalido` — histórico mal formado) não é falha do fluxo, é estado que chegou pela metade; `disparo._entrada_recusada` devolve a execução à espera (só quando o último passo ainda é a pausa), avisa quem esperava e **não conta para o disjuntor**. E execução que vira `falhou` **desvincula a conversa** (`aprovacao.desvincular`) — era assim que o agente seguia conversando, e trabalhando, por um canal cujo fluxo já tinha morrido.
- **O que desce ao PRÓXIMO NÓ depois de uma aprovação é idêntico nas duas superfícies:** `retoma.entrada_retomada(..., proximo_no=True)` — o material apresentado + a decisão rotulada como **já tomada no passo anterior**. Antes o canal repassava o transcript da conversa e a tela o apresentado + `[Resposta do humano]`; o nó seguinte lia uma pergunta de aprovação já respondida como decisão a encaminhar e chamava `seguir_para` sem fazer o próprio trabalho.
- **Fila** (`fila.py`): pool de N≈3 trabalhadores em threads; o claim é `SELECT ... FOR UPDATE SKIP LOCKED` na própria tabela `execucoes` (sem broker externo). Todo gatilho **enfileira** (`aguardando` → worker pega). No boot, execuções `em_andamento` órfãs viram `falhou`. O vigia periódico de **presas** mede progresso por **três** sinais e só mata quando os três estão velhos: `iniciada_em`, o último passo concluído e `atividade_em` — o **sinal de vida** publicado pelo instrumento em curso (2026-09-03). Sem o terceiro, um passo que legitimamente demora dentro de UM instrumento era morto mesmo trabalhando: a prova estava no código, onde `gerar_video` encolhia o próprio teto "para ficar abaixo do sweeper".
- **Agendador** (`agendador.py`): APScheduler `BackgroundScheduler`, fuso `America/Sao_Paulo`. Relógio em memória reconstruído do banco no startup e re-sincronizado no CRUD de automações. Só dispara se `ativa=true`.
- **Gatilhos**: **manual** (botão, sempre roda — testa qualquer fluxo), **agendamento/cron** (formulário guiado, sem jargão cron), **webhook de entrada** (`POST /webhooks/automacoes/{id}`, público; o corpo vira a entrada).
- **Disparo** (`orquestracao/disparo.py`): `criar_execucao` (enfileira) + `rodar_execucao` (o worker executa). Resolve as **chaves de IA** na fronteira e as fixa num *context var* (`usar_chaves`) — o grafo não sabe de onde a chave vem.
- **Nada dispara antes de ativar:** a automação nasce **inativa** — tudo o que a IA criadora monta é real, mas **dorme** até o consultor ativar. Ativar não tem trava: a proteção contra ação irreversível é o instrumento `pedir_aprovacao` no cinto do agente (ver acima), não uma recusa automática.

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

**O último estado sem vigia (2026-09-14).** A mesma classe de falha reapareceu num estado que ninguém
tinha olhado: `humano_assumiu`. O bot entregava a conversa sozinho ao atingir um teto e ali ela ficava
**para sempre** — `registrar_entrada` engolia calada toda mensagem do contato, inclusive a resposta de uma
aprovação que o próprio Batuta acabara de pedir por aquele canal, e novos pedidos continuavam saindo por
ele. Tudo parecia saudável nas duas pontas. As respostas: `sweeper.varrer_transferidas` devolve ao bot o
que ninguém assumiu (prazo contado desde **quem está esperando** — a mensagem mais antiga sem resposta —,
nunca desde `atualizado_em`, senão insistir adiaria o próprio resgate), `aprovacao.vincular_pausa` religa a
conversa quando chega pedido novo, resposta a portão pendente é **sempre** processada, e os eventos
`conversa.devolvida_ao_bot` / `conversa.religada_por_portao` / `portao.limite_atingido` deixam rastro. A
regra geral que ficou: **todo estado "em andamento" precisa de alguém que o varra — inclusive os que
parecem finais.** Só a conversa que uma PESSOA assumiu de propósito (`atribuida_a`) fica fora, porque aí há
um responsável de verdade.

**E o agente vê o que acontece na própria conversa.** No modo memória a entrada do turno filtrava por
`papel == 'contato'`: o agente era o único que não ficava sabendo da transferência para um humano nem do
que um operador escreveu pela inbox — seguia conduzindo às cegas. `_conteudo_novo` passa a trazer tudo que
não é fala dele, rotulado (`[Operador (humano)]`, `[Sistema]`).

**Orçamento de conexões com o pooler (2026-09-24).** O pooler do Supabase em modo sessão aceita um número
FIXO de clientes (era 15), enquanto o banco aceita 60. O engine usava o padrão do SQLAlchemy (5 fixas + 10
extras por processo), a memória das conversas até 4 e o serviço MCP mais 15: o Batuta podia pedir 30+ e,
em repouso, já segurava 11–15. Todo pico (deploy com dois cérebros no ar, várias execuções juntas) virava
`EMAXCONNSESSION` e erro 500 — 11 vezes entre 26/08 e 24/09. Agora: orçamento explícito e ajustável por
variável de ambiente (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`/`DB_POOL_TIMEOUT`; cérebro 5+7, MCP 2+4 fixado em
`mcp_servidor.py`), quem passa do orçamento ESPERA uma conexão livre do próprio pool, e quando o pooler
recusa por estar cheio a conexão **espera e tenta de novo** (~6,5 s, `db.conectar_com_paciencia`) em vez de
falhar na primeira — com evento `banco.pooler_cheio` no banco de logs (warning se saiu, error se desistiu).
Recomendado subir o **Pool Size** do pooler para 30 no painel do Supabase (Project Settings › Database ›
Connection pooling): o conector MCP do Supabase não alcança essa configuração. Modo transação (porta 6543)
foi avaliado e **não** adotado: exige desligar comandos preparados e mudar o `statement_timeout` por
sessão, e o checkpointer depende do modo sessão.

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
   motores internos (fila, agendador, vigia da mensageria — heartbeat `ULTIMA_VARREDURA_EM` — e o
   **vigia das execuções**, `vigias.py`: o batimento dos três jobs que soltam execução PAUSADA —
   esperas, sub-fluxos e presas. Sem ele, um job morto deixaria toda execução em `aguardando_tempo`/
   `aguardando_sub_fluxo` parada para sempre com a página verde, porque `agendador.esta_saudavel()`
   só reporta `_scheduler.running`: o relógio girando, não os jobs disparando). Estado por
   elo com erro **traduzido** (rede × credencial × quota), evento em toda transição (`elo.caiu`/`elo.voltou`/
   `elo.reconectado`), **auto-cura nos elos de banco** (2 falhas seguidas → `engine.dispose()` /
   reconstrução do pool) e reconexão por botão (`POST /saude/elos/{id}/reconectar`, admin da consultoria).
   A interface expõe tudo em **`/status`** (poll do cache em `GET /saude/elos`; o selo da sidebar linka).
   Sondas nunca gastam token de IA nem tocam API de cliente (instrumentos testam sob demanda, no
   Construtor). Complemento na mensageria: **guarda do turno atrasado** (o estado fresco da conversa é
   reconferido antes de entregar/escrever — turno que destrava tarde é descartado com evento
   `turno.descartado`, nunca entregue numa conversa fechada) e tetos do vigia separados (chat 8 min;
   aprovação 30, porque a retomada de fluxo pode legitimamente levar 300 s × 6 de IA).

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

A irreversibilidade é resolvida **por instância** (`acao_irreversivel(tipo, config)`): ex.: REST
GET = leitura, POST/PUT/DELETE = escrita. Ela governa a **política de falha** (uma escrita que falha
derruba o passo; uma leitura, não) e o selo do catálogo — **não** é mais uma trava de ativação.
Falhas de instrumento têm **retentativa com backoff** e nunca "morrem em silêncio".

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
**webhook** de uma automação aparece no painel do nó **Gatilho** (aba Automações = o Estúdio). `/biblioteca`,
`/uso` e `/configuracoes-consultoria` são placeholders "em breve" (`components/area-em-breve.tsx`).

**Aprovação humana — uma peça só, e é do agente (2026-08-31).** O instrumento `pedir_aprovacao`
(`instrumentos/pedir_aprovacao.py`, `pausa_para_humano = True`) apresenta o pedido pelo canal
configurado e faz a execução parar; `orquestracao/agente.py` devolve `pausado=True` + `aprovacao`, e
`orquestracao/cadeia.py` transforma isso em `aguardando_humano`, gravando o passo como
`espera_humano` com o canal/destinatário. As DUAS peças anteriores — o **portão** (`no.gate`) e a
**parede** (`organizacoes.parede_ativacao` + `portao_ativacao.validar`) — **foram removidas**: eram
invisíveis, se sobrepunham (a conversa pedia confirmação em dobro) e tiravam do agente uma decisão
que é dele. A irreversibilidade (`instrumentos.acao_irreversivel`, derivada de tipo+config) continua
existindo como política de falha e selo do catálogo.

---

## 9-bis. A porta INTERNA serviço-a-serviço (2026-09-22)

Até aqui o Batuta tinha duas portas: a **pública** do cérebro (`api.batuta.team`, autenticada por
JWT do Supabase) e a do **serviço MCP** (OAuth 2.1 próprio). Nasceu uma terceira, estreita:
`POST /interno/conector/testar-operacao` (`cerebro/rotas/interno.py`).

**Por que existe.** O serviço MCP roda **sem** a `COFRE_CHAVE_MESTRA`, de propósito (least-privilege:
a IA nunca recebe segredo). Consequência: a IA monta um conector e não consegue testá-lo. Em vez de
dar a chave ao MCP, o pedido se **inverte** — o MCP pede ao cérebro que rode o teste. O segredo é
decifrado, usado e descartado do lado de cá; o que atravessa a fronteira é só a resposta da API.

**Como se protege — três camadas, porque numa porta serviço-a-serviço uma só não basta:**

1. **`BATUTA_INTERNO_SECRET`**, comparado em tempo constante (`hmac.compare_digest`). Prova que quem
   chama é um serviço nosso. **Ausente = a porta não existe** (404, não 403: um ambiente que não usa
   a ponte não anuncia que ela poderia existir). Nada fica aberto por omissão.
2. **Autorização por USUÁRIO, pelos guardas de sempre.** O segredo não autoriza nada sozinho: o corpo
   diz em nome de quem se age e o pedido passa por `instrumento_acessivel(..., "operador")` — o mesmo
   guarda da tela. Há teste dedicado a isso; se ele cair, a porta virou atalho de permissão.
3. **Escopo mínimo.** Faz UMA coisa (testar uma operação de conector), não é proxy genérico, e devolve
   só `{ok, status, corpo, erro, campos_detectados}` — sem configuração e sem segredo.

Toda chamada deixa evento `conector.testado_pela_ia` (origem `mcp`) com quem agiu. **Risco residual,
dito na cara:** quem tiver o segredo interno pode testar operações de conector em nome de qualquer
usuário — limitado ao que aquele usuário já poderia fazer. É por isso que o escopo é mínimo e o
rastro existe.

**Variáveis novas:** `BATUTA_INTERNO_SECRET` (nos DOIS serviços) e, no serviço MCP, `CEREBRO_URL`
(padrão `https://api.batuta.team` na Railway).

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
- **Frente "O motor vira um grafo de verdade" (2026-08-31 → 09-04):** Ondas **1**, **2**, **Parte III**, **3** e **4** ✅ completas e no ar (inclusive o nó "Chamar outra automação").
- **Integrações sem código (2026-09-21/22):** o **MCP como cliente** (o agente ganha as ferramentas que se escolher de um servidor MCP, com aprovação POR FERRAMENTA) e a **conta de serviço do Google** como tipo de autenticação do Construtor — a saída da verificação de app do Google, que tinha deixado o Search Console dois meses em 401. A IA passou a poder **testar** um conector sem ver o segredo (§9-bis).
- **Estúdio** — a tela do fluxo desde 2026-09-22: condição no fio, cartão listando as saídas, o desenho se conferindo sozinho, e as regras do fluxo no painel da direita (sem o antigo botão "Fluxo"). Assumiu a aba **Automações**; a tela clássica saiu da barra mas a ROTA `/times/[id]/automacoes` segue viva como saída de emergência, a um clique no menu "⋯". Apagá-la é decisão para depois do teste ao vivo.
- **Cada regra tem um DONO (2026-09-22).** A cascata de configuração passou a ser particionada por dono, e isso virou **lei de código** (`_mesclar(…, permitidas=…)` em `mensageria/config.py`): **canal** = a voz de quem fala (saudação, horário, mensagens automáticas); **agente** = propriedade de um ATO (quanto trabalha num passo, quanto/como espera uma pessoa); **fluxo** = contador que acumula (mensagens e custo da conversa, passos e custo da execução, vigias). Antes qualquer camada escrevia qualquer chave e quem vencia mudava campo a campo. Junto, o **"Tipo de fluxo" morreu como camada**: guardava uma etiqueta cujos números moravam no código (migração `prs00preset001` materializou-os nos ajustes, com diff provado vazio nas 16 automações reais), e virou modelo de partida. O agente ganhou a coluna `configuracao` (`rte00ritmo0001`) e a aba **"Ritmo e espera"**.
- **A espera por uma pessoa não prende mais ninguém (2026-09-22).** Um agente que conclui o trabalho e não declara o caminho deixava a mesma aprovação voltando para sempre — o `portao.indeciso` detectava em nível `error` e, por decisão anterior, "só deixava rastro". Agora, se a pessoa responde com o nome exato de um caminho e o agente já teve a chance dele, o motor segue por essa resposta e registra `portao.destravado` (§12-A: evento + vigia + recado).
- **Falta:** (a) **Mensageria (WhatsApp)** — o canal do Líder (provedor decidido: Evolution API por QR); (b) **a Biblioteca** — objeto desta análise; (c) instrumentos **org-wide** (hoje `instrumentos.time_id` é obrigatório e nenhum tipo é da organização — decidido em 12/08, nunca construído; exige migração).

---

## 12. O PROBLEMA DA BIBLIOTECA (a decisão a tomar)

> **[2026-09-24] Esta seção é histórico.** A Biblioteca foi absorvida pelo **Cérebro da organização**
> (`docs/CEREBRO-PLANO.md`): Quadros (dados que os agentes escrevem e leem entre si), Arquivos e Biblioteca, nessa ordem.

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
