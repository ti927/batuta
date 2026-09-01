---
titulo: "A Automação (a definição do fluxo)"
area: "automacoes"
slug: "automacao"
tags: ["automacao", "fluxo", "ativar", "desativar", "gatilho", "cadeia"]
revisado_em: "2026-07-17"
fontes: ["PRODUTO.md §14", "cerebro/modelos.py (Automacao)"]
---

# A Automação (a definição do fluxo)

## Em uma frase
Uma automação é **um fluxo**: um gatilho que o inicia + uma cadeia ordenada de agentes que o executam +
um interruptor liga/desliga.

## Para que serve / quando usar
A automação é a receita do trabalho. Um time pode ter **várias automações independentes** (ex.: "Postar
no Instagram" e "Responder comentários"), cada uma com seu próprio gatilho e sua própria cadeia.

## Como usar (na tela)
1. Na aba **Automações** do time, crie uma automação (dê um nome claro).
2. Defina o **gatilho** (como ela inicia) e monte a **cadeia** (o construtor visual de grafo).
3. Ajuste o **Tipo de fluxo** se for conversacional (prazos, saudação, horário).
4. **Ative** quando estiver pronta — nada roda até ativar.

## Exemplos
- Automação diária de blog (gatilho: agendamento) com cadeia idealizador → redator → revisor → publica.
- Automação de atendimento (gatilho: mensagem) com um agente atendente que bifurca conforme o caso.

## Limites e cuidados
- **Inativa não roda.** Ativar não impõe nenhuma trava. Quem segura uma ação que precisa
  de gente é o próprio agente, pelo instrumento [[automacoes/pedir-aprovacao]].
- Ao **duplicar**, a cópia nasce **inativa** (evita disparo em dobro de agendadas/webhook).

## Para a IA
Trabalhe sempre sobre a automação certa: com várias no time, pergunte **qual** antes de mexer (use o
`automacao_id`). Sinalize quando dá para ativar, mas **quem ativa é o consultor**. Nunca diga que o time
"já está no ar" antes de ativar.

## Relacionado
- [[automacoes/gatilhos]]
- [[automacoes/cadeia-e-grafo]]
- [[automacoes/pedir-aprovacao]]
- [[automacoes/pedir-aprovacao]]
