---
titulo: "Instrumento — Ler site (Tavily)"
area: "instrumentos"
slug: "ler-site"
tags: ["ler-site", "extrair", "pagina", "tavily", "url", "leitura", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/ler_site.py"]
---

# Instrumento — Ler site (Tavily)

## Em uma frase
Abre uma URL e devolve o **conteúdo limpo** daquela página (o texto do artigo, sem menus e scripts).

## Para que serve / quando usar
Depois de achar um link (na busca), para **ler o conteúdo completo** da página. É diferente da busca (que
traz só um trecho) e do "Chamar API REST" (que traz o HTML cru). Para sites feitos em JavaScript, use o
[[instrumentos/ler-site-firecrawl]].

## Como usar (na tela)
1. Crie o instrumento **Ler site (Tavily)**.
2. Ajuste a **Profundidade** (rápida ou aprofundada), o **Formato** (markdown ou texto) e o **Tamanho
   máximo** (corta o conteúdo para não estourar o contexto do agente).
3. A **chave** reusa a chave Tavily da organização (a mesma da busca na web).

## Exemplos
- Busca na web → escolhe um resultado → **ler site** para trazer o artigo inteiro → resumir.

## Limites e cuidados
- **Não renderiza páginas feitas em JavaScript** — para essas, o Firecrawl.
- Precisa da chave Tavily cadastrada na organização.
- Só leitura → ninguém precisa aprovar nada.

## Para a IA
Parâmetro no catálogo (`ler_site`): `url`. A profundidade/formato/tamanho são da configuração do humano.
Se a página não abrir (pode exigir JS), o instrumento sugere tentar o Firecrawl.

## Relacionado
- [[instrumentos/ler-site-firecrawl]]
- [[instrumentos/busca-web]]
