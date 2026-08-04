# Batuta — Documento de Migração

**Data:** junho de 2026
**Aplica-se a:** Batuta com Etapa 1 (core) construída e validada, prestes a iniciar a Etapa 2.

---

## Como usar este documento

Este é um **documento de migração**, não uma reescrita. Os documentos vigentes do projeto (`PRODUTO.md`, `CLAUDE.md`, `BUILD-PLAN.md`, `DESIGN-SYSTEM.md`) continuam válidos como base. Este documento descreve **as mudanças** de visão que ocorreram após o fechamento do portão de validação do core, e instrui como aplicá-las sobre o que já está construído.

A ordem de leitura recomendada:
1. Seção 1 — entender o estado atual reconhecido.
2. Seção 2 — entender o que mudou na visão.
3. Seção 3 a 5 — os impactos concretos em produto, plano e código.
4. Seção 6 — como executar a migração com segurança.

**Importante:** este documento não autoriza, em nenhuma circunstância, mexer no motor de orquestração já construído e validado. As mudanças são por adição e por reorientação da Etapa 2 — não por refatoração do núcleo.

> **Atualização de governança (2026-07-26):** o "não mexer no motor, em nenhuma circunstância" foi a regra **certa** para proteger o core recém-validado — mas, ao valer como trava absoluta, empurrou todo trabalho novo para a borda e fez a mensageria virar um **segundo motor** paralelo. A regra **graduou** para **evolução dirigida do motor** (ele pode evoluir por mecanismo formal, aditivo e aprovado-antes, nunca por reescrita cega). Ver a **§6.1 (reescrita)** e o programa **`docs/UNIFICACAO-ESTADO.md`**. O espírito anti-reescrita-cega permanece; a proibição absoluta, não.

---

## 1. Estado atual reconhecido

A Etapa 1 do `BUILD-PLAN.md` foi concluída e o portão de validação foi aberto pelo maestro. O que está **construído, testado e em produção interna**:

- Modelo de dados do core: Organizações, Times, Agentes (Líder + Agentes), Instrumentos, Biblioteca, Automações, Execuções, Passos de Execução.
- Cérebro Python com FastAPI; interface Next.js com Tailwind e shadcn/ui.
- Orquestração de agentes sobre LangGraph, com encadeamento, estado e human-in-the-loop.
- Espera-por-humano nas três formas (pergunta pontual, portão de aprovação, confirmação de baixa confiança).
- Tela de inspeção da orquestração passo a passo.
- Gatilhos manual e CRON.
- Robustez: tratamento de falha, feedback de progresso, fila de volume, medição de uso informativa.
- Um time real em uso (`news-to-insight → curator-lure-fit → lure-writer → Lure.publisher`), publicando no WordPress por instrumento real.
- Roteiro de validação cumprido, incluindo: espera-por-humano com retomada após tempo, tratamento de falha forçada, execuções simultâneas.

**Decisão operacional crítica:** o núcleo construído nesta Etapa 1 é tratado, daqui em diante, como **núcleo congelado**. As migrações descritas neste documento podem **estender** o núcleo, **somar** novas peças e **reorientar** a Etapa 2 — mas não justificam reescrita do que já roda. *(Atualizado em 2026-07-26: "congelado" graduou para **evolução dirigida** — o motor pode mudar de forma dirigida e aprovada, o que segue vedado é a reescrita cega. Ver §6.1 e `docs/UNIFICACAO-ESTADO.md`.)*

---

## 2. As cinco viradas de visão

Após a Etapa 1 ter sido construída, a visão de produto evoluiu por conversas estratégicas com o maestro. Cinco viradas, todas válidas e firmes:

### Virada 1 — Batuta é ferramenta interna da consultoria, não SaaS

O Batuta deixa de ser concebido como SaaS público vendido a empresas em geral. Passa a ser **ferramenta interna da consultoria do maestro**, usada por seus consultores para padronizar e automatizar processos nos clientes que a consultoria atende. O modelo comercial é: o contrato existente entre consultoria e cliente, somado a uma cobrança recorrente (boleto ou similar) pelo uso continuado do Batuta no cliente — operada fora do produto, não como módulo dentro dele.

**Consequência prática:** todo o aparato de SaaS público é eliminado do escopo: planos, cobrança recorrente automatizada, billing, painel de cancelamento, fluxo de inadimplência automatizado, marketing, onboarding público, suporte público, termos de uso de consumidor. A operação comercial entre a consultoria e o cliente é fora do Batuta.

### Virada 2 — AI-first do início ao fim do projeto

A criação de um projeto/time deixa de ser por formulários e telas; passa a ser por **conversa entre o consultor e a IA**. O consultor descreve o que o cliente precisa; a IA conduz a conversa, propõe uma estrutura, e — após aprovação do consultor — **executa a implantação**: cria o time, cria os agentes, escreve os markdowns (`agent.md`, `skill.md`, `tools.md`, `soul.md`), configura os instrumentos, monta as automações. As telas estruturais não desaparecem — viram interface de revisão, ajuste fino e inspeção. A entrada padrão para criar coisas no Batuta é a conversa.

