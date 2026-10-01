---
titulo: "Gatilhos (o que inicia um fluxo)"
area: "automacoes"
slug: "gatilhos"
tags: ["gatilho", "manual", "agendamento", "webhook", "comentario", "instagram", "entrada"]
revisado_em: "2026-10-01"
fontes: ["PRODUTO.md §12", "cerebro/agendador.py", "cerebro/rotas/webhooks.py", "cerebro/webhook_entrada.py"]
---

# Gatilhos (o que inicia um fluxo)

## Em uma frase
O gatilho diz **como** a automação começa; há três tipos, e cada automação tem o seu.

## Para que serve / quando usar
- **Manual** — você (ou alguém) dispara pelo botão "Rodar agora". Bom para testar ou rodar sob demanda.
- **Agendamento** — roda sozinho num horário fixo (diário, semanal, mensal, no fuso de Brasília).
- **Webhook** — um sistema externo dispara por uma **URL** (POST); o corpo enviado vira a entrada.
- Comentário em rede social (Instagram etc.) chega pelo **webhook**: o serviço que cuida da conta
  (ex.: Zernio) chama a URL da automação. O gatilho "Comentário do Instagram" saiu em 01/10/2026.

## Como usar (na tela)
1. No nó **Gatilho** do construtor, escolha o tipo.
2. **Agendamento:** defina frequência + horário, e (opcional) a **"Mensagem que o gatilho envia ao
   fluxo"** — esse texto chega ao **primeiro agente** como a entrada dele.
3. **Webhook:** salve a automação para gerar a URL; ela só dispara com a automação **ativa**.
   Para um serviço que avisa por webhook (rede social, ERP, pagamento), preencha também:
   - **Segredo (o mesmo cadastrado no serviço):** você inventa um segredo, cola aqui e no
     painel do serviço. Com ele, aviso sem a assinatura certa é recusado (ninguém mais
     dispara o fluxo pela URL). Em branco ao editar = mantém o guardado.
   - **Só dispara para o aviso:** o tipo de aviso que interessa (ex.: `comment.received`); os
     outros chegam, respondem "ok" e não disparam.
   - **Teto de disparos por hora** (0 = sem limite).

## Exemplos
- Lembrete todo dia 1º às 9h (agendamento) com a mensagem "Gere o lembrete mensal de fechamento."
- Um CRM externo chama o webhook do time a cada novo lead.
- Comentários do Instagram vindos de um serviço de redes sociais: webhook com segredo, aviso
  `comment.received`; o corpo (comentário, autor, post) vira a entrada do agente que responde.

## Limites e cuidados
- **A URL do webhook** aparece ao abrir aquela automação (ou no nó Gatilho), não no painel do time.
- Um **gatilho recém-criado ou duplicado** pode nascer "a conectar" (webhook/conta pendente) — avise.
- **Webhook — sempre ligado, sem configurar:** o mesmo aviso reentregue (mesmo id) dispara
  **uma vez só**; e aviso sobre algo que a **própria conta** fez (`isOwnAccount: true` e
  parecidos) **não dispara** — é o que impede o agente de responder a si mesmo em loop.
- **Webhook — filtros por campo** (`so_quando` / `nunca_quando`, só pela IA): aparecem na tela
  do gatilho e são preservados ao salvar.
- **Passar parâmetros ao 1º agente:** é um **texto livre** (a "entrada"), não campos nomeados. Para
  vários "parâmetros", escreva-os no texto e instrua o agente a lê-los.
- **A entrada não morre no primeiro passo.** Ela entra na **ficha da execução** (no campo
  `entrada`) e chega a **todos** os passos, do primeiro ao último — nenhum agente precisa
  repeti-la no texto para que o próximo a receba. Ver [[automacoes/ficha-da-execucao]].

## Para a IA
Nunca afirme o tipo de gatilho de memória — confira no retrato do time (`tipo_gatilho` por automação).
Gatilho/webhook é **por automação**, nunca "do time". O tipo `comentario_instagram` é recusado:
comentário de rede social é webhook. No **webhook**, a config aceita `evento`, `so_quando`/`nunca_quando`
(`[{campo: "a.b", valor}]`), `teto_por_hora` e `cabecalho_assinatura`; o **segredo você nunca manda**
(é recusado) — peça ao consultor para colá-lo na tela do gatilho e no painel do serviço. O endereço
a cadastrar no serviço aparece em `ver_automacao` (`endereco_webhook`). Para agendamento por um AGENTE (disparo futuro), veja
[[instrumentos/agendar-automacao]] — o alvo deve ser **manual + ativa**.

## Relacionado
- [[automacoes/automacao]]
- [[automacoes/ficha-da-execucao]]
- [[instrumentos/agendar-automacao]]
- [[instrumentos/webhook-saida]]
