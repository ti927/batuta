# Batuta — Canal de mensageria plugável (Telegram primeiro)

**Documento de decisão e plano.** Define como o Batuta deixa de amarrar o Líder a um WhatsApp fixo e passa a tratar **canal de mensageria como peça plugável**, à semelhança dos instrumentos. O primeiro canal implementado é o Telegram, completo (saída e entrada); a fundação nasce preparada para o WhatsApp encaixar depois sem retrabalho.

> Nota ao Claude Code: este documento é arquitetural. Nomes exatos de tabelas, endpoints e módulos devem ser confirmados contra o código real antes de implementar — adote os nomes que mantêm consistência com o que já existe (execuções, espera-por-humano, fila, cofre). Onde este documento sugere um nome, é sugestão, não imposição.

---

## 1. O problema que motivou

A v1 amarrava cada Líder a um número de WhatsApp físico. Isso não escala: uma organização não consegue manter dezenas de chips/números, o WhatsApp Business API tem custo por conversa e burocracia de aprovação da Meta, e muitas plataformas nem suportam múltiplos números numa conta.

## 2. A decisão

**Canal de mensageria vira peça plugável**, no mesmo espírito dos instrumentos. Princípios:

1. **Canal não é propriedade fixa do Líder.** É uma capacidade disponível, e o fluxo decide qual canal usar em cada interação.
2. **Um time pode usar um canal, o outro, ou os dois ao mesmo tempo.** A maioria usará um só; alguns (que falam com público interno E externo) usarão os dois. O sistema não impõe a divisão — disponibiliza e deixa o consultor compor.
3. **A divisão típica (Telegram para equipe interna, WhatsApp para cliente externo) é tendência de uso, não regra do produto.** Ela emerge naturalmente porque a equipe interna topa instalar Telegram (grátis, sem fricção) e o cliente externo só está no WhatsApp. Mas é escolha do consultor ao montar o time, não amarração do sistema.
4. **Os canais se conectam à organização**, e todos os times da organização têm os canais configurados à disposição (coerente com o resto da arquitetura, em que recursos pendem da organização).

## 3. Por que Telegram primeiro

- **Grátis e instantâneo:** a Bot API do Telegram não cobra por mensagem e o bot é criado em minutos pelo BotFather, sem aprovação, sem verificação, sem período de espera.
- **Prova a mecânica difícil sem custo nem burocracia:** o desafio real (resposta voltando e casando com a execução pausada) é resolvido uma vez, de graça, antes de enfrentar a burocracia da Meta.
- **Resolve já parte da dor:** os fluxos internos (aprovações, notificações, perguntas à equipe) saem do WhatsApp e vão pro Telegram imediatamente, aliviando a pressão por números.
- **Constrói a fundação:** uma vez que "canal" é plugável e provado com Telegram, o WhatsApp é "mais um canal" no mesmo encaixe.

## 4. A peça difícil, declarada desde já

Um instrumento comum é mão única: aciona, recebe, segue. **Um canal de mensageria é mão dupla e assíncrono:**

- **Saída** — o Líder manda uma mensagem. Relativamente simples.
- **Entrada** — alguém responde, e essa resposta precisa voltar para o **fluxo certo, na execução certa**, que pode estar pausada esperando há minutos ou dias.

A entrada tem **dois modos distintos**, ambos presentes nos casos reais do Batuta:

- **Modo A — Resposta a uma execução pausada.** O fluxo pausou numa espera-por-humano (aprovação do blog, pergunta pontual), mandou a pergunta por um canal, e a resposta chega por esse mesmo canal. O sistema precisa casar a mensagem recebida com a execução pausada.
- **Modo B — Início de um fluxo novo.** Alguém manda uma mensagem "do nada" (o consultor manda foto do recibo; o paciente pergunta sobre agenda). Não é resposta a nada — é um gatilho que inicia uma execução nova.

Os dois modos entram pelo mesmo canal e precisam ser distinguidos. Este é o coração técnico do trabalho, e **não muda o motor de orquestração** — o motor já sabe pausar e retomar (espera-por-humano já validada) e já sabe ser disparado por gatilho. O que muda é *por onde* a entrada chega e *como* ela é roteada.

## 5. Arquitetura proposta

### 5.1. Conceito central: o Canal como abstração

Criar uma abstração de **Canal** com uma interface comum, da qual Telegram e (futuramente) WhatsApp são implementações. A interface mínima:

- `enviar(destinatario, mensagem)` — manda uma mensagem pelo canal.
- `receber(payload)` — recebe um evento de entrada (mensagem que chegou) e o normaliza para um formato interno único, independente do canal.

Toda a lógica de roteamento de entrada (Modo A vs Modo B) opera sobre o **formato normalizado**, não sobre o formato específico do Telegram ou do WhatsApp. Assim, adicionar WhatsApp depois é implementar `enviar`/`receber` para ele — o roteamento já está pronto e não muda.

### 5.2. Tabelas novas