### Virada 3 — IA companheira do projeto (sessão viva)

A IA que ajudou a criar o projeto **não some após a criação**. Ela permanece como **IA companheira**, com memória do projeto inteiro: o que foi conversado durante a criação, o que mudou desde então, o estado atual do banco de dados, os históricos de execução. O consultor (ou o admin do cliente) pode, a qualquer momento, **abrir uma conversa sobre o projeto** e pedir alterações, diagnóstico de erros, sugestões de melhoria. A IA conhece o projeto como se tivesse vivido nele desde o começo.

Tecnicamente, isso se sustenta sobre três camadas de memória descritas em seção própria abaixo (3.6).

### Virada 4 — Três tipos de IA, com chaves de origem distinta

A partir desta migração, o Batuta passa a ter **três papéis distintos de IA**, conceitualmente separados, mesmo que possam usar o mesmo modelo subjacente:

- **IA executora** — vive dentro dos Agentes que processam tarefas reais dos clientes. Já existe; não muda no comportamento.
- **IA criadora** — conversa com o consultor para estruturar o projeto e executa a criação no Batuta. Adição nova.
- **IA companheira** — vive junto do projeto, mantém memória, responde sobre ele. Adição nova.

A distinção é **conceitual** (papéis distintos da IA), não de chave: as **três** podem usar tanto chaves próprias do cliente quanto as chaves da consultoria — a escolha cabe ao usuário/admin do projeto (ver Virada 5). Por isso a medição de tokens precisa ser explícita no produto para todas as três: é ela que diz quanto cada IA consumiu e em qual chave, definindo o que é cobrado e de quem.

### Virada 5 — Chaves por projeto, com fallback para a chave padrão da consultoria

Substitui o modelo de "BYOK + mensalidade" do `PRODUTO.md` original. O novo modelo é:

- **Toda chamada de IA — executora, criadora e companheira** — usa a chave configurada **no projeto** para aquele tipo de IA.
- Se o projeto **não tiver chave configurada** para um tipo, usa por **fallback** a **chave padrão da consultoria**.
- As chaves do projeto são **trocáveis a qualquer momento** e a escolha **cabe ao usuário/admin**: quem quiser usar **chaves próprias** indica **todas** as chaves (uma por tipo de IA, ou uma só usada por todas, conforme o provedor); quem usar as **chaves da consultoria** opera sob a contrapartida obrigatória de medição abaixo. Tipicamente o consultor inicia o projeto na chave da consultoria, valida com o cliente, e depois troca pelas chaves do cliente.
- **Medição de tokens em tudo é obrigatória.** O Batuta mede o consumo (tokens, custo aproximado) de **todas as três IAs**, **separado por qual chave esteve em uso** em cada momento — é o que permite à consultoria saber e cobrar o que rodou na chave dela (executora, criadora ou companheira), e ao cliente acompanhar o que roda na chave própria.

**Decisão técnica relacionada — uso de plano Max do Claude:** vetado em definitivo. Os Termos de Serviço da Anthropic proíbem uso de credenciais de planos Free/Pro/Max em integrações de terceiros. O Batuta usa exclusivamente API keys pagas por uso, dos provedores oficiais (Anthropic API, OpenAI, Google, etc.).

---

## 3. O que muda no `PRODUTO.md`

O `PRODUTO.md` precisa ser revisado seção por seção. Esta seção descreve o que adapta, o que adiciona e o que remove. **Mantém-se** tudo o que não é mencionado aqui.

### 3.1. Parte I — O que é a Batuta

**Adapta:** Seção 4 ("Quem usa"). Hoje diz que o Batuta atende empresas de qualquer porte e ramo, sendo operado por uma pessoa não-técnica. Reescrever para refletir que o **operador principal do Batuta é o consultor da Lure** (perfil técnico-de-domínio, não leigo total), e que os usuários do lado do cliente entram em papéis restritos (ver seção 3.7 deste documento). O Batuta continua servindo empresas de qualquer porte e ramo, mas via a consultoria.

**Mantém:** seções 1, 2 e 3 (frase única, metáfora do maestro, princípio da composição). Permanecem inalteradas.

### 3.2. Parte II — A anatomia

**Mantém integralmente.** As seções 5 a 15 descrevem o motor já construído e validado. Não tocar.

### 3.3. Parte III — Quando as coisas dão errado

**Mantém integralmente.** As seções 16 a 23 descrevem decisões de design já implementadas e validadas.

### 3.4. Parte IV — O lado administrativo e do negócio

**Reescreve significativamente.** Toda esta parte foi escrita assumindo SaaS público com BYOK + mensalidade. Com a Virada 1, encolhe drasticamente.

