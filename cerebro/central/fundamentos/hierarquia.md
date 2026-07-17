---
titulo: "A hierarquia: Organização, Time, Agentes"
area: "fundamentos"
slug: "hierarquia"
tags: ["fundamentos", "organizacao", "time", "agente", "estrutura", "hierarquia"]
revisado_em: "2026-07-17"
fontes: ["PRODUTO.md §6-11", "cerebro/modelos.py"]
---

# A hierarquia: Organização, Time, Agentes

## Em uma frase
Tudo no Batuta vive numa árvore: **Usuário → Organização → Time → Agentes** (com seus Instrumentos e
Automações).

## Para que serve / quando usar
Entender a hierarquia é o que te ajuda a saber **onde cada coisa mora** e **o que fica isolado do quê**.

- **Usuário** — uma pessoa com conta; cria organizações ou é convidada para elas.
- **Organização** — a empresa. É o espaço fechado onde vivem os times, as chaves, as credenciais, os
  membros e a auditoria. Uma organização **não enxerga** outra.
- **Time** — a unidade de trabalho, montada para um conjunto de tarefas. Dentro dele ficam os agentes,
  os instrumentos, as automações e (no futuro) a biblioteca do time.
- **Agentes** — as peças que fazem o trabalho, encadeadas em fluxos.

## Como usar (na tela)
1. Escolha a Organização ativa (seletor no rodapé da barra lateral).
2. Entre num Time (ou crie um) para ver seus agentes, instrumentos e automações.
3. Chaves e credenciais são **da Organização** (valem para todos os times dela).

## Exemplos
- Consultoria com 3 clientes → 3 organizações; cada uma com seus times (marketing, financeiro…).
- Um mesmo time pode ter **várias automações** (fluxos independentes, cada um com seu gatilho).

## Limites e cuidados
- **Isolamento por organização** é rígido: chaves, credenciais e dados de uma org não vazam para outra.
- Um **instrumento é do time** — para usá-lo em outro time, recria-se lá (ou duplica-se o time).

## Para a IA
Ao montar/editar, respeite o escopo: instrumento e agente são do **mesmo time**; credenciais e chaves
são da **organização**. Nunca proponha apontar recursos entre organizações diferentes. Ao duplicar um
time, os ids mudam e os canais nascem **desconectados**.

## Relacionado
- [[fundamentos/o-que-e-o-batuta]]
- [[times-agentes/agente]]
- [[segredos/chaves-de-ia]]
- [[admin/duplicar-time]]
