---
titulo: "Conversas (atendimento por mensageria)"
area: "mensageria"
slug: "conversas"
tags: ["conversa", "atendimento", "inbox", "takeover", "humano-assume", "timeout", "audio"]
revisado_em: "2026-08-26"
fontes: ["cerebro/mensageria/servico.py", "cerebro/mensageria/sweeper.py", "cerebro/orquestracao/memoria_conversa.py", "cerebro/orquestracao/agente.py (portão nativo)", "cerebro/mensageria/config.py (parede governa a trava)", "project_estado-atual-build-plan"]
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
  injeção de instruções, transcrição de **áudio** (Whisper) e leitura de **imagem** (visão — o agente
  "enxerga" a foto que o contato manda; veja [[instrumentos/arquivar-imagem]] para guardá-la).
- Uma conversa parada é retomada/encerrada pelo mecanismo de tempo — não fica presa em silêncio. Isso vale
  para os **dois** tipos de espera: quando a bola está com o contato (ele não respondeu) e quando a bola está
  com o Batuta (**o agente começou a responder e o turno não voltou**, por queda ou travamento). Neste
  segundo caso, passados cerca de 30 minutos, o contato **recebe um aviso honesto** ("tive uma falha interna e
  não consegui concluir — pode reenviar?") e a conversa é destravada. Se a conversa conduzia uma **aprovação
  de portão**, a execução continua pendente e retomável: nada se perde, basta reenviar a resposta ou aprovar
  pela tela.
- A conversa tem **memória entre turnos**: o agente lembra o que já consultou e decidiu nos turnos
  anteriores da MESMA conversa, então não refaz do zero a cada mensagem. Para não crescer sem limite, os
  turnos antigos são condensados num resumo e a janela recente é mantida — a memória dura, o custo fica sob
  controle.
- **Ação irreversível na conversa é segurada pelo próprio sistema.** Se o agente atendente vai fazer algo
  irreversível (lançar, publicar, enviar, gravar num sistema externo), o Batuta **pausa e pede a confirmação
  do contato automaticamente** antes de a ação acontecer — é a mesma [[operacao/parede-de-ativacao]] que
  protege as automações, agindo agora **ao vivo**, dentro da conversa. A pessoa vê **uma** confirmação, na
  voz do próprio agente; se a organização desligar a parede, a ação segue direto.

## Para a IA
Para atendimento, o canal precisa estar **conectado** (webhook) e no cinto do **único** agente atendente.
Não pendure o mesmo canal em dois agentes esperando que ambos atendam. Ligar a memória do agente costuma
ajudar no atendimento (veja [[times-agentes/memoria-do-agente]]). A conversa em si já tem **memória entre
turnos** (o agente não "renasce" a cada mensagem; lembra o que já buscou) — não desenhe o fluxo supondo que
cada turno começa do zero, e não instrua o agente a "não re-buscar": ele já carrega o contexto anterior. Isso
é DIFERENTE da memória do agente (fichas por assunto, que persistem entre execuções distintas).
Como o sistema já **segura o irreversível e pede o OK** sozinho, **não** instrua o agente atendente a fazer
um ritual manual de "pergunte 'confirma?' e espere o sim" — isso viraria confirmação **em dobro** (a do
agente e a do sistema). Deixe-o **afirmar** o que vai fazer e agir; a trava aparece por conta própria quando
for preciso. Na conversa **não** existe o modelo de dois nós (prepara+gate → executa) da esteira: o portão é
nativo, no meio do próprio turno.
Se o consultor relatar *"respondi e não aconteceu nada"*, **não conclua que o agente ignorou a mensagem**:
verifique primeiro se o turno ficou preso (a conversa parada em "bot respondendo") e se cada turno está
carimbado com memória durável ou legado — os dois aparecem no diagnóstico da execução da conversa e nos
registros do sistema (veja [[operacao/sinais-e-diagnostico]]). O agente rodando **sem** memória entre turnos
é modo degradado, não o normal: ele re-busca dados e a trava de ação irreversível fica inativa.

## Relacionado
- [[mensageria/canal-telegram]]
- [[times-agentes/lider]]
- [[times-agentes/memoria-do-agente]]