**Seções que ficam, com adaptação:**
- **§25 — Medição de uso (informativa):** mantém o conceito, agora com a granularidade adicional descrita na Virada 5 (separação de consumo por chave em uso ao longo do tempo no projeto).
- **§26 — Cofre de chaves:** mantém o conceito, agora com a estrutura descrita na Virada 5 (chaves por projeto + chave padrão da consultoria + chaves de instrumentos como antes).
- **§28 — Membros e papéis:** substituída pela seção 3.7 deste documento (papéis novos e finalizados).
- **§31 — Auditoria:** mantém, ganha peso (ver seção 3.7 sobre rastreabilidade de ações de admin).
- **§32 — Painel do operador:** redefinido. Não é mais "painel SaaS para o dono da Batuta". É **painel de gestão interna da consultoria**: visão dos projetos ativos por cliente, status de cada um, consumo da chave da consultoria por projeto, alertas operacionais. Função interna, escopo enxuto.

**Seções que saem:**
- **§24 — Modelo de cobrança BYOK + mensalidade fixa:** elimina. A cobrança é feita pela consultoria, fora do produto.
- **§27 — Planos da plataforma:** elimina. Não há planos.
- **§29 — Billing da plataforma:** elimina. Não há billing automatizado dentro do produto.
- **§30 — Inadimplência:** elimina. Trato comercial fora do produto.
- **§33 — Suporte e onboarding:** redefinido como **interno** — onboarding de novos consultores da Lure, materiais internos, canal de suporte da própria consultoria. Não é mais um sistema de suporte público.
- **§34 — Termos legais:** redefinido. Sai o aspecto de "termos de consumidor". Permanece, e cresce em importância, o aspecto **LGPD**: dados de pacientes, menores, financeiros que trafegam pela ferramenta usada pela consultoria continuam sob regulação séria. Contrato comercial entre Lure e cliente cobre as obrigações; o produto sustenta as obrigações técnicas (criptografia, retenção, isolamento).

### 3.5. Adicionar — Os três tipos de IA

Acrescentar uma seção nova na Parte II descrevendo formalmente os três tipos de IA do Batuta (Virada 4). Texto-âncora:

> O Batuta tem três tipos de IA, conceitualmente distintos, mesmo que possam usar o mesmo modelo subjacente.
>
> A **IA executora** vive dentro dos Agentes que processam as tarefas reais do cliente. É ela que lê o recibo, classifica a mensagem, redige o artigo. Consome a chave de API do projeto (ou, na ausência dela, a chave padrão da consultoria).
>
> A **IA criadora** é a porta de entrada para construir coisas no Batuta. O consultor conversa com ela; ela propõe a estrutura do time, escreve os markdowns, configura os instrumentos, e — com a aprovação do consultor — executa a criação. Consome a chave configurada no projeto para ela ou, na ausência, a chave padrão da consultoria — a escolha cabe ao admin, e o que consumir é sempre medido.
>
> A **IA companheira** vive junto do projeto após sua criação. Ela tem memória de tudo o que foi conversado e construído, conhece o estado atual do projeto, e responde a perguntas, sugere alterações, ajuda a diagnosticar problemas. É o que torna o projeto vivo no Batuta — não algo que foi criado e abandonado. Consome a chave configurada no projeto para ela ou, na ausência, a chave padrão da consultoria — a escolha cabe ao admin, e o que consumir é sempre medido.

### 3.6. Adicionar — A camada conversacional e a memória da IA companheira

Acrescentar seção descrevendo as três camadas que sustentam a memória da IA companheira (referida na Virada 3):

- **Histórico de conversas do projeto** — armazenado em tabela própria, ligado ao projeto, recuperado em resumo na abertura de cada nova conversa.
- **Conhecimento estrutural** — a IA tem ferramentas (no padrão de tool use) para consultar, sob demanda, o estado atual do projeto: quais agentes existem, quais instrumentos, últimas execuções, resultados, configurações. Não carrega tudo na janela de contexto; busca quando precisa.
- **Memória de longo prazo destilada** — fatos, decisões e preferências importantes do projeto são guardados para recuperação posterior. **[Atualizado 2026-07-26]** Na implementação real (ver `docs/ARQUITETURA.md §4/§7`), essa memória ficou **destilada, SEM vetor/embeddings** — decisão do maestro: um projeto acumula poucas memórias curtas que cabem no contexto, então a recuperação é por recência/filtro simples. A ideia de "embeddings/memória vetorial" deste parágrafo original **não** foi adotada (segue como possibilidade futura, não como estado atual).

**Princípio de isolamento:** a memória de um projeto **nunca** vaza para outro. A engenharia dessa separação é crítica e segue o princípio de isolamento entre clientes já vigente no produto.

### 3.7. Membros e papéis (substitui a §28 original)

Adicionar seção formal substituindo a §28 original. Conteúdo final:

