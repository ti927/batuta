# Prova de conceito — Batuta como servidor MCP (criar/ajustar agentes pelo claude.ai)

> **Status: PROVA validada AO VIVO em 2026-08-20.** Um consultor, conversando no
> **próprio claude.ai (assinatura dele)**, criou um agente dentro do Batuta via um
> **connector MCP**. Isto é uma prova descartável — **não** é produção. A versão de
> verdade (login real + escopo por consultor + toolset completo) é trabalho à parte.

## Por que isto existe

O fio condutor é **custo de IA**: a **IA criadora ≈ 70%** do custo do app (Marco 0).
A ideia de "usar o login do Claude" para baratear esbarra numa regra da Anthropic:
**usar OAuth de assinatura (Free/Pro/Max) dentro de um produto que roda IA no
servidor para clientes é proibido e bloqueado tecnicamente desde jan/2026** — o
caminho de produto é **API key**.

**MAS** o padrão **permitido** (o mesmo do buildprint.ai) é o inverso: o Batuta ser
um **MCP** (Model Context Protocol) que o **claude.ai do próprio usuário aciona**. A
IA roda na **assinatura do usuário**, dentro do app nativo da Anthropic; o Batuta só
**oferece as ferramentas**. Como a **criação** de times é feita pelos **consultores**
(técnicos — PRODUTO §4), mover a criação para o claude.ai do consultor tira o 70% da
conta de API do Batuta, **de forma legítima**, e cada consultor gasta na **própria
assinatura** (custo fixo).

Analogia (a mesma "cérebro × instrumento" do produto): um MCP é um **instrumento**
que o Claude do usuário chama; o Batuta, no runtime que serve o cliente, é o
**cérebro** (e esse continua em API key). Aqui é o Batuta bancando o papel de
instrumento para o Claude do consultor.

## O que a prova faz (escopo mínimo)

Um servidor MCP remoto (Streamable HTTP) com **4 ferramentas**, todas escopadas a
**um único time de teste fixo** (`MCP_PROVA_TIME_ID`):

- `descrever_time` — nome/id/contagem de agentes do time de teste (leitura).
- `listar_agentes` — os agentes do time (leitura).
- `criar_agente(nome, instrucoes, papel)` — cria agente (escrita).
- `ajustar_agente(agente_id, nome, instrucoes)` — renomeia/reescreve (escrita).

As ferramentas **reusam a camada de serviço** validada do Batuta
(`cerebro/criacao/servicos.py` — `adicionar_agente`/`editar_agente`), a MESMA porta
por onde a IA criadora e as rotas REST escrevem no time real. **Não** reusam os tools
da criadora (que são acoplados a um turno/conversa).

## Arquitetura (e as duas descobertas que a moldaram)

**1. O claude.ai EXIGE OAuth no connector personalizado.** Não há modo "sem senha"
no fluxo de "Vincular" (ele tenta registrar um login e recusa se não achar). Então o
servidor implementa um **OAuth 2.1 mínimo AUTO-APROVADO** (`cerebro/mcp_auth.py`):
registro dinâmico de cliente (DCR) + `/authorize` que **auto-aprova** (sem tela de
senha, sem usuário real) + `/token` + verificação do token. As **engrenagens** (rotas
e metadados) vêm prontas do SDK `mcp`; só a lógica do provedor é nossa. A postura de
segurança é **igual à do "sem senha"** — só embrulhada no ritual que o claude.ai quer.

**2. O MCP roda como SERVIÇO PRÓPRIO na RAIZ de um domínio, não montado no cérebro.**
As URLs de descoberta do OAuth (`.well-known/...`) que o SDK gera ficam na **raiz do
domínio**; montar sob um subcaminho (ex.: `api.batuta.team/mcp-prova`) faria o
claude.ai procurar os metadados na raiz e **quebrar a descoberta**. Por isso o cérebro
(`api.batuta.team`) fica **intocado** e o MCP sobe como um **2º serviço Railway** a
partir do mesmo repositório, apontando para o **mesmo banco**. O Railway dá um domínio
próprio ao serviço, então nem precisa de subdomínio novo.

### Arquivos
- `cerebro/mcp_prova.py` — o `FastMCP` (Streamable HTTP em `/mcp`, `stateless_http`),
  as 4 ferramentas, o `AuthSettings` (issuer/resource derivados de
  `RAILWAY_PUBLIC_DOMAIN` ou `MCP_PROVA_PUBLIC_URL`), e o `asgi_app` + um bloco
  `__main__` que roda o uvicorn lendo `PORT` do ambiente.
