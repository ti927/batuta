# Mensageria de mão dupla — plano aprovado (Telegram Fase 1, WhatsApp Fase 2)

> **Status (2026-06-13): PLANEJADO e APROVADO pelo maestro. NÃO iniciado.**
> Aguarda só o sinal do maestro para executar. Este documento é a cópia durável do plano (o
> arquivo de plano da sessão é efêmero). Ordem na fila de execução: ver `BUILD-PLAN.md`.
> Lição que originou este desenho: ver a memória `feedback_canais-sao-instrumentos` (a 1ª
> tentativa, com "ambiente de Canais" no nível da organização, foi **revertida**).

## Contexto — por que esta mudança
O maestro quer que os agentes do Batuta **conversem de verdade** com pessoas — equipe interna e
clientes externos — por mensageria. Hoje o Batuta só sabe *enviar* (instrumentos de mão única) e
*pausar para um humano na tela*. Falta a **mão dupla**: a pessoa manda mensagem, o agente responde,
a pessoa replica, o agente reage — em laço.

Uma 1ª tentativa (revertida) errou ao criar um "ambiente de Canais" no nível da organização.
**A correção:** o canal é um **INSTRUMENTO** no cinto do agente (`enviar_telegram` / `enviar_whatsapp`);
cada instância = um bot/número = a identidade do canal. Em cima disso entra uma **camada fina de
conversação** que coordena os turnos.

**Faseamento (decisão do maestro):** **Fase 1 = Telegram com TODAS as soluções de atendente de IA**
(profissional, mitigando o máximo de problemas). **Fase 2 = só incorporar WhatsApp** (mesmo desenho +
provedor + janela de 24h/templates). Este documento detalha a Fase 1.

**Resultado pretendido:** um atendente Telegram de mão dupla, profissional, com inbox, transferência
para humano, transcrição de áudio, timeout, tetos de gasto e guarda-corpos — sem tocar o núcleo de
orquestração.

## Decisões já batidas com o maestro
- **Formato:** suportar **os dois** — começar pelo **conversacional** (1 agente, papo natural, lembra a
  conversa) e deixar o **fluxo com etapas** (cadeia multi-agente com aprovação) encaixado na mesma
  fundação.
- **Inatividade:** **cutucar uma vez** ("ainda está aí?") e, persistindo o silêncio, **encerrar** com
  despedida.
- **Teto de gasto / limite:** ao estourar, **passar a conversa para um humano** (cai na inbox; o bot cala).

## Decisões técnicas fechadas (não exigem o maestro)
- **Como a conversa roda:** modo **conversacional = uma execução por turno** (1 agente; o histórico da
  conversa é carregado no preâmbulo a cada mensagem). Evita o teto `MAX_PASSOS=25` do núcleo e casa com
  "vinculo o instrumento ao agente". Modo **fluxo = cadeia com pausa/retoma** (reusa `responder`/
  `_escolher_saida`).
- **Saída ao contato:** a borda **entrega automaticamente** a resposta do agente ao contato ao fim do
  turno (mais confiável que depender da IA "lembrar" de acionar o instrumento). O instrumento
  `enviar_telegram` fica disponível para mensagens proativas e para o operador.
- **Ponto de partida:** o instrumento de canal aponta para um **destino de atendimento** (um agente, no
  conversacional; uma automação, no fluxo) via gatilho novo `"mensagem_recebida"`.
- **Quem inicia:** **inbound-first** (a pessoa fala primeiro) — é o que Telegram/WhatsApp permitem sem
  fricção; outbound proativo fica como extensão.
- **Segurança e debounce entram já no Milestone 1** (não são "refinamento opcional"): secret token no
  webhook e um debounce leve por contato.

## Princípio estrutural — núcleo congelado, tudo na borda
**NUNCA tocados:** `cerebro/orquestracao/cadeia.py`, `cerebro/orquestracao/agente.py`. Reusados por
chamada: `executar_cadeia(..., no_inicial=, ordem_inicial=, registrar_passo=, cancelado=)`,
`_escolher_saida`, `_DESTINOS_FIM`, contrato de pausa `pausa_humano`, `executar_agente`.
**Reuso direto:** `orquestracao/disparo.py` (`criar_execucao`, `_aplicar_resultado`, `rodar_execucao`),
`fila.py` (`enfileirar`), `chaves.py` (`resolver_chaves_por_time`), `orquestracao/llm.py` (`usar_chaves`),
encaixe de `instrumentos/base.py` + cofre `segredos_instrumento.py`, `precos.resumir_uso`.
**Extensão (borda):** novos arquivos em `cerebro/instrumentos/` e num pacote novo `cerebro/mensageria/`,
novos modelos/migration, novos endpoints, **um** job no agendador, telas novas na interface.