> **Três papéis, e somente três:**
>
> - **Admin** — poderes plenos. Troca chaves de API (do projeto e, se for admin da consultoria, a chave padrão). Convida e desativa usuários. Cria e desativa projetos e times. Deleta histórico. Exporta dados do projeto. Vê todo o uso e custos.
>
> - **Operador** — operacional do dia a dia. Cria e edita Agentes, Instrumentos e Automações. Dispara execuções. Arquiva execuções. Vê o uso e custos dos projetos a que pertence. **Não** troca chaves, **não** convida ou desativa usuários, **não** deleta projetos ou times, **não** deleta histórico.
>
> - **Observador** — só vê o que acontece nos projetos a que pertence. Responde portões de aprovação humana. Responde perguntas pontuais do agente quando o fluxo pausa. **Não** altera nada.
>
> **Princípios fundamentais:**
>
> 1. Identificação de quem é consultor da Lure ou usuário do cliente fica no email/nome — não há papéis separados por origem.
> 2. Admin pode ser de qualquer origem. Isso é deliberado: garante autonomia do cliente caso o contrato de consultoria encerre, permitindo que admin do lado do cliente continue conduzindo o Batuta sozinho.
> 3. Acesso é por convite explícito. Ninguém se autoinscreve. Convite é emitido por um admin.
> 4. Isolamento entre clientes é absoluto. Um usuário de um cliente **nunca** acessa, vê ou influencia dados de outro cliente, sob nenhuma circunstância.
> 5. Permissões são por papel, não por usuário individual. O Batuta não suporta exceções caso-a-caso.
>
> **Regra de polegar para ações futuras não previstas:**
>
> Quando uma ação nova surgir e não estiver explicitamente atribuída a um papel, aplica-se a regra:
> - Ação **destrutiva ou sistêmica** (apagar, trocar configuração crítica, mexer no acesso): só admin.
> - Ação **operacional** (criar, editar, executar, arquivar dentro do dia a dia): operador também.
> - **Observar**: todos.
>
> **Auditoria:** toda ação relevante (troca de chave, criação ou exclusão de projeto/agente/instrumento, aprovações de portão humano, alteração de markdowns de agente em produção, alteração de papéis) fica registrada nominalmente com data, hora e usuário responsável.

### 3.8. Parte V — O que ainda precisa ser decidido

**Reescreve.** As decisões da versão atual estão resolvidas pelas viradas. Substituir por uma lista nova de pontos em aberto que efetivamente subsistem:

- Política de retenção de dados (por quanto tempo o Batuta guarda históricos de execução e conversas antes de eventual remoção/arquivamento).
- Política de exportação de dados (formato exato, granularidade, frequência).
- Política de memória da IA companheira (qual o horizonte de detalhe que ela retém; quando e como uma decisão sai da memória ativa e vai para a memória destilada).

### 3.9. Parte VI — O que não é a Batuta

**Adapta:** adicionar à lista de "não é":
- Não é um SaaS público vendido a empresas em geral.
- Não é um sistema de billing nem de cobrança recorrente automatizada.
- Não usa, sob nenhuma circunstância, credenciais de planos Free/Pro/Max do Claude (ou equivalentes de outros provedores) — somente API keys oficiais.

---

## 4. O que muda no `BUILD-PLAN.md`

A Etapa 1 está concluída e validada — não se mexe nela. A migração afeta exclusivamente a Etapa 2.

### 4.1. Reorganização da Etapa 2

A Etapa 2 original tinha sete fases (6 a 12). Com as viradas, ela encolhe e se reorganiza em **cinco fases**, na seguinte ordem sugerida:

**Fase 6 — Identidade e papéis**
- Substituir o usuário fixo de testes por login real (Supabase Auth).
- Implementar os três papéis (admin, operador, observador) com as regras da seção 3.7 deste documento.
- Sistema de convites e desativação de usuários.
- Auditoria nominal das ações sensíveis.

**Fase 7 — Cofre de chaves por projeto**
- Cofre criptografado para chaves de API.
- Chave padrão da consultoria + chave por projeto + fallback automático.
- Tela de troca de chave (apenas admin).
- Medição de uso refinada — separação de consumo por qual chave esteve em uso ao longo do tempo no projeto.

**Fase 8 — Identidade visual**
- Aplicar o `DESIGN-SYSTEM.md` sobre as telas cruas do core.

**Fase 9 — Camada conversacional de criação (IA criadora)** — IMPLEMENTADA
> **Revisão de paradigma (2026-06-07):** a Fase 9 foi entregue primeiro em "modo
> rascunho + 3 modos + Aprovar e criar time", e depois **redesenhada** para o
> paradigma definitivo abaixo (que também absorve a parte conversacional da Fase 10).
- Tela de chat para criação de projeto/time por conversa.
- Tool use para a IA executar as operações do Batuta (criar time, agente, configurar
  instrumento, montar automação) escrevendo no **time real**, por uma porta única e
  validada (`cerebro/criacao/servicos.py`).
- **Uma IA, uma conversa que nunca termina:** investiga, monta, ativa e mantém
  (edita/diagnostica/conserta) — sem ritual de "aprovar e criar". Não há mais rascunho
  em JSON nem os 3 modos.
