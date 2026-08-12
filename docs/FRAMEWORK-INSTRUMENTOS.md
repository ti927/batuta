# Framework de Instrumentos — Plano Completo (Construtor + Central + IA criadora + Marketplace)

> **Status:** 📋 **PLANO — não iniciar sem o sinal do maestro.** Mockup da **Fase 1 validado** (2026-08-12,
> artefato `435b0bdf`). Este é o plano da **Fase 2**. **Sequência:** vem **depois da prioridade nº 1**
> (Unificação de Estado, `docs/UNIFICACAO-ESTADO.md`); a *semente barata* (o tipo "conector" + o construtor)
> pode começar antes do marketplace, pois ajuda o maestro **já** e toca pouco o motor. Governança:
> `MIGRACAO §6.1` (evolução dirigida) — mas quase tudo aqui é **borda** (um novo tipo de instrumento + UI +
> ferramentas da criadora), não o núcleo.

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
- **OAuth 2.0 (login do usuário):** mais complexo (fluxo de consentimento + refresh). **Fase posterior.** Por ora,
  o usuário cola o **token do próprio app** (o "bypass" pessoal do Instagram/Google — sem App Review).
- Renovação de token: o Batuta avisa quando estiver perto de expirar (o mesmo cuidado que o Instagram já tem).

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

---

## 6. A IA criadora monta o instrumento

Hoje a criadora monta agentes/automações pela **porta única** dos serviços de domínio. Adicionar "montar um
conector" é a **mesma forma** — e é **seguro**, porque a criadora só preenche **dado declarativo** (não código).

- **Novas ferramentas da criadora:** `criar_conector`, `adicionar_operacao`, `definir_auth` (a IA preenche a
  `Config` do conector a partir da conversa).
- **Fluxo:** *"quero um instrumento que publica no meu Instagram"* → a criadora **consulta a Central** (§7) para
  saber como montar, propõe as operações (Publicar foto / Ler comentários), monta o conector.
- **Regra de segurança (já existe):** a criadora **NÃO pluga o segredo** — deixa "pendente"; **o humano cola o
  token** no cofre. Ver [[project-ia-criadora-credenciais-nomeadas]] (`tipos_credencial_aceitos` +
  `credencial_id`, referência, nunca toca o segredo).
- **Parede:** um conector com operação irreversível só ATIVA com portão antes — a criadora já respeita a parede.

---

## 7. Central de Conhecimento

Novos capítulos (auto-descobertos por `rglob`, `cerebro/central/`):
- **`instrumentos/construir-instrumento.md`** — o que é um instrumento personalizado, o construtor, os papéis de
  campo (IA/Fixo/Segredo), auth por menu, `[colchete]`, testar-e-detectar, a parede por operação.
- **`instrumentos/instrumento-pessoal-vs-saas.md`** — honesto: usar **o próprio app** (Meta/Google) para a
  **própria conta** evita App Review; o preço é você fazer a configuração e cuidar do token. Quando vale o SaaS.

Atualizar: `instrumentos/chamar-rest.md` (aponta para o conector multi-operação), `INDICE.md`. **A criadora
consulta esses capítulos** para montar conectores (a Central é a base de conhecimento dela).

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
| **0. Forma** | decisões (§12) + spike do executor genérico | não | baixo |
| **1. Motor do conector** | novo tipo `conector` (`expandir_ferramentas` + executor), **sem UI**, provado por teste; reusa REST/cofre/parede/`campos_resposta` | não | baixo |
| **2. Construtor** | as telas do mockup (Identidade/Auth/Operações/Testar) | **sim** (propor antes) | médio |
| **3. Importar OpenAPI** | colar spec → gera operações | sim | médio |
| **4. Criadora + Central** | ferramentas da criadora p/ montar conector + capítulos novos | sim | médio |
| **5. Marketplace básico** | só-org → compartilhado → público + revisão | sim | alto |
| **6+. Nível 3 (sandbox)** | código hospedado | sim | máximo |

Fatia 1 já entrega o **valor pro maestro** (conector multi-operação p/ o Bubble) sem marketplace. Cada fatia:
plano + verificação aprovados **antes** do código; deploy e observação antes da seguinte.

---

## 12. Decisões abertas (do maestro)

1. **Nome:** "Conector"? "Construtor de Instrumento"? "Instrumento personalizado"? (o construtor é a tela; o
   tipo no motor precisa de um nome).
2. **Novo tipo × generalizar o REST atual.** *Recomendação:* **novo tipo** `conector` — deixa o `chamar_api_rest`
   simples intacto (retrocompat) e o conector nasce multi-operação.
3. **OAuth 2.0 (login):** entra em qual fatia? (por ora, token do próprio app resolve o caso pessoal).
4. **Marketplace:** quando? É a virada de "ferramenta interna" → "plataforma". Sequência depois da prioridade nº1.
5. **Nível 3 (sandbox):** investir, e quando? (só faz falta para código arbitrário hospedado).

---

## 13. Governança e sequência

- **Aguarda o sinal do maestro.** A execução vem **depois da prioridade nº 1** (Unificação de Estado).
- A **semente barata** — Fatias 0→2 (o tipo conector + o construtor) — ajuda o maestro **já** (dor do Bubble),
  é quase toda **borda** (novo tipo de instrumento + UI + criadora), e **toca pouco o motor**.
- O **marketplace** (Fatia 5) é a decisão estratégica grande — abrir o Batuta a terceiros.
- Núcleo evolui por **decisão dirigida** (`MIGRACAO §6.1`); aqui, quase nada é núcleo.
