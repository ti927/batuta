---
titulo: "Execuções e inspeção"
area: "automacoes"
slug: "execucoes-e-inspecao"
tags: ["execucao", "inspecao", "rodar", "ao-vivo", "diagnostico", "passo-a-passo"]
revisado_em: "2026-08-26"
fontes: ["PRODUTO.md §15", "cerebro/orquestracao/disparo.py", "cerebro/diagnostico_execucao.py", "project_navegacao-time-centrica", "feedback_feedback-constante-ao-usuario"]
---

# Execuções e inspeção

## Em uma frase
Uma execução é **uma rodada** de uma automação; a tela de inspeção mostra o fluxo **rodando passo a passo**,
ao vivo.

## Para que serve / quando usar
Para acompanhar e diagnosticar: ver qual agente está trabalhando agora, o que cada passo produziu, onde
parou (esperando uma pessoa) ou por que falhou. Toda operação longa mostra **progresso ao vivo** (cronômetro + "o que
está acontecendo agora") — você nunca fica no escuro achando que travou.

## Como usar (na tela)
1. As execuções vivem **na página do time** (`/times/[id]`) — não há uma página de execuções separada.
2. Dispare uma automação manual pelo **"Rodar agora"**, ou veja as execuções que os gatilhos iniciaram.
3. Abra uma execução para **inspecionar**: os passos, as entradas/saídas, o tempo e o estado.

## Exemplos
- Acompanhar uma publicação: gera imagem → escreve legenda → **espera aprovação** → publica.
- Investigar por que um fluxo parou: a inspeção mostra o passo e o motivo (em português).

## Limites e cuidados
- Um fluxo pode ficar **parado esperando uma pessoa** (o agente pediu aprovação) — isso é normal, não é falha.
- Uma execução pode **falhar** e, dependendo do erro, ser **retentada** automaticamente — veja
  [[operacao/falhas-e-retentativa]].
- **Execução "concluída" não garante que tudo deu certo.** Uma ferramenta pode ter respondido "não deu" sem
  derrubar o fluxo; o passo guarda essa falha crua e o diagnóstico a levanta como aviso, mesmo quando o
  agente escreveu que deu certo.
- **As conversas também deixam rastro.** O atendimento por mensageria gera sua própria linha do tempo, com
  os mesmos passos, instrumentos acionados e custo — dá para inspecionar um agente conversacional como se
  inspeciona uma automação.
- **"O passo N não recebeu os dados" tem um lugar próprio de olhar:** o painel
  **"A ficha desta execução"**, na inspeção, mostra tudo o que atravessou o fluxo. Cada passo
  ainda diz o que **guardou na ficha** e quais **regras exatas** o sistema conferiu (com o
  resultado de cada uma). Ver [[automacoes/ficha-da-execucao]].

## Para a IA
Ao diagnosticar com o consultor, baseie-se no **estado real** da execução (o que a inspeção mostra), não em
suposição. Um fluxo "parado" costuma ser um agente aguardando uma aprovação, não um erro.
O diagnóstico já entrega, quando dá para saber: **qual instrumento** falhou (pelo nome que o próprio erro
cita), **qual agente** o carrega e uma **ação sugerida derivada do tipo de erro** — arquivo grande demais
pede ajuste de configuração, não cadastro de credencial. Use essas referências em vez de deduzir pelo
instrumento que aparece por último no passo: o que falhou pode nem ter chegado a registrar passo, se o
agente estourou antes.

## Relacionado
- [[automacoes/automacao]]
- [[automacoes/ficha-da-execucao]]
- [[automacoes/pedir-aprovacao]]
- [[operacao/falhas-e-retentativa]]
- [[operacao/uso-e-custos]]