- **Segurança por ativação** (ver §6.4, revisto): tudo é real mas DORME até o consultor
  ATIVAR; a parede de ativação exige portão humano antes de ação irreversível.

**Fase 10 — IA companheira de projeto** — parcialmente absorvida pela Fase 9
- A parte "conversa viva que continua sobre o projeto" **já está pronta**: é a mesma
  conversa única e eterna da Fase 9 (a IA criadora e a companheira viraram uma só).
- Tool use para a IA consultar o estado do projeto (agentes, instrumentos, automação) —
  já existe (`ver_time` e a fotografia do time injetada a cada turno).
- **Falta** (escopo remanescente da Fase 10): memória vetorial de longo prazo para
  fatos/decisões/preferências, com isolamento estrito entre projetos.

**Fase adicional — MCP e instrumentos restantes** (era a Fase 8 antiga, deliberadamente adiada na Etapa 1)
- Conectar instrumento de MCP.
- Demais tipos de instrumento previstos no `PRODUTO.md` §13 que ainda não foram implementados, entrando no mesmo encaixe já validado na Etapa 1.
- Esta fase pode ser inserida onde fizer mais sentido na ordem — sugestão: entre 7 e 8, antes da identidade visual e da camada conversacional, pois enriquece o que essas podem usar.

**Fase de Design hi-fi — realizar o handoff por inteiro** — CONCLUÍDA (2026-06-09)
- Inserida na execução (não estava na lista original): a Fase 8 aplicou só a marca; esta realizou o handoff `docs/design/` tela a tela (shell de sidebar, dashboard rico + edição pelo dashboard, inspeção, painel da companheira em 3 camadas, placeholders, polimento). Detalhe no `BUILD-PLAN.md`.

**Fase de Mensageria (WhatsApp) — o canal do Líder** — ADICIONADA (2026-06-09)
- **Lacuna corrigida:** o `PRODUTO.md` §10 prevê o WhatsApp como o canal do Líder (cada time com seu número), mas o core adiou isso "para a Etapa 2" e esta reorganização original (as cinco fases acima) **não o recolheu** — caiu num vão. Esta fase fecha a lacuna.
- É um **adaptador de canal na borda** (gatilho de entrada + envio de saída), reusando o motor de execução e a espera-por-humano já validados — **não mexe no núcleo congelado**. **[Nota 2026-07-26]** Na prática, o modo *conversacional* da mensageria acabou virando um **runtime paralelo** ao motor (chama o agente por fora do disparo, sem criar execução) — exatamente o "segundo motor" que o **Programa de Unificação de Estado** (`docs/UNIFICACAO-ESTADO.md`) vai absorver para dentro do motor único.
- **Decisão (2026-06-09, revista):** provedor = **Evolution API** — o vínculo é por **QR code, sem fricção** (o Cloud API oficial não faz QR; exige burocracia da Meta). Trade-off: não-oficial, risco de ban → mitigar com número dedicado por time e uso humano. **Cloud API = upgrade futuro** para quem exigir oficial. Detalhe e Definition of Done no `BUILD-PLAN.md`.
- **Depende da URL pública** da implantação → executar junto com / logo após a fase final.

**Fase final — Implantação em produção**
- Publicação no Railway, domínio definitivo, teste de ponta a ponta. Dá a URL pública HTTPS de que a Mensageria (WhatsApp) precisa.

**Fase — Automações como GRAFO (construtor visual)** — ✅ **NO AR E VALIDADA AO VIVO EM PRODUÇÃO (2026-06-17, `main`=`64d0088`).** Maestro validou: montar/Salvar, **nó inicial**, **arrastar**, **bifurcação/loop**, **Rodar**, e **portão aprovado por Telegram + pela tela**. 285 testes. Correção de raiz do "nó inicial" (fonte única `cadeia.inicial`; front `normalizarCadeia` espelha `grafo._completar`; arestas via `useUpdateNodeInternals`). Pendente só: aplicar o drop adiado `apv00drop001` quando o maestro autorizar.
- **Lacuna corrigida:** a aba Automações nasceu como **lista linear** (rápida para provar o core); ao montar times reais com bifurcações/loops virou gargalo. Esta fase a substituiu por um **construtor de grafo** (React Flow; handoff `docs/design_handoff_automacoes_grafo/`), aproveitando que o motor **já** executa grafo.
- **Decisões do maestro (2026-06-16):** (1) **adaptar** o motor atual ao novo formato de `cadeia` (lista de nós tipados) — **não** migrar para LangGraph nativo; (2) **integrar a aprovação por canal** (Telegram) no nó com portão (absorveu a config por-automação `apv00canal001`). Detalhe e Definition of Done no `BUILD-PLAN.md` ("FASE — Automações como GRAFO").
- **Como ficou (2 desvios para proteger a produção):** (1) **sem migração de dados** — o motor **normaliza na leitura** (lê o shape antigo e o novo); só a coluna aditiva `passos_execucao.no_id` foi aplicada (`gra00grafo001`). (2) o drop da coluna `aprovacao_instrumento_id` (`apv00drop001`) é aplicado **pós-deploy** (subir o código que não a usa antes — lição `una00prov001`).
- **Cuidado/exceção registrada:** diferente das outras fases, esta **toca o parser do motor** (`orquestracao/cadeia.py`) para ler o novo shape — evolução **autorizada pelo maestro**; o laço de execução de um agente (`agente.py`) permanece intocado. Ver a exceção registrada na §6.1 (item 1).

