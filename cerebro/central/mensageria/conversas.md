---
titulo: "Conversas (atendimento por mensageria)"
area: "mensageria"
slug: "conversas"
tags: ["conversa", "atendimento", "inbox", "takeover", "humano-assume", "timeout", "audio"]
revisado_em: "2026-07-17"
fontes: ["cerebro/mensageria/servico.py", "cerebro/mensageria/sweeper.py", "project_estado-atual-build-plan"]
---

# Conversas (atendimento por mensageria)

## Em uma frase
Quando um contato manda mensagem por um canal conectado, o time abre uma **conversa** e um agente atende —
com a opção de um humano assumir a qualquer momento.

## Para que serve / quando usar
Atendimento de mão dupla (hoje por Telegram): o agente responde as mensagens que chegam, mantém o fio da
conversa e sabe quando chamar uma pessoa. Cada canal tem **um agente atendente** (veja
[[mensageria/canal-telegram]]).

## Como usar (na tela)
1. Conecte o canal (o instrumento de Telegram com webhook) e pendure-o no agente atendente.
2. As conversas aparecem numa **caixa de entrada**; você acompanha e pode **assumir** (takeover) — a partir
   daí o agente para e quem responde é você.
3. Devolva ao agente quando quiser.

## Exemplos
- Um bot de atendimento que resolve dúvidas simples e passa para o humano os casos delicados.

## Limites e cuidados
- O atendimento tem **regras de borda uniformes**: junta mensagens em rajada (debounce), tem **teto** de
  idas e vindas antes de chamar um humano, **timeout** com aviso de retomada (nudge), proteção contra
  injeção de instruções, e transcrição de **áudio** (Whisper).
- Uma conversa parada é retomada/encerrada pelo mecanismo de tempo — não fica presa em silêncio.

## Para a IA
Para atendimento, o canal precisa estar **conectado** (webhook) e no cinto do **único** agente atendente.
Não pendure o mesmo canal em dois agentes esperando que ambos atendam. Ligar a memória do agente costuma
ajudar no atendimento (veja [[times-agentes/memoria-do-agente]]).

## Relacionado
- [[mensageria/canal-telegram]]
- [[times-agentes/lider]]
- [[times-agentes/memoria-do-agente]]
