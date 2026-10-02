---
titulo: "Instrumento — Ler página da web"
area: "instrumentos"
slug: "ler-pagina"
tags: ["ler-pagina", "ler-site", "pagina", "link", "url", "extrair", "web", "anthropic", "instrumento"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/ler_pagina.py", "cerebro/instrumentos/anthropic_servidor.py"]
---

# Instrumento — Ler página da web

## Em uma frase
A IA abre um link e devolve, em português, **o que o agente pediu** da página.

## Para que serve / quando usar
Quando já se tem o endereço: o artigo que a pesquisa achou, a página de produtos de um cliente, um
edital publicado. O agente diz o que quer ("a tabela de preços", "a data e o local do evento") e recebe
só isso, não a página inteira.

## Como usar (na tela)
1. Crie o instrumento **Ler página da web** (aparece quando a organização tem a chave da Anthropic).
2. Ajuste, se quiser: o **modelo** (o Haiku já vem escolhido) e o **tamanho máximo lido** — corta
   páginas enormes para o custo não disparar.
3. No markdown do agente, diga **o que extrair** de cada tipo de página.

## Exemplos
- Depois de [[instrumentos/pesquisar-web]], ler o artigo mais relevante e resumir os 5 pontos principais.
- Ler a página de um evento e extrair data, local e preço.

## Limites e cuidados
- **Não abre página com login** nem site que só monta o conteúdo no navegador (JavaScript pesado) —
  nesses casos a página vem vazia ou o instrumento avisa que não conseguiu abrir.
- Lê texto, HTML e PDF. Endereço com até 250 caracteres.
- Custo: só os tokens da página (medido em 02/10/2026: cerca de US$ 0,05 numa página da Wikipédia
  no Sonnet; menos no Haiku).
- Só leitura → ninguém precisa aprovar nada.

## Para a IA
Parâmetros no catálogo (`ler_pagina`): `url` (completa, com https://) e `o_que_extrair`. Devolve
`conteudo` e `avisos`. Se falhar com "não pôde ser aberta", a página exige login, bloqueia robôs ou está
fora do ar — não insista no mesmo link.

## Relacionado
- [[instrumentos/pesquisar-web]]
- [[instrumentos/ler-documento]]