### 4.2. O que sai da Etapa 2 original

Eliminadas do escopo (conforme Virada 1):
- Planos da plataforma.
- Cobrança recorrente via Stripe.
- Painel de billing do cliente.
- Fluxo de inadimplência automatizado.
- Onboarding público.
- Suporte público.
- Termos de consumidor (sai a forma; a substância de LGPD entra como cláusula contratual entre Lure e cliente, fora do produto, com sustentação técnica dentro).

### 4.3. Definition of Done de cada fase nova

Quando o Claude Code for detalhar cada uma das fases novas (6 a 10), seguir o mesmo padrão das fases da Etapa 1 já validadas: tarefas em formato investigar/implementar/verificar, Definition of Done concreto com prova de execução, commit + push ao fim de cada fase.

---

## 5. Estrutura de dados — adições mínimas

Esta seção descreve **somente o que precisa ser acrescentado** ao modelo de dados existente. As tabelas atuais não se alteram em estrutura — apenas ganham vínculos em pontos específicos. O Claude Code, ao implementar, deve usar migrations aditivas, **nunca destrutivas**, sobre o banco já em uso.

**Adições novas:**

- **`usuarios`** — registros das pessoas com acesso ao Batuta. Inclui email, nome e vínculo ao sistema de autenticação (Supabase Auth na Fase 6).
- **`membros`** — relação de quais usuários pertencem a quais organizações, com qual papel (admin / operador / observador). Um usuário pode ser membro de várias organizações com papéis diferentes em cada uma.
- **`convites`** — convites pendentes (email convidado, organização, papel proposto, status, quem convidou, quando expira).
- **`chaves_api`** — cofre criptografado. Vínculo a um nível (projeto/time específico, ou nível "padrão da consultoria"), provedor (Anthropic, OpenAI, Google, etc.), e o valor da chave criptografado.
- **`conversas_projeto`** — histórico de conversas da IA criadora e da IA companheira por projeto. Vínculo a um projeto, lista de mensagens, datas.
- **`memoria_projeto`** — entradas destiladas para recuperação semântica. Vínculo a um projeto, conteúdo, embedding, metadados.
- **`auditoria`** — registros nominais de ações sensíveis (quem, o quê, quando, em qual recurso, qual o estado antes e depois quando aplicável).

**Mudança em tabela existente:**

- **`organizacoes`** — o campo "dono" hoje aponta para o usuário fixo de testes. Após a Fase 6, o vínculo passa a ser via tabela `membros` (relação muitos-para-muitos), em vez de um dono único. O campo legado pode ser mantido temporariamente como `dono_inicial` para preservar histórico, mas a permissão real passa a vir de `membros`.

**Detalhes finos** (tipos exatos de cada campo, índices, regras de criptografia da `chaves_api`) ficam para o Claude Code definir na implementação, seguindo a documentação oficial das ferramentas em uso (Supabase, Postgres) e validando com o maestro nas tarefas correspondentes.

---

## 6. Como executar a migração — instruções operacionais para o Claude Code

Esta seção é dirigida ao Claude Code. Lê com atenção; ela governa o **como** desta migração.

### 6.1. Princípios não-negociáveis

