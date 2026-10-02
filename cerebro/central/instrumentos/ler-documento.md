---
titulo: "Instrumento — Ler documento (PDF)"
area: "instrumentos"
slug: "ler-documento"
tags: ["ler-documento", "pdf", "documento", "contrato", "nota-fiscal", "citacao", "anthropic", "instrumento"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/ler_documento.py", "cerebro/instrumentos/anthropic_servidor.py", "cerebro/instrumentos/openai_servidor.py"]
---

# Instrumento — Ler documento (PDF)

## Em uma frase
A IA lê um PDF e responde à pergunta do agente **citando a página** de onde tirou cada informação.

## Para que serve / quando usar
Contratos, notas fiscais, boletos, relatórios, editais: o agente pergunta ("qual o valor total e o
vencimento?", "quais as cláusulas de multa?") e recebe a resposta — com um modelo da Anthropic, também
os trechos e as páginas que a sustentam, para quem confere depois saber de onde veio cada dado.

## Como usar (na tela)
1. Crie o instrumento **Ler documento (PDF)** (aparece quando a organização tem a chave da Anthropic, da
   OpenAI ou do Google).
2. O modelo pode ficar em branco: o Batuta usa um modelo preciso da IA que tem chave (Claude Sonnet 5,
   GPT-5.6 Terra ou Gemini 3.8 Flash). Se as páginas de onde veio cada dado importam, escolha um modelo da Anthropic.
3. No markdown do agente, diga **o que perguntar** a cada tipo de documento.

## Exemplos
- Nota fiscal recebida pelo canal → extrair fornecedor, valor e vencimento para lançar no sistema.
- Contrato de um cliente → listar prazos e multas antes de uma renovação.

## Limites e cuidados
- O PDF precisa estar num **link público (https://)** — a própria IA o baixa (no Google, o Batuta baixa e manda junto; até
  20 MB). Arquivo recebido
  pelo canal ou gerado por outro instrumento já vem com um link assim.
- Até 32 MB e 600 páginas. Cada página custa cerca de 1.500 a 3.000 tokens. Medido em 02/10/2026: um PDF
  de 15 páginas com 3 perguntas custou US$ 0,042 no Haiku, com resposta correta citando trecho e página.
- Lê texto, tabelas e imagens das páginas (inclusive PDF escaneado).
- Só leitura → ninguém precisa aprovar nada.

## Para a IA
Nome de argumento errado é recusado com a lista dos certos (veja os argumentos em
`listar_tipos_instrumento`).
Parâmetros no catálogo (`ler_documento`): `url` (link público https do PDF) e `pergunta`. Devolve
`resposta` e `citacoes` (lista de `trecho` + `pagina`; vazia com modelo da OpenAI ou do Google, que não citam PDF). Use as citações quando o dado for para outro
sistema ou para uma pessoa conferir.

## Relacionado
- [[instrumentos/ler-pagina]]
- [[instrumentos/pesquisar-web]]
- [[instrumentos/arquivar-imagem]]