---

## MILESTONE 1 — Atendente Telegram de mão dupla, ponta a ponta

### Fase A — Instrumento `enviar_telegram` (borda pura)
- **Novo:** `cerebro/instrumentos/enviar_telegram.py`, espelhando `cerebro/instrumentos/webhook_saida.py`.
  `ConfigTelegram(token_bot)` (segredo), `ArgsTelegram(destinatario, mensagem)`,
  `EnviarTelegram(TipoInstrumento)`: `tipo="enviar_telegram"`, `campos_secretos=("token_bot",)`,
  `acao_irreversivel=True`, `executar()` faz `httpx.post` em `sendMessage` (401/403→não retentável,
  429/5xx→retentável). `registrar(EnviarTelegram())`.
- **Editar:** `cerebro/instrumentos/__init__.py` (+`from instrumentos import enviar_telegram`).
- **Verificar:** `GET /instrumentos/tipos` mostra o tipo; `POST /instrumentos/{id}/acionar` com
  `{argumentos:{destinatario, mensagem}}` entrega no Telegram (rota existente já decifra o segredo).

### Fase B — Modelos `Conversa` + `MensagemConversa` + migration (aditiva)
- **Editar (aditivo):** `cerebro/modelos.py`:
  - `Conversa`: `instrumento_id` (FK = o canal/bot → liga a time/org e às chaves), `canal` (default
    `'telegram'`), `contato_chave` (chat_id, string), `contato_nome`, `estado`
    (`aberta|bot_respondendo|aguardando_resposta|humano_assumiu|fechada`), `destino_tipo`+`destino_id`
    (agente ou automação), `execucao_id` (FK, nullable), `aguardando_ate`, `nudge_enviado` (bool),
    `atribuida_a` (FK usuário), `custo_acumulado_usd`, `turnos`, `ultima_entrada_em`. Índice único parcial
    `(instrumento_id, contato_chave) WHERE estado <> 'fechada'`.
  - `MensagemConversa`: `conversa_id` (FK CASCADE), `papel` (`contato|agente|operador|sistema`),
    `conteudo`, `midia` (JSONB), `entregue` (bool). Índice `(conversa_id, criado_em)`.
- **Novo:** migration Alembic em `cerebro/alembic/versions/` (molde:
  `d4e5f6a7b8c9_instrumento_exige_aprovacao.py`), `down_revision` = head atual. Cria só as 2 tabelas.
  Não toca nenhuma tabela do motor.
- **Verificar:** `alembic upgrade head` e `alembic downgrade -1` limpos (rodar **primeiro em banco
  local**, ver Risco R1).

### Fase C — Miolo de retoma reutilizável (borda)
- **Novo:** `cerebro/mensageria/retoma.py` — `retomar_execucao(sessao, execucao, resposta, *, chaves,
  origens)` com o algoritmo hoje embutido em `cerebro/rotas/automacoes.py::responder` (achar último
  `PassoExecucao`, saídas do nó, `_escolher_saida`, `_entrada_retomada`,
  `executar_cadeia(no_inicial=proximo, ...)`, `_aplicar_resultado`). Mover `_entrada_retomada` para cá.
- **Editar:** `cerebro/rotas/automacoes.py::responder` passa a chamar esse serviço (mantém
  auditoria/portão).
- **Verificar:** o portão de aprovação existente (`POST /execucoes/{id}/responder`) continua idêntico.

### Fase D — Webhook de entrada + roteamento (borda) — o coração da mão dupla
- **Novo:** `cerebro/mensageria/telegram.py` — adaptador da Bot API:
  `extrair_update(corpo)→MensagemEntrante` (chat_id, nome, texto, mídia),
  `configurar_webhook(token, url, secret)`, `enviar(token, chat_id, texto)`.
- **Novo:** `cerebro/mensageria/servico.py` — roteamento `processar_entrada(sessao, instrumento, msg)`:
  1. Acha/cria `Conversa` viva por `(instrumento_id, contato_chave)`; grava `MensagemConversa(contato)`;
     atualiza `contato_nome`.
  2. **Debounce leve** por contato (janela curta via `ultima_entrada_em`) para juntar rajada.
  3. Se `estado=="humano_assumiu"`: só registra (operador responde pela inbox). Retorna.
  4. **Modo conversacional:** monta a entrada com o **histórico** da conversa + preâmbulo de contexto e
     roda 1 turno do agente (`executar_agente`), grava `MensagemConversa(agente)`, **entrega a saída ao
     contato**, marca `aguardando_resposta` + `aguardando_ate`.
     **Modo fluxo:** 1ª msg → `criar_execucao` da automação + `fila.enfileirar`; msgs seguintes com
     execução em `aguardando_humano` → `retoma.retomar_execucao`.