1. **O motor evolui por decisão dirigida — nunca por reescrita cega.** *(Princípio atualizado em 2026-07-26; substitui o "núcleo intocável" original, cujo custo estrutural está explicado na "Evolução de governança" ao final deste item.)* A orquestração de agentes, o LangGraph, a espera-por-humano, os gatilhos, a tela de inspeção, os instrumentos já construídos são o **core validado — precioso e protegido**. A regra **padrão** continua sendo **estender e adicionar**, não refatorar por impulso. Mas quando o produto **exige** mudar o motor (e a experiência mostrou que exige), a mudança é **autorizada de forma formal, aditiva, faseada e aprovada-antes**, com rede de testes máxima — jamais um rewrite às cegas. Se uma fase parece exigir mudança no núcleo, **pare, dimensione o impacto e alinhe com o maestro** um aditivo curto a esta seção antes de prosseguir (o formato do precedente de 2026-06-16).
   - **Exceção autorizada (2026-06-16):** a **FASE — Automações como GRAFO** muda o **formato do `cadeia`** (de dict por-agente para lista de nós tipados), o que **toca o parser do motor** (`orquestracao/cadeia.py`: `validar_cadeia`/`executar_cadeia`) e a retomada (`mensageria/retoma.py`). O maestro autorizou essa evolução explicitamente (foi perguntado e decidiu *adaptar* o motor, não reescrevê-lo para LangGraph nativo). O **laço de execução de um agente** (`agente.py`, o `create_react_agent`) permanece **intocado**. Este é o **precedente formal** do mecanismo de evolução dirigida.
   - **Evolução de governança (2026-07-26) — por que a regra mudou:** a trava absoluta ("intocável, em nenhuma circunstância") foi prudente para proteger o core recém-validado, mas teve um custo estrutural: empurrou tudo o que era novo para a **borda**, e a mensageria, em vez de estender o motor, virou um **segundo motor** paralelo e incompatível (diagnóstico em `docs/REMODELAGEM-MOTOR.md §2`; o maestro: *"escreveram que era intocável, e agora temos 2; daqui a pouco teremos 3"*). Fica autorizada a **direção** de unificar os dois motores numa timeline única — o **Programa de Unificação de Estado** (`docs/UNIFICACAO-ESTADO.md`), **prioridade nº 1**. **Permanecem congelados** (não se tocam nem no rewrite): a semântica de `seguir_para`, a garantia HITL antes de ação irreversível, o contrato de instrumentos, a fila `FOR UPDATE SKIP LOCKED`, o laço `create_react_agent` do agente, e o heartbeat/sweeper/recuperação de órfãos (lei `CLAUDE.md §12-A`). A suspensão para tocar `cadeia.py`/`agente.py`/modelo `PassoExecucao` é **cirúrgica e só antes da Fatia 4** do programa, por novo aditivo aprovado (ver `REMODELAGEM-MOTOR.md §7`). **Execução de código aguarda sinal explícito do maestro.**
   - **Suspensão dirigida do congelamento nº 2 — Fatia 4 (2026-08-04, autorizada pelo maestro):** o maestro aprovou explicitamente a Fatia 4 da remodelagem (`docs/REMODELAGEM-MOTOR.md §5/§7`) — o portão como passo `espera_humano` unificado. Fica suspenso o congelamento, de forma **aditiva e cirúrgica**, **apenas** nestes pontos: **(1)** `modelos.py` → `PassoExecucao` ganha a coluna `tipo` (nulável: `agente`|`roteador`|`espera_humano`|`mensagem_entrante`; migração puramente aditiva); **(2)** `orquestracao/cadeia.py` e `orquestracao/agente.py` podem ser tocados para carimbar o passo de portão como `espera_humano` e para unificar a retomada num caminho só (`_turno_de_portao` vira adaptador fino). **Permanece intocável** (repete a lista de 2026-07-26): a semântica de `seguir_para`, a garantia HITL antes de ação irreversível, o contrato de instrumentos, a fila `FOR UPDATE SKIP LOCKED`, o laço `create_react_agent`, e o heartbeat/sweeper/recuperação de órfãos-presos (§12-A). A suspensão é para **absorver a borda de conversa para dentro do motor**, faseada (sub-fatias 4.1→4.3) e testada — **não** para reescrever o motor. A adoção de persistência entre turnos (checkpointer nativo do LangGraph × solução caseira), da sub-fatia 4.3, é **decisão à parte**, a ser trazida com a documentação oficial lida (§9) e o estudo de tokens, antes de qualquer código dela.

2. **Migrations no banco são aditivas, nunca destrutivas.** Você adiciona tabelas e colunas; não apaga nem renomeia o que já tem dados em produção interna. Onde for inevitável uma transformação (como o caso de `organizacoes.dono` migrando para a tabela `membros`), faz-se em duas etapas: adiciona o novo, popula com base no existente, e só então — depois de validação — descontinua o antigo.

3. **Protocolo de execução do `CLAUDE.md` continua valendo integralmente.** Cada tarefa segue investigar / planejar / implementar / verificar / decidir / relatar. Pare no primeiro erro. Commit + push ao final de cada fase. Nada do método muda.

4. **As fases desta Etapa 2 são executadas na ordem proposta na seção 4.1.** Não pule. Cada uma se apoia nas anteriores: papéis vêm antes de cofre (porque admin é quem troca chave), cofre vem antes da camada conversacional (porque a IA criadora consome chave), identidade visual vem antes ou em paralelo às camadas de IA (porque é mais agradável conversar com uma interface bonita).

### 6.2. Antes de iniciar a primeira fase desta migração

1. Lê os quatro documentos do projeto na íntegra (`PRODUTO.md`, `CLAUDE.md`, `BUILD-PLAN.md`, `DESIGN-SYSTEM.md`) e este `MIGRACAO.md`.
2. Rode `git status` e `git log --oneline -10` para situar-se no estado atual do repositório.
3. Crie uma branch dedicada à migração (sugestão: `migracao-etapa-2`), para que o trabalho seja revisável antes de chegar a `main`. Não trabalhe direto em `main` durante a Etapa 2 inteira — só faça merge ao final de cada fase com Definition of Done verde, conforme padrão já estabelecido.
4. Propõe ao maestro um plano detalhado da **Fase 6** (a primeira) no formato das fases da Etapa 1, e espera aprovação antes de implementar.

