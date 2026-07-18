---
titulo: "Cadeia e grafo (o construtor do fluxo)"
area: "automacoes"
slug: "cadeia-e-grafo"
tags: ["cadeia", "grafo", "construtor", "no", "bifurcacao", "loop", "fluxo"]
revisado_em: "2026-07-17"
fontes: ["PRODUTO.md §14", "cerebro/orquestracao/cadeia.py", "project_orquestracao-bifurcacao"]
---

# Cadeia e grafo (o construtor do fluxo)

## Em uma frase
A cadeia é o **desenho do fluxo** de uma automação: nós (os passos) ligados por setas, montado num
construtor visual.

## Para que serve / quando usar
Para dizer **em que ordem** os agentes trabalham e **para onde** o fluxo segue depois de cada passo. A
orquestração do Batuta é por **bifurcação**: cada agente pode escolher **uma de várias saídas** conforme o
resultado — não é só uma fila reta. Loops são permitidos (voltar a um passo anterior).

## Como usar (na tela)
1. No construtor (tela cheia), o primeiro nó é o **Gatilho**; depois vêm os nós de **agente**.
2. Ligue os nós com setas para definir a ordem; num ponto de decisão, saia para **ramos diferentes**.
3. Marque **portão de aprovação** no nó que precede uma ação irreversível.
4. Salve — o Batuta valida a cadeia (referências corretas, sem becos sem saída).

## Exemplos
- Reta: idealizador → redator → revisor → **portão** → publica.
- Com bifurcação: um atendente que decide entre "resolver", "escalar para humano" ou "encerrar".

## Limites e cuidados
- **Cada nó de agente = uma função.** Se um passo faz coisas demais, quebre em mais nós.
- O nó que **executa** uma ação irreversível fica **depois** do portão, e precisa receber tudo **pronto**
  do nó anterior (senão o agente trava pedindo o que falta).
- **Cancelar** é embutido (não se desenha uma saída de cancelar).

## Para a IA
Modele por bifurcação, não só linear; loops são válidos. Estrutura de publicação: nó que prepara/apresenta
(gate=sim) → nó que executa (gate=não). Confira sempre a cadeia real antes de propor mudanças.

## Relacionado
- [[automacoes/automacao]]
- [[automacoes/portao-de-aprovacao]]
- [[automacoes/execucoes-e-inspecao]]