- `cerebro/mcp_auth.py` — o provedor OAuth 2.1 auto-aprovado (in-memory).
- O cérebro (`cerebro/main.py`) **não** importa nem monta nada disto (voltou intacto).

## Como subir o 2º serviço no Railway

1. **New → Deploy from GitHub repo** → o mesmo repositório do Batuta.
2. **Settings:**
   - **Root Directory:** `cerebro` (via o link "Add Root Directory" no bloco Source).
   - **Custom Start Command:** `uv run python mcp_prova.py`
     (⚠️ *não* use `uvicorn ... --port $PORT` direto: o builder não expande `$PORT` e o
     uvicorn recusa; e `uvicorn` cru não está no PATH — por isso `uv run python` +
     o bloco `__main__` que lê `PORT` do ambiente.)
   - **Networking → Generate Domain** (cria a URL pública).
3. **Variables:**
   - `DATABASE_URL` = o **mesmo valor** do serviço `cerebro` (o banco de produção).
   - `MCP_PROVA_TIME_ID` = o id de um "Time de Teste MCP" (crie o time no Batuta, copie
     o id da URL `/times/<id>`).
   - `MCP_PROVA_PUBLIC_URL` = a URL pública do serviço (ex.:
     `https://batuta-production.up.railway.app`) — recomendado para fixar o issuer do
     OAuth (senão o código tenta pelo `RAILWAY_PUBLIC_DOMAIN`).
4. **Deploy.** No Deploy Log, sucesso = `Uvicorn running on http://0.0.0.0:<PORT>` +
   `StreamableHTTP session manager started`.

## Conectar no claude.ai (Pro/Max)

1. **Customize → Connectors → + → Add custom connector** → cole a URL do MCP:
   `https://<seu-dominio>/mcp` → **Add**.
2. Clique em **Vincular** — o login OAuth roda e **auto-aprova** (sem pedir senha).
3. **Ative o connector na conversa** (o "+"/menu de ferramentas do chat).
4. Peça: *"descreva o time de teste"*, depois *"crie um agente chamado X que faz Y"*.

## Verificação de ponta a ponta (por fora, sem o claude.ai)

O fluxo inteiro pode ser exercido com um cliente HTTP contra a URL do serviço:
`GET /.well-known/oauth-authorization-server` (200) → `GET
/.well-known/oauth-protected-resource/mcp` (200) → `POST /mcp` sem token (**401**) →
`POST /register` (201, DCR) → `GET /authorize` (**302** com `code`) → `POST /token`
(200, access_token) → `POST /mcp` `initialize`/`tools/list`/`tools/call` com `Bearer`
(200). Provado em produção em 2026-08-20 (inclusive `tools/call descrever_time` lendo
o time de teste real do banco).

## Segurança (leia antes de deixar ligado)

- O login é **auto-aprovado**: qualquer um que rode o fluxo OAuth recebe um token com
  acesso às ferramentas. O raio de dano é **um time de teste descartável**
  (`MCP_PROVA_TIME_ID`). **Nunca** aponte para um time real neste estado.
- Quando não estiver testando, **remova o connector** no claude.ai e/ou **pause o
  serviço** no Railway.
- Os tokens/códigos são **in-memory** (somem no restart do processo).

## O que a prova NÃO faz (deferido — decisões de produto)

1. **Substituir × coexistir** — a criação passa a ser feita pelo claude.ai (corta o
   70%), ou o claude.ai vira um caminho a mais ao lado da criadora atual?
2. **Login REAL** — trocar o auto-aprovado por login do Batuta (Supabase) + **escopo
   por consultor/organização** (o `authorize` autentica o consultor e amarra o token à
   org dele; as ferramentas param de usar um time fixo e passam a respeitar o escopo).
3. **Toolset completo** de criação (hoje são 4 ferramentas).
4. Nada disto muda o **runtime que serve o cliente** (continua API key; é <3% do custo).

## Relacionado
- `docs/ECONOMIA-TOKENS-IA-CRIADORA.md` — o 70% que esta prova ataca por outro caminho.
- `docs/UNIFICACAO-ESTADO.md` — o programa de custo/estado (via memória entre turnos).
- `PRODUTO.md §3/§4` — por que a criação é do consultor (técnico), não do cliente final.
