---
titulo: "Canal Telegram (conectar e as regras do bot)"
area: "mensageria"
slug: "canal-telegram"
tags: ["telegram", "canal", "bot", "webhook", "atendente", "aprovacao", "alcance", "conectar"]
revisado_em: "2026-07-17"
fontes: ["cerebro/rotas/mensageria.py (ativar_canal)", "cerebro/mensageria/servico.py", "cerebro/mensageria/aprovacao.py", "project_telegram-canal-webhook-secret"]
---

# Canal Telegram (conectar e as regras do bot)

## Em uma frase
Um canal de Telegram é um instrumento **Enviar no Telegram** conectado (webhook) — e vale a regra de
ouro: **um bot = um webhook = um canal**.

## Para que serve / quando usar
Para o time **conversar** por Telegram (mão dupla): atender contatos e/ou receber aprovações de portão.
Enviar mensagem sem conectar já funciona; **conectar** é o que faz o bot **receber** de volta.

## Como usar (na tela)
1. Crie o instrumento de Telegram com o token do bot (um bot próprio no BotFather).
2. **Conecte o canal** (registra o webhook). Ao salvar, o Batuta checa o **alcance** e avisa se o
   destinatário ainda não deu /start.
3. Um canal tem **um agente atendente**: o agente que tem o instrumento no cinto.

## Exemplos
- Um bot de atendimento cujo agente responde as mensagens que chegam.
- Um bot que recebe o "aprovado/reprovado" de um portão.

## Limites e cuidados
- **Enviar** pode ser compartilhado entre agentes; **receber** (atender ou aprovar) é **exclusivo**.
- **Um bot, um atendente:** se o mesmo canal estiver no cinto de dois agentes, só o **mais antigo**
  responde.
- **Dois agentes/dois portões no mesmo bot para aprovação** só colidem se ficarem esperando aprovação do
  **mesmo humano, pelo mesmo bot, ao mesmo tempo** — os pedidos se misturam no chat e um "sim" resolve só
  o mais recente; o outro fica preso. Em série, é seguro.
- O Batuta **recusa** conectar dois canais com o **mesmo token** (409) — cada canal precisa do seu bot.

## Para a IA
Recomende **um bot por canal de aprovação/atendimento** (ou aprovadores/chats diferentes; ou aprovar pela
tela em concorrência). Conectar bot/token é pela tela (cofre) — você não faz. Não pendure o mesmo canal de
atendimento em dois agentes esperando que os dois atendam.

## Relacionado
- [[instrumentos/enviar-telegram]]
- [[automacoes/portao-de-aprovacao]]
- [[mensageria/conversas]]
