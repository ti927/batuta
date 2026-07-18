---
titulo: "O Time"
area: "times-agentes"
slug: "time"
tags: ["time", "agentes", "instrumentos", "automacoes", "unidade", "organizacao"]
revisado_em: "2026-07-17"
fontes: ["PRODUTO.md §7-9", "cerebro/modelos.py (Time)"]
---

# O Time

## Em uma frase
Um time é a **unidade de trabalho**: um conjunto de agentes, instrumentos e automações que resolvem, juntos,
um tipo de tarefa dentro de uma organização.

## Para que serve / quando usar
Agrupe num time tudo o que serve a um mesmo objetivo — "Conteúdo do Instagram", "Atendimento", "Blog". Uma
organização pode ter **vários times**, e cada time tem os seus:

- **Agentes** (incluindo, opcionalmente, um **Líder**) — quem faz o trabalho.
- **Instrumentos** — as capacidades no cinto dos agentes.
- **Automações** — os fluxos (cada um com seu gatilho e sua cadeia).

## Como usar (na tela)
1. Na organização, crie um **Time** com um nome claro.
2. Tudo do time vive **na página do time** (`/times/[id]`): o dashboard com os agentes, os instrumentos, as
   automações, as execuções e a IA companheira. Não há páginas soltas "de execução" ou "de automação" — é
   tudo dentro do time.
3. Monte os agentes e o fluxo — à mão ou com a **IA criadora**.

## Exemplos
- Um time "Marketing" com idealizador → redator → revisor → publicador, e uma automação diária de blog.

## Limites e cuidados
- Um time tem **no máximo um Líder**.
- **Duplicar** o time copia toda a estrutura (agentes, instrumentos, automações, memória), mas os canais
  nascem **desconectados** e as automações **inativas** — veja [[admin/duplicar-time]].

## Para a IA
Trabalhe sempre no escopo do time certo. Com várias automações no time, confirme **qual** antes de mexer.
Um time = um objetivo; se a demanda é bem diferente, prefira **outro time** a inchar um só.

## Relacionado
- [[fundamentos/hierarquia]]
- [[times-agentes/lider]]
- [[times-agentes/agente]]
- [[admin/duplicar-time]]
