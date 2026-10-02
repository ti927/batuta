---
titulo: "Instrumento — Pesquisar na web"
area: "instrumentos"
slug: "pesquisar-web"
tags: ["pesquisar-web", "pesquisa", "busca", "web", "internet", "noticias", "fontes", "anthropic", "instrumento"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/pesquisar_web.py", "cerebro/instrumentos/anthropic_servidor.py"]
---

# Instrumento — Pesquisar na web

## Em uma frase
A IA pesquisa na internet e devolve uma resposta em português **com as fontes** (título e link).

## Para que serve / quando usar
Quando o agente precisa de informação **atual** ou que não sabe: notícias, preços, concorrentes, dados
públicos, referências para uma pauta. Para ler por inteiro um link que a pesquisa trouxe, encadeie o
[[instrumentos/ler-pagina]].

## Como usar (na tela)
1. Crie o instrumento **Pesquisar na web** (aparece quando a organização tem a chave da Anthropic).
2. Ajuste, se quiser: o **modelo** (o Haiku já vem escolhido e é o mais barato), o **máximo de buscas**
   por pesquisa e uma lista de **sites** onde buscar só (ou nunca buscar — um ou outro, não os dois).
3. Pendure no cinto do agente e diga no markdown dele **quando** pesquisar e o que fazer com as fontes.

## Exemplos
- Pauta da semana: "pesquise as 3 notícias mais relevantes sobre reforma tributária desta semana".
- Preço de mercado: "preço médio do aluguel de sala comercial em Campinas em 2026".

## Limites e cuidados
- **Custo real por uso**, medido pelo que a Anthropic informa: US$ 10 por mil buscas + tokens. Medido
  em 02/10/2026: **de US$ 0,02 a 0,05 por pesquisa no Haiku**, conforme o número de buscas (uma
  pesquisa de notícias com 2 buscas custou US$ 0,047), e US$ 0,20 no Sonnet 5 (que lê muito mais).
- **Período:** a busca da Anthropic não filtra por data. O instrumento informa à IA a data de hoje, e o
  argumento opcional `desde` (AAAA-MM-DD) faz a IA descartar fonte mais antiga e dizer se sobrou pouco.
  Para "notícias da semana", passe `desde` = 7 dias atrás. Cada fonte vem com a `idade` da página.
- A resposta só vale o que as fontes valem — o agente deve citar as fontes quando o dado importa.
- Se a conta da Anthropic da empresa tiver a busca desligada (painel da Anthropic › Privacy), o
  instrumento falha com esse recado.
- Só leitura → ninguém precisa aprovar nada.

## Para a IA
Argumentos (`pesquisar_web`): `pergunta` (com o contexto: região, o que interessa) e, opcional,
`desde` (AAAA-MM-DD). Nome de argumento errado é recusado com a lista dos certos. Devolve `resposta`,
`fontes` (título, url e `idade` quando a busca informa) e `avisos` (ex.: `max_uses_exceeded` = atingiu o máximo de buscas e
respondeu com o que tinha). Hoje só a Anthropic faz a busca; OpenAI e Google entram depois como opção
do mesmo instrumento.

## Relacionado
- [[instrumentos/ler-pagina]]
- [[instrumentos/ler-documento]]
- [[segredos/chaves-de-ia]]
