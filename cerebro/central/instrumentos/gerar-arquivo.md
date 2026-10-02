---
titulo: "Instrumento — Gerar arquivo e analisar dados"
area: "instrumentos"
slug: "gerar-arquivo"
tags: ["gerar-arquivo", "planilha", "excel", "xlsx", "word", "docx", "powerpoint", "pptx", "pdf", "grafico", "relatorio", "analise", "csv", "anthropic", "instrumento"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/gerar_arquivo.py", "cerebro/instrumentos/anthropic_servidor.py"]
---

# Instrumento — Gerar arquivo e analisar dados

## Em uma frase
A IA monta **arquivos prontos** — planilha, Word, PowerPoint, PDF, gráfico — e **analisa dados**, e
devolve o link de cada arquivo com um resumo.

## Para que serve / quando usar
Quando o trabalho termina num arquivo: o relatório mensal em PDF, a planilha de resumo de vendas com
gráfico, a apresentação para o cliente, a proposta em Word. Também para **analisar** dados que chegam
em CSV ou planilha (totais, médias, comparações) sem o agente fazer conta de cabeça.

## Como usar (na tela)
1. Crie o instrumento **Gerar arquivo e analisar dados** (aparece quando a organização tem a chave da
   Anthropic).
2. Em **Formatos que a IA sabe montar**, deixe só os que este agente usa (planilha, Word, PowerPoint,
   PDF) — cada pedido fica um pouco mais barato.
3. No markdown do agente, descreva **o arquivo esperado** (colunas, seções, formato) e o que fazer com
   o link (mandar no canal, gravar num quadro, passar ao próximo passo).

## Exemplos
- Recebe um CSV de vendas → devolve `resumo.xlsx` com total por mês e gráfico de barras.
- Junta os números da semana → gera o relatório em PDF e o agente seguinte manda no Telegram.

## Limites e cuidados
- **Leva tempo:** de dezenas de segundos a alguns minutos. A tela mostra "Gerando o arquivo (45 s)…"
  enquanto espera.
- **Custo real por uso:** tokens (a IA lê o manual de cada formato) + tempo de execução (1.550 h grátis
  por mês por organização, depois US$ 0,05 por hora). Medido em 02/10/2026: uma planilha de resumo de
  um CSV com gráfico custou **US$ 0,23** no Sonnet 5.
- Arquivos de entrada: até 10, por **link público (https://)**, até 30 MB cada.
- Os arquivos gerados ficam guardados no armazenamento do Batuta (link público) e, por até **30 dias**,
  também na Anthropic. Para clientes que exigem que nenhum dado fique com terceiros, avise antes de usar.
- Se nada for gerado (só análise), o resultado diz isso — o agente não deve dizer "segue o arquivo".
- Só gera arquivos → ninguém precisa aprovar (quem ENVIA o arquivo é que pode precisar).

## Para a IA
Parâmetros no catálogo (`gerar_arquivo`): `instrucao` (o que gerar/analisar, com os detalhes) e
`arquivos_url` (links públicos de entrada, opcional). Devolve `resumo`, `arquivos` (lista de `nome`,
`url`, `tipo`) e, se nada foi gerado, `aviso`. Encadeie o `url` no passo que envia ou grava.

## Relacionado
- [[instrumentos/ler-documento]]
- [[instrumentos/gerar-pdf]]
- [[instrumentos/pesquisar-web]]
