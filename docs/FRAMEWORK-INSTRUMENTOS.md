# Framework de Instrumentos — Plano Completo (Construtor + Central + IA criadora + Marketplace)

> **Status:** ▶️ **EM EXECUÇÃO (sinal dado 2026-08-12).** **Fatias 0–2 + 4 ✅ NO AR** — motor do conector (`3163721`)
> + o **Construtor de Instrumento** (`c7db8ab`, tela do mockup validado + backend "testar e detectar") + a **IA
> criadora monta o conector** (Fatia 4: `montar_conector`/`testar_operacao_conector` + capítulo da Central; ver §6);
> tsc/eslint/build limpos; ver §11. **Próxima: Fatia 2.5** (biblioteca da org — escopo org-wide) ou **Fatia 3** (importar OpenAPI).
> Mockup validado (2026-08-12, artefato `435b0bdf`). **Sequência:** convive com a **prioridade nº 1**
> (Unificação de Estado, `docs/UNIFICACAO-ESTADO.md`); a *semente barata* (o tipo "conector" + o construtor)
> pode começar antes do marketplace, pois ajuda o maestro **já** e toca pouco o motor. Governança:
> `MIGRACAO §6.1` (evolução dirigida) — mas quase tudo aqui é **borda** (um novo tipo de instrumento + UI +
> ferramentas da criadora), não o núcleo.
>
> **Decisões do maestro em 2026-08-12** (nome="Instrumento" + botão "🌟 Criar instrumento"; escopo de organização;
> substituir os instrumentos existentes por este modelo, com a fronteira dos 3 grupos; credenciais moram no
> instrumento): registradas em **§5.7–5.9** e **§12**.

