# Batuta-MCP — o consultor opera o Batuta pelo próprio claude.ai

> **Status: NO AR.** Fatias 0–3 provadas ao vivo; Fatia 4 (acabamento) aplicada.
> Sucede a prova descartável (`docs/MCP-PROVA.md`), que foi **aposentada**
> (`mcp_prova.py`/`mcp_auth.py` removidos).

## Por que existe

A **IA criadora ≈ 70%** do custo do app (Marco 0). Usar OAuth de assinatura dentro de um
produto server-side é proibido/bloqueado pela Anthropic. O padrão **permitido** é o
inverso: o Batuta é um **servidor MCP** que o **claude.ai do próprio consultor** aciona —
a IA roda na **assinatura dele**, o Batuta só oferece as ferramentas. Como a montagem de
times é trabalho de consultor, mover a criação para o claude.ai deles corta o 70% da
conta de API do Batuta, de forma legítima, cada um na própria assinatura (custo fixo).

**Coexiste** com a IA criadora dentro do app (ela fica como está); é um caminho a mais.

## Arquitetura

- **2º serviço Railway** (mesmo repositório, mesmo banco), app ASGI standalone na **raiz
  de um domínio** — obrigatório porque as URLs `.well-known` do OAuth ficam na raiz. O
  cérebro (`api.batuta.team`) fica **intocado**, com uma única exceção aditiva na borda
  (ver "Agendador" abaixo).
- **Login real por consultor (OAuth 2.1):** o `authorize` NÃO auto-aprova — ele manda o
  navegador do consultor para uma **telinha de login do Batuta** (e-mail/senha), autentica
  no **Supabase** (`grant_type=password`), resolve o `Usuario` e emite um código amarrado à
  identidade (`subject = Usuario.id`). Arquivos: `cerebro/mcp_login.py` (provedor OAuth +
  telinha), `cerebro/mcp_servidor.py` (FastMCP + registro das tools).
- **Tokens sem estado:** código/access/refresh são strings **assinadas** (HMAC-SHA256 com
  `MCP_TOKEN_SECRET`) que carregam o próprio conteúdo — sobrevivem a restart/réplica e
  dispensam tabela de tokens. Só os **clientes OAuth** (registro dinâmico) ficam numa
  tabela portável `mcp_cliente`, criada no boot (`create_all`, fora do alembic).
- **Escopo por papel, ao vivo:** toda ferramenta resolve o `Usuario` pelo `subject` e
  checa o acesso pelos MESMOS guardas das rotas REST (`rotas/_comum` +
  `auth.exigir_papel`) — uma fonte só de autorização. A **revogação é imediata**: desativar
  o consultor ou tirá-lo da org corta o acesso na próxima chamada, mesmo com token válido
  (mesma filosofia do `auth.py`). Arquivo: `cerebro/mcp_escopo.py`.
- **Matriz de papéis:** observador lê; **operador** cria/edita; **admin** cria
  organização/time, duplica e exclui.

## As ferramentas (47)

- **Leitura/diagnóstico:** `listar_organizacoes`, `listar_times`, `descrever_time`,
  `listar_agentes`, `ver_agente`, `ver_memoria_agente`, `listar_instrumentos`/
  `ver_instrumento` (o que é cada id do cinto: nome, tipo, config pública, segredos que
  faltam — nunca o valor de um segredo), `listar_automacoes`, `ver_automacao`,
  `listar_execucoes`, `diagnosticar_execucao` (avisos + ação sugerida),
  `listar_conversas`, `ler_conversa`, `ver_uso`, `listar_tipos_instrumento`,
  `consultar_conhecimento` (a Central).
- **Criação núcleo:** `criar_time`/`editar_time`, `criar_agente`/`editar_agente`/
  `remover_agente`, `configurar_instrumento`/`editar_instrumento`, `montar_conector`/
  `testar_operacao_conector`, `encaixar_instrumento`/`desencaixar_instrumento`,
  `criar_automacao`/`renomear_automacao`/`montar_cadeia`/`definir_gatilho`/
  `ativar_automacao`/`desativar_automacao`. Reusa a porta validada `criacao/servicos.py`.
- **Credenciais/chaves (esqueleto — a IA NUNCA recebe segredo):** `listar_tipos_credencial`,
  `listar_credenciais` (mascarado), `ver_chaves_de_ia` (quais provedores têm chave, por
  existência — não decifra), `criar_credencial` (esqueleto), `remover_credencial`.
- **Config/referência/exclusão/duplicação/org:** `configurar_memoria_agente`,
  `apontar_credencial` (instrumento→credencial), `duplicar_time`, `excluir_time`/
  `excluir_automacao`/`excluir_instrumento`, `criar_organizacao`/`excluir_organizacao`
  (esta só apaga organização **vazia** — nunca em cascata).

> **Nomes que mudaram (2026-08-26):** `ativar_time`/`desativar_time` viraram
> `ativar_automacao`/`desativar_automacao` — recebiam `automacao_id` e operavam sobre uma
> automação, e o nome antigo convidava ao acidente de achar que desligava o time inteiro.
> Depois de qualquer atualização, **reconecte o conector** no claude.ai (remover e
> adicionar): ele guarda a lista de ferramentas, e sem isso nomes antigos continuam
> visíveis e as novas não aparecem.

