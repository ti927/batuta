---
titulo: "Instrumento — Busca na web (Tavily)"
area: "instrumentos"
slug: "busca-web"
tags: ["busca-web", "busca", "internet", "tavily", "recencia", "dominios", "instrumento"]
revisado_em: "2026-10-01"
fontes: ["cerebro/instrumentos/busca_web.py"]
---

# Instrumento — Busca na web (Tavily)

> **Não é mais um pronto do Batuta (desde 01/10/2026).** Integração com serviço de fora é
> instrumento **personalizado**: crie em **🌟 Criar instrumento → Uma API** (ou **Um servidor
> MCP**, se o serviço tiver um), com a chave do serviço no próprio instrumento (pela IA:
> `montar_conector` ou `configurar_instrumento` com `conectar_mcp`). Os que já existem seguem
> funcionando e editáveis até serem trocados — este capítulo vale só para eles.
> Ver [[instrumentos/construir-conector]] e [[instrumentos/mcp]].

## Em uma frase
Busca informação atualizada na internet e devolve uma lista de resultados (título, link e um trecho).

## Para que serve / quando usar
Quando o agente precisa de dados **recentes** ou que não estão na memória dele — pautas, cotações,
notícias, referências. Para ler um resultado inteiro, encadeie o [[instrumentos/ler-site]].

## Como usar (na tela)
Você **padroniza** a busca daquele instrumento na configuração — é o que evita a "mesma pauta de sempre":
1. Escolha o **Tipo** (geral, notícias, finanças), a **Recência** (24h, semana, mês, ano) e a
   **Profundidade**.
2. Defina a **quantidade** de resultados, o **país** (só no tipo geral) e listas de **sites a incluir /
   excluir**.
3. A **chave** reusa a chave Tavily da organização.

## Exemplos
- Um idealizador de pauta com Recência "semana" e sites de referência incluídos, para não repetir tema.

## Limites e cuidados
- Os parâmetros (tipo, recência, domínios) são do **humano**, na config; o agente só passa a consulta.
- Aprofundada custa mais créditos na Tavily.
- Só leitura → ninguém precisa aprovar nada.

## Para a IA
Parâmetro no catálogo (`busca_web`): `consulta` (só isso — o resto é config do humano). Se a busca traz
sempre o mesmo topo, o ajuste é na **Recência/domínios** da config, ou usar a busca semântica
([[instrumentos/busca-exa]]).

## Relacionado
- [[instrumentos/ler-site]]
- [[instrumentos/busca-exa]]
- [[segredos/chaves-de-ia]]