> **Origem (2026-08-11/12):** ideia do maestro, inspirada na **loja de plugins do Bubble.io** ("desenvolvedores
> criam mini-aplicações que outros usam"). Quer um **framework self-service**: hoje, todo instrumento novo
> precisa ser codado por mim; o framework deixa **ele — ou um dev — criar sozinho**. Dor concreta: usa muito o
> Bubble e "1 endpoint = 1 instrumento REST"; e integrações "só da minha conta" (Instagram/Google pessoais)
> não precisariam de App Review. Documentação do Bubble estudada (API Connector, Actions, Publishing) — os
> insights estão embutidos aqui.

---

## 1. Visão em uma frase

Um **Construtor de Instrumento** onde qualquer pessoa monta um instrumento novo **em formulário, sem código** —
e, no futuro, um **marketplace** onde terceiros publicam os seus. Construído **sobre** o contrato
`TipoInstrumento` que já existe (`instrumentos/base.py`), não um sistema novo.

**Ganho imediato do maestro (independe do marketplace):**
- Mata a dor "1 endpoint = 1 instrumento": um **conector multi-operação** (vários endpoints num instrumento só).
- Destrava integrações **pessoais** (o próprio app da Meta/Google, só a conta dele) → **sem App Review**, sem
  depender de mim.

---

## 2. O trilema (a física do problema) e a estratégia em camadas

Quando um **estranho** cria um instrumento, escolhe-se **2 de 3** — nunca os três:
**(A)** código de lógica qualquer · **(B)** o dev não hospeda servidor próprio · **(C)** o Batuta não constrói
um *sandbox* (caixa de areia p/ código de estranho).

| Nível | O que o dev faz | Onde roda o código | Trilema | Quando |
|---|---|---|---|---|
| **1. Conector declarativo** | preenche um formulário (endereços, campos, auth) | é **dado**, não código | B + C | **o foco desta Fase 2** |
| **2. Traga seu endpoint** | escreve código e **hospeda** (MCP/webhook) | servidor **do dev** | A + C | **MCP já no ar**; falta SDK público |
| **3. Código hospedado** | escreve código, **o Batuta roda** | cérebro (sandbox) | A + B | aposta grande, **adiada** |

A maioria dos 26 instrumentos de hoje é "conversar com uma API" → **cabe no Nível 1**. Só `gerar_pdf`/`sql`/mídia
com laço de espera precisam de código (Nível 2/3). Os internos (`agendar_automacao`, `arquivar_imagem`,
`descrever_imagem`, `mcp`) seguem sendo de 1ª parte.

---

## 3. Onde encaixa no que JÁ existe (estender, não reescrever)

O contrato `TipoInstrumento` (`instrumentos/base.py`) já entrega quase tudo que um framework precisa:

| Peça existente | O que já resolve | Papel no framework |
|---|---|---|
| `TipoInstrumento` (contrato) | forma comum: `tipo`/`Config`/`Args`/`executar` | é o "SDK" interno; o construtor gera/edita instâncias |
| `expandir_ferramentas(config)` | **um instrumento → várias ferramentas** (o MCP usa) | o conector expõe **N operações** como N ferramentas |
| `Config` / `Args` / `campos_secretos` | fixo × variável × segredo | os papéis **Fixo / IA / Segredo** dos campos |
| Cofre (7-B) + `chave_compartilhada` + credenciais nomeadas | segredos cifrados, injetados na execução | auth do conector, sem segredo em claro |
| `acao_irreversivel` / `irreversivel_para` | deriva do tipo+config; **fonte única da parede** | **Ação × Só-leitura** por operação → portão automático |
| `campos_resposta` (`instrumentos/rest.py`) | enxuga a resposta, corta custo de tokens | o "testar e detectar → marcar campos" |
| `FalhaInstrumento` (retentável/não) + backoff | semântica de falha honesta | tratamento de erro do conector (§12-A) |
| `mcp.py` + `expandir_ferramentas` | conecta servidor MCP externo | **o Nível 2 já funciona hoje** |

**Conclusão:** o framework é, no motor, **um novo `TipoInstrumento` "conector"** cuja `Config` é uma **lista de
operações** + `expandir_ferramentas` que as transforma em ferramentas. **Nenhum motor novo.**

---

## 4. Os 5 padrões (do estudo do Bubble) → especificação

| Padrão do Bubble | No Construtor do Batuta | Aproveita |
|---|---|---|
| **1. Auth por menu** (None/chave/Basic/OAuth2/JWT) | dropdown de tipos de autenticação | cofre + `chave_compartilhada` |
| **2. `[colchete]` na URL** cria o campo | escrever `[id]` no endereço → argumento criado sozinho | gera o `Args` |
| **3. Campo Público/Privado/Secreto** | seletor **IA / Fixo / Segredo** por campo | `Args` / `Config` / `campos_secretos` |
| **4. "Inicializar" detecta a resposta** | botão **"Testar e detectar"** → marcar campos a trazer | **é o `campos_resposta`** |
| **5. "Ação" × "Dado"** | badge **Ação (irreversível)** × **Só leitura** | `irreversivel_para` → **parede** |

Insight extra do Bubble já resolvido melhor no Batuta: o Bubble **re-tenta** chamadas > 150 s (risco de
cobrar/enviar em dobro) e avisa "a função roda várias vezes"; o Batuta já trata isso com `retentável` +
**parede antes do irreversível** + o *caveat do re-run contido* (Fatia 4.3).

---

## 5. O Construtor de Instrumento (Nível 1) — especificação

### 5.1 Modelo de dados (aditivo, sem tabela nova)

Novo tipo de instrumento (nome a decidir — **decisão aberta**, ver §12), cuja `Config` guarda:

```
{
  auth: { tipo: "bearer" | "header" | "url" | "basic" | "oauth2" | "nenhum",
          config: {...}, campo_secreto: "access_token" },  // segredo → cofre
  operacoes: [
    {
      nome: "Publicar foto",
      descricao: "…",                       // a IA lê isto p/ decidir acionar
      metodo: "POST",
      url_template: "https://…/[id_conta]/media",   // [colchete] vira campo
      campos: [
        { nome:"image_url", papel:"publico", descricao:"…" },   // → Args (IA)
        { nome:"id_conta",  papel:"fixo", valor:"178414…" },    // → Config
        { nome:"access_token", papel:"secreto" }                 // → cofre
      ],
      corpo_template: {...},                 // opcional (POST/PUT)
      campos_resposta: ["id","permalink"],   // do "detectar"
      irreversivel: "auto" | "sim" | "nao"   // auto = deriva do método
    }
  ]
}
```

- **`expandir_ferramentas(config)`** → para cada operação, uma `StructuredTool`: `Args` = os campos `publico`;
  `executar` = monta a chamada (url + fixos + segredos do cofre + args), aplica `campos_resposta`, devolve. **Reusa
  o executor do `rest.py`** (HTTP + `_projetar_registros` + `validar_cabecalhos_ascii` + `FalhaInstrumento`).
- **`irreversivel_para(config)`** por operação (deriva do método; override). A parede continua funcionando **por
  operação** — de graça.
- **Persistência:** a tabela `instrumentos` (coluna `configuracao` JSONB) — **aditivo**. Segredos no cofre (já
  existe). Versionamento: ver §10.

### 5.2 As telas (o mockup validado É o spec)

Barra de seções: **Operações** (lista + editor), **Identidade**, **Autenticação**, **Testar conexão**,
**Publicar**. O editor de operação carrega os 5 padrões. Recriar em Next + Tailwind + shadcn/ui, na marca
(`DESIGN-SYSTEM.md`) — **proposta em texto antes** de mexer em tela (é UI).

### 5.3 Autenticação — tipos, faseado

- **Já-fáceis (declarativos):** Bearer, chave no cabeçalho, chave na URL, HTTP Basic, sem auth.
- **Token auto-renovável (renovação automática, sem agente):** ver §5.3.1 — resolve o token que expira
  (Instagram/Google pessoal) sem o usuário ficar trocando à mão.
- **OAuth 2.0 (login do usuário):** o mais complexo (consentimento no navegador). **Fase posterior.** Por ora,
  o usuário cola o **token do próprio app** (o "bypass" pessoal do Instagram/Google — sem App Review).

#### 5.3.1 Token auto-renovável — o sistema renova sozinho, no fundo

**Dor (levantada pelo maestro):** tokens expiram (o do Instagram dura ~60 dias); ninguém quer ficar trocando à mão.

**A forma CERTA é system-level, não um agente.** Um agente só renovaria se **rodasse** — se nenhuma automação
disparar, o token morre em silêncio. Renovação é assunto de **credencial**, não de lógica de agente: um
trabalhador automático (**agendador**) renova **antes** de expirar, independente de qualquer agente.

**O Batuta JÁ faz isso — para o Instagram:** `instagram_tokens.renovar` é chamada pelo **agendador** e "estica a
validade antes dos 60 dias" (`instagram_oauth.py`, `instagram_tokens.py`). O framework **generaliza** esse padrão
para **qualquer conector**.

**No construtor (declarativo, sem código):** um tipo de auth **"token que se renova sozinho"** onde o autor
declara **(a)** a **chamada de renovação** (endereço/método/o que enviar — o token atual ou um `refresh_token`) e
**(b)** **onde o token novo está na resposta** (ex.: `access_token`, `expires_in`). O sistema agenda e renova no
fundo, gravando o token novo no cofre. Espelha o **OAuth2 auto-renovável do Bubble** (a doc estudada exige
resposta com `access_token` + `expires_in`).

**Capacidade nova (pequena e contida — a ÚNICA peça de motor que esta parte toca):** hoje um instrumento só
**LÊ** o segredo do cofre; a auto-renovação exige o sistema **GRAVAR** o token novo de volta. O encanamento já
existe (o `instagram_tokens` já grava o token renovado) — o framework só o estende aos segredos dos conectores.
Roda no **agendador/borda**, não no laço do agente.

**Limite honesto:** a auto-renovação só funciona enquanto o token atual **ainda é válido** (renova ANTES de
vencer) ou há um `refresh_token` de longa vida. Se o token **morrer de vez**, ou se a API exigir um **login de
navegador** (consentimento OAuth completo), o sistema **não** se cura sozinho — o humano precisa **logar de novo
uma vez**. Ou seja: cobre o "esticar antes de vencer" (o caso comum, incl. Instagram); não ressuscita credencial
morta nem faz o primeiro login sozinho.

### 5.4 O `[colchete]` → campo automático

Ao escrever `[nome]` no endereço/corpo, o campo aparece na tabela de campos (papel padrão = **IA**). Espelha o
"dynamic value" do Bubble.

### 5.5 Testar e detectar → `campos_resposta`

Roda a chamada **real** uma vez (com valores de teste), lê a resposta, lista os campos com tipo, o usuário
**marca só os que interessam**. **§12-A:** se a chamada demorar, roda em **segundo plano** com heartbeat +
polling (nada de request preso). Erro honesto e reenviável (`mensagemDeErro`).

### 5.6 Importar OpenAPI/Swagger (matador) — fase posterior

Colar a especificação da API → o Batuta **gera as operações sozinho**. É como as ferramentas no-code fazem
"conector de Stripe/HubSpot". Reduz o Instagram/Google a poucos cliques.

### 5.7 Onde nasce e onde vive (decisões do maestro, 2026-08-12)

- **Nome:** continua **"Instrumento"** (sem palavra nova). O rótulo interno do tipo é técnico e invisível (comigo).
- **Entrada:** um botão **"🌟 Criar instrumento"** na **aba de Instrumentos do time**.
- **Escopo — vira biblioteca de instrumentos da ORGANIZAÇÃO:** ao criar, o instrumento é gravado **na organização**
  (disponível para **todos os times**) **e** vinculado ao **time atual** para uso imediato. Cria-se uma vez,
  reaproveita-se em qualquer time. (Hoje o instrumento é por-time — `instrumentos.time_id`; isto introduz o
  **escopo de organização** + o vínculo time↔instrumento. Aditivo.)

### 5.8 Substituir os instrumentos existentes por este modelo — a meta e a fronteira honesta

**Meta do maestro:** trocar os instrumentos de hoje por instrumentos personalizados; **nativos** só os que são
**código fechado do motor** (ex.: o agendador). Direção correta — com uma **fronteira honesta em 3 grupos** (do
estudo de §2, porque nem todo instrumento é "só uma chamada de API"):

- **(a) Nativos para sempre — tocam o interior do Batuta:** `agendar_automacao`, `arquivar_imagem`, `mcp`,
  `descrever_imagem` (usa o motor de IA). São tripas, não "chamada de API".
- **(b) Migram para o modelo personalizado (a MAIORIA — "só chamam API"):** busca web/Exa/Firecrawl, WordPress,
  Search Console, Telegram, webhook de saída, os de Instagram, `chamar_api_rest`. Viram conectores declarativos.
- **(c) Ficam nativos ATÉ o Nível 3 (precisam de código de verdade):** `gerar_pdf` (monta um PDF), `sql` (fala com
  banco), `gerar_imagem`/`gerar_video`/`gerar_video_fal` (laço "ficou pronto?"). Um conector declarativo **não
  expressa** essa lógica — ou esperam o **Nível 3** (código hospedado), ou um conector multi-passo mais esperto os
  absorve depois. A fronteira é "**tem lógica além de chamar um endereço**".

**Como migrar (sem quebrar):** instrumento por instrumento, a versão declarativa **provada equivalente** antes de
trocar; as instâncias já configuradas (Instagram/WordPress plugados) **continuam funcionando** com caminho de
migração. **Nada de big-bang.**

### 5.9 Credenciais — moram no instrumento (decisão do maestro, 2026-08-12)

Com o instrumento virando **objeto da organização** (criado uma vez, usado por todos os times), a credencial que
mora nele **já é compartilhada e única** → a **"caixa-forte de credenciais nomeadas" vira redundante para
instrumentos**: o segredo fica **no próprio instrumento**. Consequências:

- **A criptografia FICA** — o cofre que cifra o segredo continua; some só a **abstração "credencial separada"**
  (`tipos_credencial_aceitos`/`credencial_id`) para instrumentos.
- **A renovação automática (§5.3.1)** grava o token novo **no segredo do instrumento** — coerente.
- **Separado disto:** o **pool de chaves de IA compartilhadas** (`chave_compartilhada` — OpenAI/Tavily/etc. das
  funções **nativas** do Batuta) é **outra coisa** (chaves das capacidades pagas da plataforma, não credencial de
  instrumento do usuário) e pode continuar como está.
- **Migração:** as credenciais nomeadas existentes se **dobram** no instrumento que as usa.

---

## 6. A IA criadora monta o instrumento — ✅ NO AR (Fatia 4, commit `36d6cca`, 2026-08-13)

A criadora monta agentes/automações pela **porta única** dos serviços de domínio. Montar um conector é a
**mesma forma** — e é **seguro**, porque a criadora só preenche **dado declarativo** (não código).

**O que a Fatia 4 entregou:**
- **`montar_conector(conector, conector_id?)`** — cria (sem `conector_id`) ou edita (com ele) o conector com a
  **spec inteira** (identidade + auth + operações), no mesmo estilo do `montar_cadeia` (dict + docstring que
  ensina o formato). Reusa a porta validada (`servicos.configurar_instrumento`/`editar_instrumento`), que já
  separa o segredo pro cofre. **Nunca recebe o token** — descarta `auth_segredo` se vier e o deixa pendente.
- **`testar_operacao_conector(conector_id, operacao, valores?)`** — a IA **testa e detecta** sozinha (reusa
  `Conector.testar_operacao` + o cofre via `decifrar`): roda a chamada real, devolve a resposta + os campos
  detectados, para escolher `campos_resposta` e verificar (se a busca voltar o lote inteiro, ela percebe). É a
  fricção manual que o maestro sentiu, agora conversada.
- **Catálogo:** `catalogo_de_instrumentos()` passou a respeitar `oculto_no_catalogo` — o conector saiu do
  catálogo genérico (do `configurar_instrumento`) para não dar **sinal misto**: a criadora o monta pela
  ferramenta própria. O `configurar_instrumento` também aponta para o `montar_conector`.
- **Regra de segurança (já existia):** a criadora **NÃO pluga o segredo** — deixa "pendente"; **o humano cola o
  token** no cofre. Ver [[project-ia-criadora-credenciais-nomeadas]].
- **Parede:** um conector com operação irreversível só ATIVA com portão antes — a criadora já respeita a parede.
- **Fluxo:** *"quero um instrumento que busca meus projetos no Bubble"* → a criadora **consulta a Central** (§7),
  monta o conector, pede o token ao consultor, **testa e detecta** os campos, refina o `campos_resposta`.
- **Verificação:** `cerebro/testes/test_criacao_conector.py` (10 testes) — criar/editar, não-pluga-token,
  sem-auth-sem-pendente, testar+detectar (união de campos esparsos do Bubble), só-conector, Central encontrável.

---

## 7. Central de Conhecimento

Capítulos (auto-descobertos por `rglob`, `cerebro/central/`):
- ✅ **`instrumentos/construir-conector.md`** (Fatia 4) — o que é um conector, o formato do objeto (operações,
  papéis IA/Fixo, destino query/corpo/url), **como o Bubble faz busca (o `constraints` como array JSON — o erro
  do `contraints` que quebrou o teste ao vivo)**, POST/PATCH (não PUT), `campos_resposta` (custo), testar-e-detectar,
  a parede por escrita, e as duas ferramentas (`montar_conector`/`testar_operacao_conector`). **A criadora consulta
  este capítulo** (via `consultar_conhecimento`) para montar conectores certos.
- 📨 *Futuro:* `instrumentos/instrumento-pessoal-vs-saas.md` — honesto: usar **o próprio app** (Meta/Google) para a
  **própria conta** evita App Review; o preço é cuidar do token. Quando vale o SaaS.

---

## 8. Marketplace (futuro — a virada de plataforma)

Do modelo do Bubble, adaptado:
- **Distribuição:** só-esta-organização → compartilhar com organizações escolhidas → **público**.
- **Licença:** aberto (copiável) × privado. "Aberto" **irreversível** (como no Bubble).
- **Versão:** avisa quem instalou para atualizar. **Instalar ≠ poder usar** (plugin pago = uso liberado pelo
  pagamento, separado da instalação).
- **Instalar em 1 clique** por organização. Notas/instalações.
- **Revisão/segurança (a gente desenha — o Bubble não detalha):** curadoria + checagem. **Atenção honesta:** o
  conector declarativo é seguro **de execução** (só faz o HTTP que o autor declarou), mas um GET ainda pode
  **exfiltrar dados** (ler seu CRM e mandar para fora). Então **confiança/revisão importam** mesmo no Nível 1 —
  marcar origem, avisar o que o conector acessa, e a parede protege a **escrita**.

---

## 9. Níveis 2 e 3 (futuro)

- **Nível 2 — Traga seu endpoint:** publicar o `TipoInstrumento` como **SDK público** (doc + exemplos) para
  quem quer MCP/webhook. **MCP já conecta hoje.** Baixo esforço, alto valor para devs.
- **Nível 3 — Código hospedado (o "Bubble completo"):** exige **sandbox**. Opções: subprocesso isolado
  (seccomp), contêiner/microVM (gVisor/Firecracker), ou **WASM** (mais barato, porém limitado). Como no Bubble:
  **pipeline de build/deploy** (dependências tipo `package.json`, minutos), limites (tamanho/tempo/rede), e o
  `context` injeta segredos sem expor. **Aposta grande, adiada** — e mais delicada para o Batuta que para o
  Bubble (lá muito código roda no navegador; aqui, tudo no servidor).

---

## 10. Transversais (valem para todas as fases)

- **Segurança por nível:** Nível 1 seguro por construção (dado); Nível 3 precisa do sandbox. Revisão no
  marketplace mesmo no Nível 1 (exfiltração).
- **Lei §12-A:** o "testar/detectar" e o runtime — erro honesto, operação longa em segundo plano, sweeper.
- **Retrocompatível:** aditivo. Os 26 instrumentos seguem intactos; o conector é **mais um tipo**. Sem
  checkpointer/rota nova obrigatória.
- **Observabilidade:** chamadas do conector já entram no `evento_log` e no `/uso` (custo por API paga).
- **Versionamento do instrumento:** um conector evolui; automações que o usam não podem quebrar (modelo de
  versão do Bubble — decisão de profundidade na fatia do marketplace).
- **Permissões:** quem pode criar/editar/publicar instrumento numa organização (papéis — Etapa 2).

---

## 11. Faseamento (estrangulador — uma fatia por vez, protocolo de 6 passos)

| Fatia | Entrega | Toca UI? | Risco |
|---|---|---|---|
| **0. Forma** ✅ | decisões (§12) + forma travada no código (§encaixe: `TipoInstrumento` + `expandir_ferramentas`) | não | baixo |
| **1. Motor do conector** ✅ | novo tipo `conector` (`expandir_ferramentas` + executor), **sem UI**, provado por teste; reusa REST/cofre/parede/`campos_resposta` | não | baixo |
| **2. Construtor** ✅ | as telas do mockup (Operações/Identidade/Auth/Testar/Publicar) + backend "testar e detectar" | sim | médio |
| **2.5. Biblioteca da org** ◀ próxima | escopo org-wide (decisão #3): conector gravado p/ a ORG, disponível a todos os times (migração) | sim | médio |
| **3. Importar OpenAPI** | colar spec → gera operações | sim | médio |
| **4. Criadora + Central** | ferramentas da criadora p/ montar conector + capítulos novos | sim | médio |
| **5. Marketplace básico** | só-org → compartilhado → público + revisão | sim | alto |
| **6+. Nível 3 (sandbox)** | código hospedado | sim | máximo |

Fatia 1 já entrega o **valor pro maestro** (conector multi-operação p/ o Bubble) sem marketplace. Cada fatia:
plano + verificação aprovados **antes** do código; deploy e observação antes da seguinte.

**O que a Fatia 1 entregou (commit `3163721`, 2026-08-12):** `cerebro/instrumentos/conector.py` — `ConfigConector`
(`auth_tipo` nenhuma/bearer/cabecalho/query + `auth_segredo` no cofre; lista de `operacoes`), cada operação → 1
ferramenta via `expandir_ferramentas`; campos com papel **ia/fixo** e destino **query/corpo/url** (colchete `[campo]`
na URL); auth declarativa; `campos_resposta` herdado do REST; robusto a nome de campo não-identificador (ex.:
`cpo.NomeCliente`). Registrado no `__init__.py`; **oculto no catálogo** via marcador aditivo `oculto_no_catalogo`
(contrato `base.py` + filtro em `/instrumentos/tipos`) — o motor executa, a tela atual não oferece até a Fatia 2.
Zero migração, zero toque em `cadeia.py`/`agente.py`. 11 testes novos (`testes/test_conector.py`).

**Dois follow-ups nomeados (esperam uma fatia com toque ADITIVO no motor, evolução dirigida):** (a) **portão
operação-a-operação** — hoje a irreversibilidade é conservadora por instrumento (qualquer escrita → gateia tudo);
o refino "GET livre, POST gateado" exige o mapa nome→irreversível por ferramenta expandida em `agente.py`
(hoje ele aplica o valor do instrumento a todas as expandidas, igual ao MCP). (b) **retentativa/`falhas` das
ferramentas expandidas** — como o MCP, o conector não passa pelo `_ferramenta_unica` (sem `acionar_com_retentativa`
nem a promessa "nunca fingir sucesso em irreversível que falhou"); o portão já PREVINE a ação sem aprovação, mas
essa garantia fina fica para a mesma fatia de motor.

**O que a Fatia 2 entregou (commit `c7db8ab`, 2026-08-12):** `interface/components/construtor-instrumento.tsx` — o
Construtor (overlay de tela cheia) com as 5 seções do mockup; botão **"🌟 Criar instrumento"** na aba Instrumentos
(`instrumentos-cliente.tsx`), e clicar num conector abre o Construtor (não o form genérico). Editor de operação:
método + URL com `[colchete]` (campo automático), campos **IA/Fixo** × destino **query/corpo/url**, comportamento
(informativo, derivado do método), e **testar e detectar** que marca os `campos_resposta`. Backend: **POST
`/instrumentos/{id}/testar-operacao`** (`Conector.testar_operacao` + `_detectar_campos`, roda SEM o filtro para
detectar tudo; reusa a config salva + segredo do cofre, nada gravado) + metadados `descricao`/`categoria` no
`ConfigConector` (o motor ignora). Tipos no `api.ts`. **Deferido com honestidade** (o mockup já adia): auth **Basic/OAuth2**
("em breve"); papel **Segredo** por-campo → o segredo é o token da aba Autenticação; **Publicar/marketplace**;
**escopo org-wide** (grava no time atual → Fatia 2.5). 816 testes verdes; tsc/eslint/build limpos.

---

## 12. Decisões (do maestro)

**✅ Decididas (2026-08-12):**
1. **Nome = "Instrumento"** (sem palavra nova); rótulo interno técnico fica comigo. Entrada: botão **"🌟 Criar
   instrumento"** na aba de Instrumentos do time (§5.7).
2. **Novo tipo** `conector` — não generalizar o `chamar_api_rest` (o REST simples fica intacto).
3. **Escopo = organização** + vínculo ao time (biblioteca de instrumentos da org, §5.7).
4. **Substituir os instrumentos** por este modelo, exceto os nativos de motor — com a **fronteira dos 3 grupos**
   (§5.8): (a) nativos p/ sempre · (b) migram (maioria "só API") · (c) esperam o Nível 3 (precisam de código).
5. **Credenciais moram no instrumento** — a caixa-forte de credenciais nomeadas vira redundante para instrumentos;
   a criptografia (cofre) fica; o pool de chaves de IA da plataforma é outra coisa e segue (§5.9).

**Ainda abertas:**
6. **OAuth 2.0 (login):** entra em qual fatia? (por ora, token do próprio app resolve o caso pessoal).
7. **Marketplace:** quando? É a virada de "ferramenta interna" → "plataforma". Sequência depois da prioridade nº1.
8. **Nível 3 (sandbox):** investir, e quando? (só faz falta para código arbitrário hospedado).

---

## 13. Governança e sequência

- **Aguarda o sinal do maestro.** A execução vem **depois da prioridade nº 1** (Unificação de Estado).
- A **semente barata** — Fatias 0→2 (o tipo conector + o construtor) — ajuda o maestro **já** (dor do Bubble),
  é quase toda **borda** (novo tipo de instrumento + UI + criadora), e **toca pouco o motor**.
- O **marketplace** (Fatia 5) é a decisão estratégica grande — abrir o Batuta a terceiros.
- Núcleo evolui por **decisão dirigida** (`MIGRACAO §6.1`); aqui, quase nada é núcleo.
