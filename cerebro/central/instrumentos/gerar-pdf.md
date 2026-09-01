---
titulo: "Instrumento — Gerar PDF/documento"
area: "instrumentos"
slug: "gerar-pdf"
tags: ["gerar-pdf", "pdf", "documento", "relatorio", "contrato", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/gerar_pdf.py"]
---

# Instrumento — Gerar PDF/documento

## Em uma frase
Gera um documento PDF a partir de um título e um texto, e devolve um link para baixá-lo.

## Para que serve / quando usar
Produzir contratos, laudos, relatórios ou comunicados a partir do texto que o agente monta. É o passo de
"entregar em documento" ao fim de um fluxo.

## Como usar (na tela)
1. Crie o instrumento **Gerar PDF/documento**. Ele **não tem configuração** — o conteúdo vem todo do
   agente ao acionar.
2. Pendure no cinto do agente que produz o documento e explique no `skill.md` o formato esperado.

## Exemplos
- Um agente que fecha um relatório mensal e o entrega em PDF.
- Um comunicado formatado a partir do texto aprovado num passo anterior.

## Limites e cuidados
- O documento usa fontes nativas do PDF (cobrem os acentos do português). **Emojis** e caracteres muito
  fora do padrão viram "?" — é para conteúdo textual, não para arte gráfica.
- Não é irreversível (só gera o arquivo) — não precisa de aprovação.

## Para a IA
Parâmetros no catálogo (`gerar_pdf`): `titulo` (opcional) e `conteudo` (o corpo, em texto). O agente
entrega o texto já pronto; a formatação é simples (título + corpo).

## Relacionado
- [[instrumentos/cinto]]
- [[instrumentos/gerar-imagem]]
