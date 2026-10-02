---
titulo: "Instrumento — Gerar arquivo e analisar dados"
area: "instrumentos"
slug: "gerar-arquivo"
tags: ["gerar-arquivo", "planilha", "excel", "xlsx", "word", "docx", "powerpoint", "pptx", "pdf", "grafico", "relatorio", "analise", "csv", "anthropic", "openai", "instrumento"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/gerar_arquivo.py", "cerebro/instrumentos/anthropic_servidor.py", "cerebro/instrumentos/openai_servidor.py"]
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
   Anthropic ou da OpenAI).
2. O **modelo** pode ficar em branco: o Batuta usa o padrão da IA que tem chave (GPT-5.6 Luna ou Claude
   Sonnet 5). Em **Formatos que a IA sabe montar**, deixe só os que este agente usa (planilha, Word,
   PowerPoint, PDF).
3. No markdown do agente, descreva **o arquivo esperado** (colunas, seções, formato) e o que fazer com
   o link (mandar no canal, gravar num quadro, passar ao próximo passo).

## Exemplos
- Recebe um CSV de vendas → devolve `resumo.xlsx` com total por mês e gráfico de barras.
- Junta os números da semana → gera o relatório em PDF e o agente seguinte manda no Telegram.

## Limites e cuidados
- **Leva tempo:** de segundos (OpenAI) a alguns minutos (Anthropic). A tela mostra "Gerando o arquivo (45 s)…"
  enquanto espera.
- **Custo real por uso:** tokens + espaço de execução. Medido em 02/10/2026: na **OpenAI (GPT-5.6
  Luna)**, uma planilha com fórmula e gráfico custou **cerca de US$ 0,03 em 11 s** (o espaço de execução
  é US$ 0,03 por pedido); na **Anthropic**, uma planilha de resumo de um CSV com gráfico custou
  **US$ 0,23** no Sonnet 5, em 65 s (a IA lê o manual de cada formato; 1.550 h de execução grátis por mês
  por organização, depois US$ 0,05 por hora).
- Arquivos de entrada: até 10, por **link público (https://)**, até 30 MB cada.
- Os arquivos gerados ficam guardados no armazenamento do Batuta (link público) e, por até **30 dias**,
  também na Anthropic (na OpenAI, o espaço de execução some em 20 minutos e os arquivos de entrada são
  apagados ao fim do trabalho). Para clientes que exigem que nenhum dado fique com terceiros, avise antes de usar.
- Se nada for gerado (só análise), o resultado diz isso — o agente não deve dizer "segue o arquivo".
- Só gera arquivos → ninguém precisa aprovar (quem ENVIA o arquivo é que pode precisar).

## Para a IA
Nome de argumento errado é recusado com a lista dos certos (veja os argumentos em
`listar_tipos_instrumento`).
Parâmetros no catálogo (`gerar_arquivo`): `instrucao` (o que gerar/analisar, com os detalhes) e
`arquivos_url` (links públicos de entrada, opcional). Devolve `resumo`, `arquivos` (lista de `nome`,
`url`, `tipo`) e, se nada foi gerado, `aviso`. Encadeie o `url` no passo que envia ou grava.

## Relacionado
- [[instrumentos/ler-documento]]
- [[instrumentos/gerar-pdf]]
- [[instrumentos/pesquisar-web]]
