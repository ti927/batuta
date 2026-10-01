---
titulo: "Instrumento — Busca na web (Exa — semântica)"
area: "instrumentos"
slug: "busca-exa"
tags: ["busca-exa", "busca", "semantica", "exa", "significado", "diverso", "instrumento"]
revisado_em: "2026-10-01"
fontes: ["cerebro/instrumentos/busca_exa.py"]
---

# Instrumento — Busca na web (Exa — semântica)

> **Não é mais um pronto do Batuta (desde 01/10/2026).** Integração com serviço de fora é
> instrumento **personalizado**: crie em **🌟 Criar instrumento → Uma API** (ou **Um servidor
> MCP**, se o serviço tiver um), com a chave do serviço no próprio instrumento (pela IA:
> `montar_conector` ou `configurar_instrumento` com `conectar_mcp`). Os que já existem seguem
> funcionando e editáveis até serem trocados — este capítulo vale só para eles.
> Ver [[instrumentos/construir-conector]] e [[instrumentos/mcp]].

## Em uma frase
Busca na internet por **significado** (não só por palavra-chave) e devolve uma lista de resultados — boa
para achar ângulos e fontes diversas.

## Para que serve / quando usar
Uma alternativa ao [[instrumentos/busca-web]] (Tavily) quando a busca por palavra-chave fica presa sempre
no mesmo topo. A busca semântica tende a trazer material mais variado.

## Como usar (na tela)
1. Crie o instrumento **Busca na web (Exa — semântica)**.
2. Escolha o **Tipo de busca** (rápida, equilibrada, profunda), a **Categoria** (notícias, pesquisa,
   empresa, relatório financeiro), a **Recência** e a **quantidade**; defina **sites a incluir / excluir**.
3. A **chave** reusa a chave Exa da organização.

## Exemplos
- Levantar ângulos diferentes sobre um tema, quando o Tavily repete as mesmas fontes.

## Limites e cuidados
- Os parâmetros são do **humano**, na config; o agente só passa a consulta.
- Profunda é mais cara e lenta.
- Só leitura → ninguém precisa aprovar nada.

## Para a IA
Parâmetro no catálogo (`busca_exa`): `consulta`. Use quando o objetivo é **diversidade** de fontes/ângulos;
para busca direta por palavra-chave, o Tavily costuma bastar.

## Relacionado
- [[instrumentos/busca-web]]
- [[instrumentos/ler-site]]
