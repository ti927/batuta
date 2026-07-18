---
titulo: "Instrumento — Chamar API REST"
area: "instrumentos"
slug: "chamar-rest"
tags: ["rest", "api", "http", "integracao", "get", "post", "leitura", "escrita", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/rest.py"]
---

# Instrumento — Chamar API REST

## Em uma frase
Faz uma requisição HTTP a uma API e devolve a resposta — para consultar ou enviar dados a um sistema
externo.

## Para que serve / quando usar
Integrar o time com qualquer sistema que tenha uma API REST: consultar um CRM, buscar um pedido, lançar um
registro. O endereço, o método e os cabeçalhos são fixos (config); a IA passa os parâmetros do momento.

## Como usar (na tela)
1. Crie o instrumento **Chamar API REST**.
2. Configure a **URL**, o **método** (GET/POST/PUT/PATCH/DELETE) e os **cabeçalhos** fixos (sem segredos).
3. Para autenticar, use o **token bearer** (segredo) — vira o cabeçalho `Authorization: Bearer`, em vez de
   deixar o segredo em claro nos cabeçalhos.
4. Se o método **escreve** (POST/PUT/PATCH/DELETE), coloque um **portão de aprovação antes**.

## Exemplos
- GET num endpoint de consulta (leitura, sem portão).
- POST que cria um registro num sistema (escrita → portão antes).

## Limites e cuidados
- A irreversibilidade depende do **método**: leitura (GET/HEAD/OPTIONS) **não** exige portão; escrita sim.
- Respostas legítimas (2xx e mesmo um 404) voltam ao agente como dado; 401/403 e 5xx viram falha do
  instrumento (a de servidor é retentável).
- Não coloque segredos nos cabeçalhos fixos — use o campo de token.

## Para a IA
Parâmetros no catálogo (`chamar_api_rest`): `parametros_query` e `corpo` (JSON, para POST/PUT/PATCH). A URL,
o método e a autenticação são da **config** do humano. Se o método escreve, garanta portão antes. O par de
"só notificar/disparar" é o [[instrumentos/webhook-saida]].

## Relacionado
- [[instrumentos/webhook-saida]]
- [[instrumentos/mcp]]
- [[automacoes/portao-de-aprovacao]]
