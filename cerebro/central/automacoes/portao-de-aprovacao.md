---
titulo: "Portão de aprovação (a espera humana)"
area: "automacoes"
slug: "portao-de-aprovacao"
tags: ["portao", "gate", "aprovacao", "aprovar", "reprovar", "cancelar", "humano", "pausa"]
revisado_em: "2026-07-17"
fontes: ["PRODUTO.md §14, §19", "cerebro/mensageria/aprovacao.py"]
---

# Portão de aprovação (a espera humana)

## Em uma frase
O portão **pausa** o fluxo e pede o OK de um humano antes de uma ação importante; quando a pessoa
responde, o fluxo **retoma**.

## Para que serve / quando usar
Sempre que houver uma **ação irreversível** (publicar, enviar, gravar num sistema), ponha um portão
**no passo anterior** — assim um humano aprova o que será feito antes de acontecer.

O humano pode **aprovar**, **reprovar** (o fluxo refaz/segue outro ramo) ou **cancelar** (encerra).

## Como usar (na tela)
1. No construtor, marque **"gate": aprovação** no **nó do agente que vem ANTES** da ação irreversível.
2. Quem **executa** a ação fica no **nó seguinte**, sem portão.
3. A aprovação pode ser respondida **na tela** da execução **ou por um canal** (ex.: Telegram) — quem
   recebe o pedido é quem aprova.

## Exemplos
- [redator prepara o artigo → **portão**] → [publica no WordPress].
- [gera a arte + escreve a legenda → **portão**] → [publica no Instagram].

## Limites e cuidados
- **Erro comum:** pôr o instrumento que publica **no mesmo nó** do portão — aí a ação nunca acontece
  (o nó só apresenta e espera). O portão vai num nó **antes**; a ação, no nó **seguinte**.
- **Cancelar** não é uma "saída" que você desenha — é embutido (botão na tela; "cancelar" no canal).
- Aprovação **por Telegram** tem cuidados de canal — veja [[mensageria/canal-telegram]].

## Para a IA
Derive a necessidade de portão de `acao_irreversivel` (não de uma lista fixa): só instrumentos de
ESCRITA/publicação exigem portão antes. Estrutura certa: nó que prepara e apresenta (gate=sim) → nó que
executa (gate=não), e o nó que executa precisa **receber tudo pronto** (ex.: mídia + legenda) senão o
agente trava pedindo o que falta. Cancelar é embutido — não desenhe saída de cancelar.

## Relacionado
- [[automacoes/cadeia-e-grafo]]
- [[operacao/parede-de-ativacao]]
- [[mensageria/canal-telegram]]
