---
titulo: "Instrumento — Conectar a servidor MCP"
area: "instrumentos"
slug: "mcp"
tags: ["mcp", "model-context-protocol", "integracao", "ferramentas", "servidor", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/mcp.py"]
---

# Instrumento — Conectar a servidor MCP

## Em uma frase
Conecta o agente a um **servidor MCP** e lhe dá acesso a **todas** as ferramentas que esse servidor
publica — não a uma só.

## Para que serve / quando usar
O MCP (Model Context Protocol) é o padrão universal de integração de IA com sistemas. Se o sistema que
você quer integrar expõe um servidor MCP, este instrumento traz **de uma vez** todas as ferramentas dele
para o cinto do agente.

## Como usar (na tela)
1. Crie o instrumento **Conectar a servidor MCP**.
2. Configure a **URL** do servidor, o **transporte** (`streamable_http`, padrão, ou `sse`) e os
   **cabeçalhos** fixos (sem segredos).
3. Para autenticar, use o **token bearer** (segredo).
4. Pendure no cinto do agente — ele passa a enxergar todas as ferramentas do servidor.

## Exemplos
- Conectar a um servidor MCP interno que expõe ações de um ERP.

## Limites e cuidados
- Diferente dos outros instrumentos: **um** MCP vira **várias** ferramentas no cinto.
- Por segurança, é tratado como **ação irreversível** (o Batuta não sabe o que cada ferramenta do servidor
  faz) → considere uma **aprovação antes** conforme o uso.
- Cada acionamento abre a própria conexão (sem estado entre chamadas).

## Para a IA
Ao acionar isolado, o instrumento **testa a conexão e lista** as ferramentas do servidor. Uma vez no cinto,
as ferramentas do MCP aparecem como ferramentas normais do agente. Trate como potencialmente irreversível.

## Relacionado
- [[instrumentos/chamar-rest]]
- [[instrumentos/cinto]]
- [[segredos/segredos-de-instrumento]]