Arquivos: `cerebro/mcp_ferramentas.py` (leitura), `cerebro/mcp_ferramentas_escrita.py`
(escrita). Cada uma abre a própria sessão, resolve a identidade, checa o acesso e traduz
erros de domínio/acesso em texto humano (nunca stack trace — §12-A).

## Segurança

- **Login real** por consultor; fim do auto-aprovado.
- **Escopo por papel**, checado ao vivo a cada chamada (revogação imediata).
- **A IA nunca pluga segredo:** credenciais e conectores são criados como esqueleto; o
  segredo o consultor cola no **cofre do Batuta pela tela**. Nada de senha/chave passa pelo
  claude.ai. (Decisão do maestro, 2026-08-21.)
- **Least-privilege:** o 2º serviço **não** recebe a chave-mestra do cofre —
  `ver_chaves_de_ia` confere existência sem decifrar. **Isso tem consequência prática:**
  nenhum caminho do MCP pode depender de decifrar. Foi assim que a criação de instrumento
  quebrou por semanas (o cálculo de segredos pendentes decifrava as chaves do pool só para
  ler o NOME do serviço) — hoje `chaves.servicos_com_chave` responde por existência.
- **A parede de aprovação** continua valendo: `ativar_automacao` recusa automação com ação
  irreversível sem portão humano.
- **Ações irreversíveis** (`excluir_*`) têm docstring que orienta o Claude a confirmar
  antes.
- **Auditoria:** as escritas passam `usuario=` real; os eventos levam `origem="mcp"`.

## Agendador (a única mudança aditiva no cérebro)

O agendador é um APScheduler **em memória** dentro do cérebro; o MCP roda em **outro
processo**. Para que uma automação de gatilho `agendamento` criada/ativada pelo MCP entre
no relógio, o cérebro ganhou um **reconcílio periódico** (`agendador.reconciliar()` + job
de 60s): re-sincroniza do banco e remove jobs órfãos — qualquer mudança externa entra em
até ~1 min. Aditivo, na borda; o núcleo de orquestração segue intocado.

## Deploy (2º serviço no Railway)

- **Root Directory:** `cerebro`. **Start Command:** `uv run python mcp_servidor.py`.
- **Variáveis:** `DATABASE_URL` (= cérebro), `SUPABASE_URL`, `SUPABASE_ANON_KEY` (login por
  senha), `MCP_TOKEN_SECRET` (segredo forte fixo — sem ele os tokens não sobrevivem a
  restart), `MCP_PUBLIC_URL` (a URL pública do serviço). **Não** precisa da chave-mestra do
  cofre.
- **Conectar no claude.ai:** Configurações → Conectores → Adicionar conector personalizado
  → `https://<dominio>/mcp` (com `/mcp`) → **Vincular** → telinha de login do Batuta.

## Verificação

- Suíte focada offline `cerebro/testes/test_mcp_login.py` (cripto dos tokens, fluxo
  code→access→refresh carregando o `subject`, DCR persistido, Supabase mockado, portões de
  identidade das ferramentas).
- **`cerebro/testes/test_mcp_escrita_real.py` — o caminho FELIZ, com banco.** Existe porque
  a suíte antiga era toda "offline" (só provava a barreira de acesso) e por isso três
  ferramentas foram para produção quebradas. Ele cria instrumento, conector, credencial e
  agente de verdade, e reproduz a condição real do serviço MCP: organização **com** chave
  no cofre e chave-mestra **ausente** — a combinação em que o bug aparecia (o teste passava
  antes porque a fixture esvazia o cofre, e sem chave nada era decifrado).
- Por fora, com um cliente HTTP: metadados AS/RS 200 → `/mcp` sem token 401 → raiz 404.
- Ao vivo: o consultor conecta, loga, e as ferramentas escopam certo (Fatias 0–3 provadas
  ao vivo em 2026-08-21).

## O que ficou de fora (deferido, honesto)

- **Gestão de membros** (convites): mandam e-mail (ação para fora) e exigiriam a
  `SERVICE_ROLE_KEY` no serviço — fora de escopo por ora.
- **Duplicação de automação:** a lógica de clone é inline na rota; replicá-la arriscaria
  divergência. `duplicar_time` (função compartilhada) cobre o caso comum.
- **`icone` de instrumento:** cosmético.
- **Extração completa das rotas de credenciais/chaves para serviço:** o MCP reusa os
  primitivos já compartilhados sem refatorar rotas sensíveis de produção; o cofre (segredo)
  já é fonte única e o MCP nunca o toca.

## Relacionado

- `docs/MCP-PROVA.md` — a prova de conceito que originou isto (aposentada).
- `docs/ECONOMIA-TOKENS-IA-CRIADORA.md` — o 70% que esta frente ataca por outro caminho.
- `cerebro/central/operacao/operar-pelo-claude-mcp.md` — o mesmo, na Central (para o
  consultor e para a IA).
