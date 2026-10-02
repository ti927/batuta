---
titulo: "Instrumento — Pesquisar na web"
area: "instrumentos"
slug: "pesquisar-web"
tags: ["pesquisar-web", "pesquisa", "busca", "web", "internet", "noticias", "fontes", "anthropic", "openai", "google", "instrumento"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/pesquisar_web.py", "cerebro/instrumentos/anthropic_servidor.py", "cerebro/instrumentos/openai_servidor.py", "cerebro/instrumentos/google_servidor.py", "cerebro/instrumentos/escolha_ia.py"]
---

# Instrumento — Pesquisar na web

## Em uma frase
A IA pesquisa na internet e devolve uma resposta em português **com as fontes** (título e link).

## Para que serve / quando usar
Quando o agente precisa de informação **atual** ou que não sabe: notícias, preços, concorrentes, dados
públicos, referências para uma pauta. Para ler por inteiro um link que a pesquisa trouxe, encadeie o
[[instrumentos/ler-pagina]].

## Como usar (na tela)
1. Crie o instrumento **Pesquisar na web** (aparece quando a organização tem a chave da Anthropic, da
   OpenAI ou do Google).
2. Ajuste, se quiser: o **modelo** — em branco, o Batuta usa o mais barato da IA que tem chave (Claude
   Haiku, GPT-5.6 Luna ou Gemini Flash-Lite, nessa ordem de preferência) —, o **máximo de buscas** por pesquisa e uma lista de **sites** onde buscar só
   (ou nunca buscar — um ou outro, não os dois).
3. Pendure no cinto do agente e diga no markdown dele **quando** pesquisar e o que fazer com as fontes.

## Exemplos
- Pauta da semana: "pesquise as 3 notícias mais relevantes sobre reforma tributária desta semana".
- Preço de mercado: "preço médio do aluguel de sala comercial em Campinas em 2026".

## Limites e cuidados
- **Custo real por uso**, medido pelo que a IA informa: US$ 10 por mil buscas + tokens. Medido em
  02/10/2026: **cerca de US$ 0,012 por pesquisa no GPT-5.6 Luna** (4 a 6 s); **de US$ 0,02 a 0,05 no
  Claude Haiku**, conforme o número de buscas; US$ 0,20 no Sonnet 5 (que lê muito mais). Na busca do
  **Google**: 5.000 buscas grátis por mês, depois US$ 14 por mil (o Batuta mostra sempre o preço cheio,
  porque não sabe quanto da franquia já foi usado).
- **Período:** a busca do Google filtra por data de verdade (o `desde` vira filtro); nas outras duas, não. O instrumento informa à IA a data de hoje, e o
  argumento opcional `desde` (AAAA-MM-DD) faz a IA descartar fonte mais antiga e dizer se sobrou pouco.
  Para "notícias da semana", passe `desde` = 7 dias atrás. Cada fonte vem com a `idade` da página.
- A resposta só vale o que as fontes valem — o agente deve citar as fontes quando o dado importa.
- Se a conta da Anthropic da empresa tiver a busca desligada (painel da Anthropic › Privacy), o
  instrumento falha com esse recado. Na OpenAI, os links das fontes vêm sem a marca `utm_source=openai`.
- No **Google**, "Nunca buscar nestes sites" é filtro da busca; "Buscar só nestes sites" vira uma regra
  para a IA (a busca dele não tem esse filtro). Os links das fontes passam por um endereço do Google que
  leva à página; o título é o nome do site. O máximo de buscas não vale: quem decide é a IA.
- Conta do Google **sem crédito** (projeto pré-pago que zerou): o instrumento avisa onde pôr crédito.
- Só leitura → ninguém precisa aprovar nada.

## Para a IA
Argumentos (`pesquisar_web`): `pergunta` (com o contexto: região, o que interessa) e, opcional,
`desde` (AAAA-MM-DD). Nome de argumento errado é recusado com a lista dos certos. Devolve `resposta`,
`fontes` (título, url e `idade` quando a busca informa) e `avisos` (ex.: `max_uses_exceeded` = atingiu o máximo de buscas e
respondeu com o que tinha). A IA que busca é a do `modelo` da configuração (Anthropic, OpenAI ou Google); em
branco, o Batuta escolhe pela chave da organização. Ao montar pela `configurar_instrumento`, deixe
`modelo` em branco, salvo pedido do consultor.

## Relacionado
- [[instrumentos/ler-pagina]]
- [[instrumentos/ler-documento]]
- [[segredos/chaves-de-ia]]
