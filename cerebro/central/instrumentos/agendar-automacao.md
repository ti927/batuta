---
titulo: "Instrumento — Agendar automação"
area: "instrumentos"
slug: "agendar-automacao"
tags: ["agendar", "agendamento", "disparo-futuro", "automacao", "alvo", "manual", "entrada", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/agendar_automacao.py", "cerebro/agendador.py"]
---

# Instrumento — Agendar automação

## Em uma frase
Permite que um **agente** reprograme um **disparo futuro** de uma automação — a própria ou a de outro
time da mesma organização.

## Para que serve / quando usar
Ao fim de um fluxo, conforme o resultado, um agente pode marcar "rode de novo daqui a 10 dias" ou "dispare
a automação do outro time em tal data". O **alvo** (qual automação) é fixado por **você** na configuração;
o agente decide só **se** e **quando**.

## Como usar (na tela)
1. Crie o instrumento **Agendar automação** e, na configuração, escolha a **automação-alvo** (seletor com
   as automações da organização).
2. Pendure no cinto do agente que decide o agendamento.
3. **A automação-alvo precisa estar ATIVA** — e o ideal é que o gatilho dela seja **manual** (senão ela
   também roda sozinha pelo cron do próprio agendamento → disparo em dobro).
4. O agente pode passar uma **entrada** (texto) que chega ao primeiro agente da automação-alvo.

## Exemplos
- Um fluxo de follow-up que se reprograma para "+7 dias" até o cliente responder.
- O time financeiro dispara o time fiscal numa data de fechamento.

## Limites e cuidados
- **Alvo inativo/ausente** → o agendamento é **cancelado** (visível, nunca em silêncio).
- Piso de ~1 minuto no futuro; teto de agendamentos pendentes por automação.
- Ao **duplicar** o time, o alvo é remapeado; confira se aponta para a automação certa.

## Para a IA
O alvo é do humano (config), não do agente — nunca proponha o agente "escolher" a automação. Requisito
real do disparo: alvo **ativo**; recomende alvo com gatilho **manual** para não haver cron recorrente
junto. A "entrada" é um texto que vira a entrada do 1º agente do alvo.

## Relacionado
- [[automacoes/chamar-automacao]] — quando você precisa do **resultado** da outra
  automação, é aquele passo, não este instrumento: este dispara e não fica sabendo o que
  aconteceu.
- [[automacoes/esperar]] — para adiar um passo **do mesmo fluxo**, sem perder a ficha.
- [[automacoes/gatilhos]]
- [[automacoes/automacao]]