- **Novo:** `cerebro/rotas/mensageria.py` — `POST /mensageria/{instrumento_id}/entrada` (público, molde
  `rotas/webhooks.py`): valida instrumento + **secret token** do header do Telegram, extrai update, chama
  o serviço, responde 200 rápido.
- **Editar:** `cerebro/main.py` (`include_router(mensageria.rotas)`).
- **Verificar:** `POST` com update fake cria Conversa+turno e entrega resposta; 2ª msg continua o papo.

### Fase E — Conectar o canal (setWebhook sob demanda)
- **Novo endpoint:** `POST /mensageria/{instrumento_id}/ativar-canal` em `rotas/mensageria.py` →
  `telegram.configurar_webhook(token, f"{CEREBRO_URL_PUBLICA}/mensageria/{id}/entrada", secret)`. Mantém o
  CRUD de instrumentos genérico **intocado**. Nova env `CEREBRO_URL_PUBLICA`.
- **Verificar:** `getWebhookInfo` mostra a URL; mensagem ao bot chega no endpoint.

### Fase F — Transferência para humano (takeover) + inbox mínima
- **Editar:** `cerebro/rotas/mensageria.py` (endpoints autenticados, escopo via instrumento→time):
  `GET /times/{id}/conversas`, `GET /conversas/{id}`, `POST /conversas/{id}/assumir` (estado=humano_assumiu,
  cancela execução viva, `atribuida_a`), `POST /conversas/{id}/responder-operador` (envia via instrumento,
  grava papel=operador), `POST /conversas/{id}/devolver`, `POST /conversas/{id}/fechar`.
- **Editar:** `cerebro/esquemas.py` (`ConversaLer`, `ConversaComMensagens`, `MensagemConversaLer`,
  `ResponderOperador`).
- **Novo (interface):** telas espelhando `interface/app/execucoes/` (Server Component + ilha cliente +
  `router.refresh()`): `interface/app/times/[id]/conversas/page.tsx` + `conversas-cliente.tsx`, e
  `.../conversas/[conversaId]/` (thread + caixa do operador + botões assumir/devolver/fechar).
  Tipos/chamadas em `interface/lib/api.ts`.
- **Verificar:** msg ao bot aparece na inbox; "assumir" silencia o bot; "responder" entrega no Telegram;
  "devolver" reativa o bot. **← Milestone 1 atingido.**

---

## MILESTONE 2 — Demais soluções (cada uma isolada, na borda)

### Fase G — Segurança e transparência
- **Secret token** do webhook (já no M1) + validação no endpoint.
- **Anti prompt-injection:** preâmbulo que rotula o texto do contato como "usuário externo não confiável"
  em `mensageria/servico.py` (não toca o núcleo).
- **Transparência:** mensagem automática de abertura ("sou um assistente virtual da …").
- **Sandbox:** `POST /mensageria/{id}/entrada-teste` (autenticado) injeta update fake sem cobrar/limitar.

### Fase H — Áudio → texto (Whisper/OpenAI)
- **Novo:** `cerebro/mensageria/transcricao.py` — baixa o áudio (`getFile`) e transcreve via OpenAI,
  **reusando** a chave OpenAI do cofre (`chaves.resolver_chaves_por_time(..., provedor="openai")`).
- **Editar:** `telegram.py::extrair_update` detecta `voice/audio`; `servico.py` transcreve antes de montar
  a entrada e grava a transcrição na thread. Para a cadeia, vira texto normal.

### Fase I — Limites: debounce, rate-limit, teto de gasto, máx. turnos
- Em `mensageria/servico.py`, antes de cada turno: incrementa `turnos`, soma custo do último passo
  (`precos.resumir_uso`) em `custo_acumulado_usd`. **Estourou teto/turnos → passa para humano** (decisão
  do maestro): `estado="humano_assumiu"` + aviso na inbox. Rate-limit/debounce por `(instrumento, contato)`.

### Fase J — Timeout de inatividade + nudge (job no agendador)
- **Convenção na cadeia/destino:** `timeout_s` + rota `"sem_resposta"` (lida pela borda; JSONB livre,
  núcleo não muda).
