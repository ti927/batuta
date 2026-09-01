---
titulo: "Instrumento — Ler site (Firecrawl)"
area: "instrumentos"
slug: "ler-site-firecrawl"
tags: ["ler-site", "firecrawl", "javascript", "spa", "extrair", "pagina", "leitura", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/ler_site_firecrawl.py"]
---

# Instrumento — Ler site (Firecrawl)

## Em uma frase
Como o "Ler site (Tavily)", mas **renderiza páginas feitas em JavaScript** (sites modernos, SPAs) e
devolve markdown limpo.

## Para que serve / quando usar
A opção **robusta** para ler uma página quando o Tavily não consegue — sites que só montam o conteúdo com
JavaScript. Se a página é simples, o [[instrumentos/ler-site]] (Tavily) costuma bastar e é mais barato.

## Como usar (na tela)
1. Crie o instrumento **Ler site (Firecrawl)**.
2. Deixe **Só o conteúdo principal** ligado (remove menus, rodapés e barras laterais).
3. Ajuste o **Tamanho máximo** e aponte a **chave** Firecrawl da organização (deixe em branco para usar a
   do pool).

## Exemplos
- Ler um portal moderno que o Tavily devolve vazio.

## Limites e cuidados
- Renderizar JS é mais lento — o instrumento dá folga de tempo.
- Precisa da chave Firecrawl cadastrada na organização (sem fallback de ambiente).
- Só leitura → ninguém precisa aprovar nada.

## Para a IA
Parâmetro no catálogo (`ler_site_firecrawl`): `url`. Prefira o Tavily por padrão; recorra ao Firecrawl
quando a página exigir JavaScript ou o Tavily falhar.

## Relacionado
- [[instrumentos/ler-site]]
- [[instrumentos/busca-web]]
