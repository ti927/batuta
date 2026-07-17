---
titulo: "Gabarito de capítulo (modelo)"
area: "meta"
slug: "gabarito"
tags: ["meta", "modelo"]
revisado_em: "2026-07-17"
fontes: []
---

# Gabarito de capítulo — como escrever um capítulo da Central de Conhecimento

Este arquivo **não é um capítulo de verdade** — é o molde. Copie a estrutura abaixo para criar
qualquer capítulo novo em `docs/central/<area>/<slug>.md`.

A Central serve **dois leitores** com **um só documento**: a pessoa lê o capítulo inteiro; a IA
criadora recupera o mesmo capítulo (priorizando a seção **Para a IA**). Uma fonte só — nunca diverge.

## Frontmatter (obrigatório, no topo)

```yaml
---
titulo: "Nome do capítulo, em sentence case"
area: "fundamentos | times-agentes | automacoes | instrumentos | segredos | mensageria | operacao | admin"
slug: "kebab-case-unico"
tags: ["palavras", "chave", "para", "busca"]
revisado_em: "AAAA-MM-DD"   # carimbo da última revisão (manutenção)
fontes: ["PRODUTO.md §13", "cerebro/instrumentos/publicar_instagram.py"]  # onde a verdade mora
---
```

## Seções (nesta ordem)

- `## Em uma frase` — o resumo de uma linha. (humano + IA)
- `## Para que serve / quando usar` — o problema que resolve, quando escolher isto. (humano)
- `## Como usar (na tela)` — passo a passo do que a pessoa clica/preenche. (humano)
- `## Exemplos` — um ou dois exemplos concretos. (humano)
- `## Limites e cuidados` — o que NÃO dá, gotchas, erros comuns. (ambos)
- `## Para a IA` — regras operacionais precisas + **como orientar o usuário**. Para instrumento,
  **referencie o catálogo do código** (não repita os parâmetros em prosa — eles vivem em
  `catalogo_de_instrumentos`). (IA)
- `## Relacionado` — links para outros capítulos com `[[slug]]`.

## Regras de escrita (voz da marca — DESIGN-SYSTEM §2)

- **PT-BR**, direto e acolhedor, **sentence case**, sem jargão gratuito.
- Vocabulário oficial: **Agente / Instrumento / Automação / Time / Organização** (nunca "assistente/habilidade").
- **Não duplicar o que o código já é fonte da verdade.** Parâmetros de instrumento, listas de modelos,
  limites técnicos: referenciar, não recopiar (senão desatualiza).
- Frases curtas. Um conceito por parágrafo. Exemplos valem mais que definições.

---

## Esqueleto para copiar

```markdown
---
titulo: ""
area: ""
slug: ""
tags: []
revisado_em: "2026-07-17"
fontes: []
---

# <Título>

## Em uma frase
<...>

## Para que serve / quando usar
<...>

## Como usar (na tela)
1. <...>

## Exemplos
- <...>

## Limites e cuidados
- <...>

## Para a IA
<regras operacionais + como orientar o usuário; para instrumento, referencie o catálogo>

## Relacionado
- [[outro-slug]]
```
