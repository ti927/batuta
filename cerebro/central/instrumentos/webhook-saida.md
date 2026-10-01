---
titulo: "Instrumento — Disparar webhook de saída"
area: "instrumentos"
slug: "webhook-saida"
tags: ["webhook", "saida", "notificar", "disparar", "integracao", "post", "instrumento"]
revisado_em: "2026-10-01"
fontes: ["cerebro/instrumentos/webhook_saida.py"]
---

# Instrumento — Disparar webhook de saída

> **Não é mais um pronto do Batuta (desde 01/10/2026).** Integração com serviço de fora é
> instrumento **personalizado**: crie em **🌟 Criar instrumento → Uma API** (ou **Um servidor
> MCP**, se o serviço tiver um), com a chave do serviço no próprio instrumento (pela IA:
> `montar_conector` ou `configurar_instrumento` com `conectar_mcp`). Os que já existem seguem
> funcionando e editáveis até serem trocados — este capítulo vale só para eles.
> Ver [[instrumentos/construir-conector]] e [[instrumentos/mcp]].

## Em uma frase
Avisa um sistema externo enviando um **POST** com dados a uma URL configurada.

## Para que serve / quando usar
Notificar, acionar ou registrar algo em outro sistema ao fim (ou no meio) de um fluxo — inclusive disparar
outra automação por webhook. É o par "de saída" do [[instrumentos/chamar-rest]] (que costuma consultar).

## Como usar (na tela)
1. Crie o instrumento **Disparar webhook de saída**.
2. Configure a **URL** que receberá o POST, os **cabeçalhos** fixos (sem segredos) e, se precisar
   autenticar, o **token bearer** (segredo).
3. Pendure no cinto do agente que notifica.

## Exemplos
- Avisar um sistema quando um pedido é aprovado.
- Disparar a automação de outro time por webhook.

## Limites e cuidados
- **Não pede aprovação por padrão** (decisão do maestro): webhook é gatilho de automação em massa — travar
  cada disparo inviabilizaria a automação. Se quiser barrar um disparo específico, ligue o interruptor
  "exige aprovação" **naquele nó** (escape para o caso raro).
- 401/403 e 5xx viram falha (a de servidor é retentável).

## Para a IA
Parâmetro no catálogo (`disparar_webhook`): `payload` (JSON). A URL e a autenticação são da **config** do
humano. Por padrão não pede aprovação; só sugira `pedir_aprovacao` se o disparo tiver efeito sensível e único.

## Relacionado
- [[instrumentos/chamar-rest]]
- [[automacoes/gatilhos]]
