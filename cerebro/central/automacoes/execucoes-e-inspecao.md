---
titulo: "Execuções e inspeção"
area: "automacoes"
slug: "execucoes-e-inspecao"
tags: ["execucao", "inspecao", "rodar", "ao-vivo", "diagnostico", "passo-a-passo"]
revisado_em: "2026-07-17"
fontes: ["PRODUTO.md §15", "cerebro/orquestracao/disparo.py", "project_navegacao-time-centrica", "feedback_feedback-constante-ao-usuario"]
---

# Execuções e inspeção

## Em uma frase
Uma execução é **uma rodada** de uma automação; a tela de inspeção mostra o fluxo **rodando passo a passo**,
ao vivo.

## Para que serve / quando usar
Para acompanhar e diagnosticar: ver qual agente está trabalhando agora, o que cada passo produziu, onde
parou (num portão) ou por que falhou. Toda operação longa mostra **progresso ao vivo** (cronômetro + "o que
está acontecendo agora") — você nunca fica no escuro achando que travou.

## Como usar (na tela)
1. As execuções vivem **na página do time** (`/times/[id]`) — não há uma página de execuções separada.
2. Dispare uma automação manual pelo **"Rodar agora"**, ou veja as execuções que os gatilhos iniciaram.
3. Abra uma execução para **inspecionar**: os passos, as entradas/saídas, o tempo e o estado.

## Exemplos
- Acompanhar uma publicação: gera imagem → escreve legenda → **espera aprovação** → publica.
- Investigar por que um fluxo parou: a inspeção mostra o passo e o motivo (em português).

## Limites e cuidados
- Um fluxo pode ficar **parado num portão** esperando o humano — isso é normal, não é falha.
- Uma execução pode **falhar** e, dependendo do erro, ser **retentada** automaticamente — veja
  [[operacao/falhas-e-retentativa]].

## Para a IA
Ao diagnosticar com o consultor, baseie-se no **estado real** da execução (o que a inspeção mostra), não em
suposição. Um fluxo "parado" costuma ser um portão aguardando resposta, não um erro.

## Relacionado
- [[automacoes/automacao]]
- [[automacoes/portao-de-aprovacao]]
- [[operacao/falhas-e-retentativa]]
- [[operacao/uso-e-custos]]
