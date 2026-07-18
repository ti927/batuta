---
titulo: "O Líder"
area: "times-agentes"
slug: "lider"
tags: ["lider", "agente", "ponte", "humano", "papel", "time"]
revisado_em: "2026-07-17"
fontes: ["PRODUTO.md §8", "cerebro/modelos.py (Agente.papel)"]
---

# O Líder

## Em uma frase
O Líder é um **agente especial** do time — a ponte com os humanos —, e cada time tem **no máximo um**.

## Para que serve / quando usar
O Líder é o agente que dá a "cara" do time para quem fala com ele: é quem tende a receber e a devolver a
conversa (por exemplo, o número/canal de atendimento). No fundo é um agente como os outros — mesmos 4
markdowns —, distinto pelo **papel** de líder.

## Como usar (na tela)
1. No time, o agente marcado como **Líder** aparece em destaque; os demais são agentes comuns.
2. Escreva os 4 markdowns do Líder como faria com qualquer agente (veja [[times-agentes/agente]]).
3. Pendure nele os instrumentos de canal (ex.: atendimento por Telegram), se o time conversa com pessoas.

## Exemplos
- Num time de atendimento, o Líder recebe a mensagem, resolve o que dá e chama um humano quando precisa.

## Limites e cuidados
- **Um Líder por time** (garantido pelo sistema).
- O Líder não é "mais inteligente" por ser líder — o comportamento vem dos markdowns dele, como em qualquer
  agente. Nada de esperar um preâmbulo escondido.

## Para a IA
Ao montar um time que conversa com humanos, defina o Líder como o ponto de contato e detalhe no markdown
dele como acolher e quando escalar para uma pessoa. Para os demais passos internos, use agentes comuns
encadeados.

## Relacionado
- [[times-agentes/agente]]
- [[times-agentes/time]]
- [[mensageria/conversas]]