**`canais`** — os canais configurados de uma organização.
- `id`, `organizacao_id` (FK obrigatório — isolamento)
- `tipo` (`telegram` | `whatsapp` | futuros)
- `nome` (rótulo amigável, ex.: "Telegram interno da Lure")
- `config` (JSONB — dados não-secretos de configuração)
- `ativo` (bool)
- `criado_em`, `atualizado_em`

Os **segredos do canal** (token do bot Telegram, credenciais WhatsApp) **não vão aqui** — vão no cofre de chaves já existente, referenciados por este registro. Mantém a regra de segredos só no cérebro, nunca expostos.

**`identidades_canal`** — o vínculo entre uma pessoa real e seu identificador em cada canal. Essencial para roteamento e para identificar quem está falando.
- `id`, `organizacao_id`
- `canal_id` (FK)
- `identificador_externo` (o chat_id do Telegram, o número no WhatsApp)
- `rotulo` (quem é: "João, consultor" / "Maria, cliente X")
- `usuario_id` (FK opcional para `usuarios`, quando a pessoa é membro do Batuta — caso da equipe interna)
- `criado_em`

Esta tabela é o que permite, por exemplo, o caso do reembolso: a mensagem chega do Telegram/WhatsApp, o sistema olha o `identificador_externo`, encontra a identidade, e sabe que é "o consultor João" — exatamente o "identifica o consultor pelo telefone" dos casos reais.

**`mensagens_canal`** (opcional, recomendado) — log das mensagens que entraram e saíram, por canal, ligado à execução quando houver. Útil para auditoria, depuração e para a tela de inspeção mostrar a conversa. Pode ficar para uma etapa posterior se quiser enxugar o primeiro passo.

### 5.3. Mudança em tabelas existentes

- **A cadeia/nó** precisa poder dizer, num ponto de saída de mensagem (pergunta ao humano, aprovação, resposta final), **por qual canal** mandar e **para quem**. Provavelmente um campo no nó da cadeia indicando o canal e o destinatário (uma identidade de canal, ou uma regra para descobrir o destinatário a partir do contexto da execução).
- **A execução** precisa registrar, quando pausa esperando humano, **por qual canal e para qual identidade** a pergunta foi enviada — para que a resposta que chegar por aquele canal seja casada com ela (Modo A). Provavelmente campos na execução (ou na tabela de pausa) guardando `canal_id` e `identificador_externo` esperados.

### 5.4. Entrada: o webhook do canal

Cada canal recebe entrada por um **webhook** que o provedor (Telegram) chama quando chega mensagem. Endpoint sugerido: `POST /canais/{canal_id}/webhook`.

Fluxo ao receber uma mensagem:

1. **Normaliza** o payload do Telegram para o formato interno.
2. **Identifica a pessoa** via `identidades_canal` (pelo `identificador_externo`). Se não houver identidade conhecida, aplica política de desconhecido (ver 5.6).
3. **Decide o modo:**
   - Procura uma **execução pausada** naquela organização esperando resposta daquele `identificador_externo` naquele canal. Se achar → **Modo A**: entrega a resposta à execução pausada (reusa o mecanismo de espera-por-humano já existente, equivalente ao atual `responder` da execução, só que originado do canal em vez da tela).
   - Se não achar execução pausada correspondente → **Modo B**: verifica se existe uma automação daquela organização com gatilho do tipo "mensagem recebida" associada àquele canal. Se existir → dispara uma execução nova, com a mensagem como entrada. Se não existir → política de mensagem não-roteável (ver 5.6).

### 5.5. Saída: enviar mensagem pelo canal

Quando um nó do fluxo precisa mandar mensagem (pergunta, aprovação, resposta final), o cérebro chama `canal.enviar(destinatario, mensagem)`. Para o Telegram, é uma chamada à Bot API. O envio é registrado (em `mensagens_canal`, se adotada) e, se for uma pergunta que pausa o fluxo, a execução registra o canal e a identidade esperada para a resposta (ligando com o Modo A).

### 5.6. Casos de borda a tratar (decisões de produto embutidas)

- **Mensagem de identidade desconhecida:** alguém manda mensagem de um número/chat não cadastrado. Opções: ignorar; responder pedindo identificação; encaminhar para um fluxo de "primeiro contato". Sugestão para o primeiro passo: **ignorar com log** (registra em `mensagens_canal` como não-roteada), e evoluir depois. Confirmar com o maestro.
- **Resposta ambígua:** chega resposta de uma identidade que tem mais de uma execução pausada esperando. Sugestão: casar com a mais recente, e registrar; refinar depois se virar problema real.
- **Mensagem fora de janela:** no WhatsApp (futuro), há a janela de 24h da Meta. Não afeta Telegram. Anotar para a fase WhatsApp.
- **Idempotência:** o Telegram pode reenviar o mesmo update. O webhook precisa ser idempotente (ignorar update já processado, via `update_id`).

### 5.7. Restrições respeitadas