- Ao pausar/aguardar: grava `Conversa.aguardando_ate`.
- **Novo:** `cerebro/mensageria/sweeper.py` — `varrer(sessao)` pega conversas vencidas: 1º vencimento →
  **nudge** "ainda está aí?" (`nudge_enviado=true`, novo prazo curto); 2º → **encerra** com despedida
  (decisão do maestro), roteando pela rota `"sem_resposta"` (sem gastar LLM).
- **Editar (aditivo):** `cerebro/agendador.py` —
  `add_job(sweeper, IntervalTrigger(30s), id="mensageria_sweeper")`. Roda em 1 réplica (já é o caso).

### Fase K — Horário comercial, status de entrega, métricas
- **Horário comercial:** checagem em `servico.py` (config no instrumento; fuso `America/Sao_Paulo`); fora
  do horário, auto-resposta sem disparar IA.
- **Status de entrega:** `MensagemConversa.entregue` pelo retorno do `sendMessage`.
- **Métricas:** `GET /times/{id}/conversas/metricas` (volume, tempo de resposta, % handoff, custo via
  `precos`) + tela usando `interface/lib/uso.ts`.

---

## FASE 2 — WhatsApp (depois da Fase 1 validada ao vivo)
Mesmo desenho de instrumento + camada de conversa; muda só o adaptador de canal e o que é específico do
WhatsApp. Esboço (detalhar quando a fase rodar):
- **Instrumento `enviar_whatsapp`** no mesmo molde; novo adaptador `cerebro/mensageria/whatsapp.py`.
- **Provedor:** decidir entre **Cloud API oficial** (robusto, exige conta Meta Business + número
  registrado + mensagens-modelo aprovadas; sem QR) e **Evolution** (QR sem fricção, não-oficial, risco de
  ban — número dedicado por instância). Sub-decisão a bater na hora.
- **Janela de 24h + templates (HSM):** dentro de 24h, resposta livre; fora, só template aprovado para
  reabrir. A camada de Conversa guarda o "último inbound" para saber se a janela está aberta.
- **Mídia/áudio:** reusa a transcrição da Fase 1 (Whisper).
- **Tudo o mais** (inbox, takeover, timeout, tetos, métricas) **já existe da Fase 1** — o WhatsApp só
  pluga como mais um canal.

---

## Migrations (todas ADITIVAS — não tocam o motor)
1. `mensageria_fase1`: cria `conversas` e `mensagens_conversa` + índices (incl. único parcial de conversa
   viva). `down_revision` = head atual. Nenhuma migration toca `automacoes`/`execucoes`/`passos_execucao`/
   `instrumentos`.

## Mapa solução → onde encaixa
Enviar=A · Receber/rotear=D · Conversa 1ª classe=B · Multi-turno=C/D · Handoff+inbox=F · Áudio→texto=H ·
Debounce/rate-limit/teto/máx-turnos=I · Anti-injeção/transparência/sandbox=G · Timeout+nudge=J ·
Horário/entrega/métricas=K · Rótulo de contato=B/D (nome vem no webhook).

## Riscos
- **R1 — DB compartilhado é produção.** Rodar migrations primeiro em local/staging; usar **bot de teste**
  até validar (o `setWebhook` redireciona um bot real).
- **R2 — Endpoint público.** Exige o secret token desde o M1 (senão injeção de mensagens = gasto de
  tokens).
- **R3 — `MAX_PASSOS=25`** limita o modo fluxo em conversas longas; o modo conversacional (execução por
  turno) não sofre disso.
- **R4 — Ordem/reentrância de mensagens** em rajada → debounce desde o M1.
- **R5 — Custo de Whisper** sem teto → coberto na Fase I.
- **R6 — `_escolher_saida` gasta 1 chamada de LLM por retoma no modo fluxo** → roteamento determinístico
  nos casos triviais.

## Pré-requisitos do maestro (contas/segredos — só o que o Claude não faz)
- **Bot de teste no BotFather** + token. (O token `8875168210:...` vazou no chat antes — **regenerar**
  antes de uso real e guardar só pelo cofre. Há também `@TesteBatutaBot`, token igualmente exposto →
  regenerar.)
- **Chave OpenAI** ativa no cofre do time (para a transcrição de áudio, Fase H).
- (Fase 2) decisão do provedor de WhatsApp + suas credenciais.

## Verificação ponta a ponta (fim da Fase 1)
1. Criar instrumento `enviar_telegram` (bot de teste) e conectar o canal → `getWebhookInfo` correto.
2. Mandar mensagem ao bot → resposta do agente chega; conversa aparece na inbox.
3. Mandar **áudio** → transcrito e respondido.
4. Mandar rajada de 3 mensagens → tratadas como um turno (debounce).
5. "Assumir" na inbox → bot cala; operador responde; "devolver" → bot volta.
6. Deixar a conversa parada → nudge "ainda está aí?" e, persistindo, encerramento.
7. Estourar o teto de gasto → conversa passa para humano automaticamente.
8. Suíte do cérebro verde (`uv run --directory cerebro pytest`), incluindo testes novos de mensageria.
9. Núcleo `cadeia.py`/`agente.py` sem diff (`git diff` vazio nesses arquivos).

