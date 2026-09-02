---
titulo: "O Agente e os 4 markdowns"
area: "times-agentes"
slug: "agente"
tags: ["agente", "markdown", "agent", "skill", "tools", "soul", "modelo", "personalidade"]
revisado_em: "2026-09-02"
fontes: ["PRODUTO.md §11", "cerebro/modelos.py (Agente)", "feedback_sem-prompt-base-agentes"]
---

# O Agente e os 4 markdowns

## Em uma frase
Um agente é uma peça que faz **uma** função bem-feita; **todo o comportamento dele vem de 4 textos**
(markdowns) que você escreve — não há preâmbulo escondido.

## Para que serve / quando usar
Cada agente é único e encadeável. Você define o que ele é e como age escrevendo os 4 markdowns:

- **`agent.md` (Quem é)** — a identidade e a missão do agente, em uma frase forte.
- **`skill.md` (Habilidades)** — o passo a passo do que ele faz; as regras do trabalho dele.
- **`tools.md` (Cinto de instrumentos)** — como e quando usar cada instrumento do cinto.
- **`soul.md` (Personalidade)** — o tom, o jeito de falar, os cuidados.

Além dos markdowns, o agente tem um **modelo de IA** (qual "cérebro" usa) e, opcionalmente, **memória**.

## Como usar (na tela)
1. No time, abra o agente (drawer/popup) e edite os 4 markdowns.
2. Escolha o **modelo de IA** (a escolha do provedor é feita aqui).
3. Pendure os **instrumentos** no cinto dele e explique no `tools.md` quando usá-los.
4. Salve — o popup mantém o que você digitou; marcadores mostram o que ainda não foi salvo.

## Exemplos
- Um "Redator": `agent.md` diz que escreve artigos SEO; `skill.md` traz o processo; `tools.md` explica
  usar a busca web; `soul.md` fixa o tom da marca.

## Limites e cuidados
- **O comportamento vem 100% dos markdowns.** Se o agente está "tagarela" ou vago, o texto está vago —
  não há prompt-base para culpar. Seja específico.
- Um agente que **precisa de um dado** (ex.: qual cliente) deve **pedir** — instrua isso no markdown.
- **Os 4 markdowns são lidos juntos: instrução contraditória em um deles vence a regra nova do outro.**
  Ao mudar o jeito de fazer alguma coisa, **apague a instrução velha** — não basta escrever a nova em
  outro campo. Caso real (2026-09-02): a regra "chame Pedir aprovação e aguardar" entrou no `skill.md`,
  mas o `tools.md` continuou mandando pedir aprovação pelo Telegram e esperar "#aprovado#". O agente
  obedeceu a velha, o fluxo não parou e a execução terminou sem que ninguém aprovasse.

## Para a IA
Ao EDITAR um agente que já existe, leia os 4 markdowns ANTES de escrever: se a mudança troca o **jeito**
de fazer algo (outro instrumento, outro caminho), remova a instrução antiga no mesmo movimento. Regra
nova num campo + regra velha em outro = o agente segue a velha, calado.

Ao montar um agente, escreva os 4 markdowns com precisão; não confie num comportamento "padrão". Ensine
no markdown COMO usar cada instrumento do cinto (o instrumento é genérico; quem dá contexto é o texto do
agente). Um agente = uma função; se a tarefa tem várias etapas distintas, prefira **vários agentes**
encadeados a um agente que faz tudo.

## Relacionado
- [[instrumentos/cinto]]
- [[times-agentes/memoria-do-agente]]
- [[automacoes/cadeia-e-grafo]]
