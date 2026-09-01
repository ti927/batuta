---
titulo: "Gatilhos (o que inicia um fluxo)"
area: "automacoes"
slug: "gatilhos"
tags: ["gatilho", "manual", "agendamento", "webhook", "comentario", "instagram", "entrada"]
revisado_em: "2026-07-17"
fontes: ["PRODUTO.md §12", "cerebro/agendador.py", "cerebro/rotas/webhooks.py", "cerebro/rotas/instagram_webhook.py"]
---

# Gatilhos (o que inicia um fluxo)

## Em uma frase
O gatilho diz **como** a automação começa; há quatro tipos, e cada automação tem o seu.

## Para que serve / quando usar
- **Manual** — você (ou alguém) dispara pelo botão "Rodar agora". Bom para testar ou rodar sob demanda.
- **Agendamento** — roda sozinho num horário fixo (diário, semanal, mensal, no fuso de Brasília).
- **Webhook** — um sistema externo dispara por uma **URL** (POST); o corpo enviado vira a entrada.
- **Comentário do Instagram** — cada comentário num post de uma conta conectada dispara o fluxo.

## Como usar (na tela)
1. No nó **Gatilho** do construtor, escolha o tipo.
2. **Agendamento:** defina frequência + horário, e (opcional) a **"Mensagem que o gatilho envia ao
   fluxo"** — esse texto chega ao **primeiro agente** como a entrada dele.
3. **Webhook:** salve a automação para gerar a URL; ela só dispara com a automação **ativa**.
4. **Comentário do Instagram:** defina os filtros (posts, palavra-chave, teto/hora); a **conta** é
   escolhida pelo humano na tela do gatilho (a IA não pluga o token).

## Exemplos
- Lembrete todo dia 1º às 9h (agendamento) com a mensagem "Gere o lembrete mensal de fechamento."
- Um CRM externo chama o webhook do time a cada novo lead.

## Limites e cuidados
- **A URL do webhook** aparece ao abrir aquela automação (ou no nó Gatilho), não no painel do time.
- Um **gatilho recém-criado ou duplicado** pode nascer "a conectar" (webhook/conta pendente) — avise.
- **Passar parâmetros ao 1º agente:** é um **texto livre** (a "entrada"), não campos nomeados. Para
  vários "parâmetros", escreva-os no texto e instrua o agente a lê-los.
- **A entrada não morre no primeiro passo.** Ela entra na **ficha da execução** (no campo
  `entrada`) e chega a **todos** os passos, do primeiro ao último — nenhum agente precisa
  repeti-la no texto para que o próximo a receba. Ver [[automacoes/ficha-da-execucao]].

## Para a IA
Nunca afirme o tipo de gatilho de memória — confira no retrato do time (`tipo_gatilho` por automação).
Gatilho/webhook é **por automação**, nunca "do time". Ao montar comentário do Instagram, avise que falta
o humano escolher a conta. Para agendamento por um AGENTE (disparo futuro), veja
[[instrumentos/agendar-automacao]] — o alvo deve ser **manual + ativa**.

## Relacionado
- [[automacoes/automacao]]
- [[automacoes/ficha-da-execucao]]
- [[instrumentos/agendar-automacao]]
- [[instrumentos/webhook-saida]]