- ✅ **Não altera o motor** — entrada e saída são camadas em volta; o motor continua pausando/retomando e sendo disparado por gatilho como já faz.
- ✅ **Isolamento por organização** — `organizacao_id` obrigatório em `canais`, `identidades_canal`, e em toda busca de execução pausada/automação no roteamento.
- ✅ **Segredos só no cérebro** — token do bot no cofre, nunca na interface, nunca em log.
- ✅ **Interface só fala com o cérebro** — a configuração de canal na tela passa pelo cérebro; o webhook é endpoint do cérebro.
- ✅ **Fundação pronta para WhatsApp** — a abstração de Canal e o roteamento sobre formato normalizado fazem o WhatsApp ser uma implementação nova, não uma reescrita.

## 6. Plano de implementação (ordem sugerida)

Cada passo termina com commit + push; nada empilha sobre passo quebrado.

1. **Abstração de Canal** — definir a interface comum (`enviar`/`receber`) e o formato normalizado de mensagem de entrada. Sem implementação concreta ainda; só o contrato. Testes do formato normalizado.

2. **Schema** — migrations aditivas: `canais`, `identidades_canal`, (`mensagens_canal` se adotada agora), e os campos novos no nó da cadeia e na execução/pausa. Referência ao cofre para o segredo do canal.

3. **Configuração de canal na interface** — tela para a organização cadastrar um canal Telegram: nome, e o token (que vai pro cofre). Cadastro de identidades (`identidades_canal`): vincular pessoas a chat_ids, com rótulo. Sem envio/recebimento ainda — só persistência e gestão.

4. **Saída pelo Telegram** — implementar `enviar` para o Telegram (chamada à Bot API com o token do cofre). Teste: um nó de fluxo manda uma mensagem para uma identidade cadastrada e ela chega no Telegram.

5. **Webhook de entrada + normalização** — endpoint `POST /canais/{canal_id}/webhook`, idempotente, normalizando o update do Telegram. Registrar configuração do webhook no Telegram (setWebhook). Teste: mensagem enviada ao bot chega normalizada no cérebro.

6. **Roteamento Modo A (resposta a execução pausada)** — casar a mensagem recebida com a execução pausada esperando aquela identidade naquele canal, e entregar a resposta reusando o mecanismo de espera-por-humano. Teste ponta a ponta: fluxo pausa pedindo aprovação pelo Telegram, consultor responde pelo Telegram, fluxo retoma e conclui. Incluir o teste de pausa longa (responder depois) que já é padrão do projeto.

7. **Roteamento Modo B (iniciar fluxo novo)** — gatilho do tipo "mensagem recebida" associado a um canal; mensagem de identidade conhecida sem execução pausada dispara execução nova com a mensagem como entrada. Teste ponta a ponta: pessoa manda mensagem ao bot, uma automação dispara e processa.

8. **Casos de borda** — identidade desconhecida, resposta ambígua, idempotência. Implementar as políticas decididas na seção 5.6 (confirmar com o maestro as que ficaram em aberto).

9. **Tela de inspeção / log** — se `mensagens_canal` foi adotada, mostrar a conversa do canal ligada à execução, ajudando a depurar.

10. **Teste integrado com caso real** — reproduzir um caso real de ponta a ponta (ex.: aprovação interna pelo Telegram num fluxo de conteúdo), confirmando os dois modos e os dois sentidos.

## 7. O que NÃO entra neste primeiro passo, deliberadamente

- **WhatsApp** — entra depois, como nova implementação da abstração de Canal. A burocracia da Meta (Business API, verificação, BSP, janela de 24h, templates) é trabalho próprio, e a fundação já estará pronta para recebê-lo.
- **Grupos / múltiplos participantes** — só conversas diretas (1:1) no primeiro passo.
- **Mídia rica avançada** (botões interativos, carrosséis) — começar com texto e, no máximo, recebimento de arquivo/imagem se algum caso real exigir (o caso do recibo, por exemplo, é Modo B com imagem — confirmar se entra já ou depois).
- **Modo intermediação completo** (o agente como ponte de conversa contínua entre duas pessoas, do `PRODUTO.md`) — a fundação de canais habilita isso, mas o modo intermediação em si é desenho próprio, posterior.

## 8. Ponto de atenção sobre o caso do recibo (imagem na entrada)

Um dos casos reais (reembolso) tem entrada por **imagem** (foto do recibo), no Modo B. Vale confirmar com o maestro se o recebimento de imagem entra já no primeiro passo ou logo depois. Tecnicamente, é o webhook normalizar também anexos e o gatilho passá-los como entrada da execução — incremental sobre o que o plano já prevê, mas é escopo a confirmar.

## 9. Como entregar ao Claude Code

Sugiro:

> Adicionei `CANAL-MENSAGERIA-PLANO.md` na raiz. Lê junto com `ARQUITETURA.md` e confirma contra o código real os nomes de tabelas, endpoints e o mecanismo atual de espera-por-humano (como a resposta do humano chega hoje pela tela), porque o Modo A vai reusar esse mecanismo. Depois me apresenta um plano detalhado no padrão das fases anteriores (investigar/implementar/verificar com Definition of Done por etapa), seguindo a ordem dos 10 passos. **Não comece a implementar ainda** — quero aprovar o plano e, em especial, ver como você pretende casar a mensagem recebida com a execução pausada (Modo A) usando o que já existe.