### 6.3. Atualização dos documentos do projeto

Este `MIGRACAO.md` é o documento de transição. As mudanças que ele descreve devem, com o tempo, ser **incorporadas aos documentos vigentes**:

- Conforme cada fase desta migração for concluída e validada, atualize o `PRODUTO.md` para refletir o que mudou (usando esta migração como referência das mudanças). Não reescreva o `PRODUTO.md` de uma vez antes do trabalho começar — atualize-o à medida que cada parte fica pronta.
- Atualize o `BUILD-PLAN.md` removendo o esqueleto antigo das fases 6 a 12 e substituindo pelas fases novas detalhadas conforme você executá-las.
- O `CLAUDE.md` e o `DESIGN-SYSTEM.md` permanecem como estão. O método não muda; a identidade visual não muda.
  - **Atualização (2026-06-06):** por decisão do maestro, ambos **foram atualizados** para incorporar o **handoff de design hi-fi** recebido, agora versionado em **`docs/design/`** (com `README.md`). Esse handoff é a **fonte da verdade de telas/layout/UX** das Fases 8–10 (criação AI-first, dashboard, inspeção de execução, IA companheira) e define o **shell em sidebar escura** (a casca definitiva — o header da Fase 8 evolui para ela). Toda doc que a IA lê (`CLAUDE.md` §13/§17, `DESIGN-SYSTEM.md`, `BUILD-PLAN.md`, `interface/AGENTS.md`) aponta para `docs/design/`.

Quando todas as fases desta migração estiverem concluídas e os documentos vigentes refletirem o estado final, este `MIGRACAO.md` pode ser arquivado em um diretório `docs/historico/` — não apagado, pois é registro da decisão.

### 6.4. Pontos de cautela específicos

- **Substituição do usuário fixo de testes (Fase 6):** este ponto é delicado. O usuário fixo está embutido em vários lugares do cérebro. Ao introduzir o sistema de autenticação real, garanta retrocompatibilidade — execuções e dados criados pelo usuário fixo devem ser corretamente migrados para o admin real correspondente. Faça em passo único, com testes, sem perder histórico.

- **IA criadora executando criação no Batuta (Fase 9):** este é o ponto de maior risco da migração inteira — a IA chama operações que **escrevem no banco**. **Modelo de proteção (revisto em 2026-06-07):** abandonamos o "modo rascunho" (nada é real até aprovar) em favor de **"tudo é real mas DORME até ativar"**. A IA escreve no time real desde o começo, mas a automação nasce **inativa** e **nada dispara** até o consultor ATIVAR. A única parede técnica é a **ativação**: um agente com instrumento de **ação irreversível** (publicar/enviar/gravar em sistema externo) só pode ser ativado se a cadeia tiver **portão de aprovação humana (`pausa_humano`) no nó anterior** a ele — o app recusa a ativação caso contrário. Salvaguardas que permanecem: automação inativa por padrão, toda ação da IA auditada, papéis e isolamento por organização. (Por que mudou: o ritual de "aprovar e criar" entregava raso e a conversa morria; consertar conversando é melhor, e o risco real — disparar no mundo sem aprovação — é exatamente o que a parede de ativação cobre.)

- **IA companheira e contaminação de memória (Fase 10):** o isolamento entre projetos é absoluto. Use a chave do projeto como **chave de partição obrigatória** em todas as consultas à memória vetorial. Teste explicitamente: crie dois projetos com nomes parecidos, popule memórias distintas em cada um, abra conversa em um deles e confirme que a IA não recupera, em momento algum, memória do outro. Esse teste é parte do Definition of Done da fase.

- **Auditoria desde o primeiro dia da Fase 6:** não adie a auditoria para "fase de polimento". Cada ação de admin (troca de chave, criação de usuário, mudança de papel) deve ser registrada nominalmente já na primeira vez que ocorrer no ambiente real. Vai ser preciso pra resolução de disputa um dia.

---

## 7. Para o maestro

O Batuta deixa esta migração mais simples do que estava, não mais complexo. A eliminação do aparato de SaaS público remove muito mais coisa do que as duas adições (camada conversacional e IA companheira) somam. O motor central, que era a parte difícil, está construído e validado.

O que falta é trabalho — bastante trabalho —, mas é trabalho do tipo que escala com paciência: cada fase entrega uma capacidade que se compõe com as anteriores. Não há retrabalho previsto sobre o núcleo.

Sugestão de ritmo: **uma fase por sessão de trabalho conjunta com o Claude Code**, igual ao ritmo que funcionou na Etapa 1. Não acelerar; não pular. O portão de validação da Etapa 1 foi conquistado por disciplina, e a Etapa 2 se conquista pelo mesmo método.
