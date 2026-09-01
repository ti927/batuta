---
titulo: "Instrumento — Enviar no Telegram"
area: "instrumentos"
slug: "enviar-telegram"
tags: ["telegram", "enviar", "mensagem", "bot", "canal", "destinatario", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/enviar_telegram.py"]
---

# Instrumento — Enviar no Telegram

## Em uma frase
Envia uma mensagem de texto pelo Telegram usando um **bot** — para avisar alguém, responder ou pedir uma
aprovação por esse canal.

## Para que serve / quando usar
É o par de **saída** do canal de Telegram: o agente manda uma mensagem para um chat. Cada instância do
instrumento (com seu token de bot) é **um canal/bot** do time.

## Como usar (na tela)
1. Crie um bot no **BotFather** e pegue o **token**.
2. Crie o instrumento **Telegram: enviar mensagem**, cole o token (segredo) e defina o **Destinatário**
   (chat_id) se quiser um destino fixo.
3. Para conversa de mão dupla / aprovação, **conecte o canal** (webhook) — veja [[mensageria/canal-telegram]].

## Exemplos
- Avisar um grupo interno quando um fluxo termina.
- Enviar o pedido de aprovação para o chat de um gestor.

## Limites e cuidados
- O **Destinatário configurado prevalece**: se preenchido, o agente **não** o troca pelo texto dele.
- O Telegram recusa enviar para quem **nunca deu /start** no bot (o destinatário precisa iniciar a
  conversa uma vez).
- **Um bot entrega para um webhook só** → um bot = um canal. Não use o mesmo token em dois canais.

## Para a IA
Para só **enviar/avisar**, vários agentes podem compartilhar o mesmo instrumento. Mas o bot é a verdade
do destino (Config vence Args). Para **receber** (atender conversa ou aprovação), há regras próprias —
veja [[mensageria/canal-telegram]] (um atendente por canal; portões concorrentes no mesmo bot colidem).

## Relacionado
- [[mensageria/canal-telegram]]
- [[automacoes/pedir-aprovacao]]