---

# PRÓXIMA FASE (APROVADA 2026-06-14, aguardando execução): Contabilização de uso de IA por CATEGORIA

> **Status: PLANEJADA e APROVADA. NÃO iniciada.** É a próxima da fila no `BUILD-PLAN.md`.

## Contexto
A Fase 1 está no ar. Ao testar o áudio, o maestro pediu: (1) confirmar que a chave OpenAI da **consultoria**
(chave-mãe) é usada quando a organização não tem chave própria — **já funciona** (`chaves.resolver_chaves_por_time`
cai `org → consultoria` para qualquer provedor; só falta confirmar com teste); (2) que **todo consumo seja
contabilizado SEPARADO POR CATEGORIA de uso** (IA de conversa, execução de agentes, atendimento/mensageria,
transcrição…), para ficar claro em que função a chave-mãe foi gasta.

**Furos atuais (mapeados no código):** o uso já é carimbado com **origem** (organizacao/consultoria/legado)
na execução, no roteamento e na IA de conversa; mas **não existe a dimensão "categoria"** em lugar nenhum, e
a **mensageria** (turno do agente) + o **Whisper** não entram nos painéis de uso.

## Categorias (rótulos ao usuário)
`execucao` (Execução de agentes — inclui o roteamento) · `conversa` (IA de criação/companheira) ·
`mensageria` (Atendimento) · `transcricao` (Transcrição de áudio). Futuro: `instrumento`.

## Desenho (tudo na borda; núcleo congelado)
- **Carimbar `categoria` na BORDA** (carimbar na fonte tocaria `agente.py`/`cadeia.py`):
  - `disparo._fazer_registrador(..., categoria="execucao")` grava a categoria em cada entrada de uso (funde
    o roteamento dentro de "execução" — granularidade fina exigiria tocar o núcleo).
  - `criacao/loop.py::responder_turno` → `uso["categoria"]="conversa"`.
  - `mensageria/servico.py` → entradas do turno: agente `categoria="mensageria"`, Whisper `categoria="transcricao"`.
- **Fechar os furos da mensageria:** nova coluna `uso` (JSONB) em `mensagens_conversa` (migration aditiva,
  `down_revision`=`f7b8c9d0e1f2`); `processar_turno` para de descartar `origens` e carimba `origem`
  (agente: `origens[provedor_do_modelo_seguro(modelo)]`; Whisper: `origens["openai"]`).
- **Whisper é por MINUTO** (whisper-1 = US$0,006/min): capturar `voice.duration` (segundos) em
  `extrair_update`; entrada `{modelo:"whisper-1", segundos:N, custo_usd:<precalc>, origem, categoria}`.
- **`precos`:** honrar `custo_usd` pré-calculado quando presente; `entradas_das_mensagens`; **`por_categoria`**
  em `resumir_uso_de_entradas`; `resumir_uso(passos, conversas, mensagens)`.
- **Endpoints:** `/uso/resumo` inclui a mensageria (join `Conversa→Instrumento.time_id→Time.org→Membro`) e
  expõe `por_categoria`; `/uso/consultoria` soma a mensageria e mostra `por_categoria` por organização.
- **Interface:** `lib/uso.ts` (`ROTULO_CATEGORIA`/`rotuloCategoria`), `lib/api.ts` (`por_categoria` nos
  tipos), `app/uso-consultoria/page.tsx` (quebra por categoria), opcional em `app/execucoes`.
- **Teto da conversa** passa a incluir o custo da transcrição.

## Fora de escopo (honesto)
`gerar_imagem` (único instrumento com IA paga) usa **chave própria do instrumento** (não a da consultoria) e
contabilizá-lo exigiria **tocar o núcleo congelado** (`agente.py`). Fica para uma fase à parte, por um
caminho que não toque o núcleo (ex.: o instrumento registra o próprio custo num ledger).

## Verificação
Testes: fallback consultoria (origem `consultoria` para openai); carimbo origem+categoria na mensageria +
Whisper no teto; categoria na execução e na conversa; `resumir_uso` com `por_categoria` (incl. Whisper);
`/uso/resumo` e `/uso/consultoria` incluindo a mensageria. Suíte verde; núcleo sem diff; tsc/eslint limpos.
