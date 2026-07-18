---
titulo: "Instrumento — Banco de dados direto (SQL)"
area: "instrumentos"
slug: "banco-sql"
tags: ["sql", "banco", "postgres", "consulta", "somente-leitura", "dados", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/sql.py"]
---

# Instrumento — Banco de dados direto (SQL)

## Em uma frase
Lê e escreve num banco de dados SQL pelo comando que o agente fornecer — útil para sistemas que **não têm
API**.

## Para que serve / quando usar
Quando o dado que o time precisa está num banco (relatório, consulta, lançamento) e não há uma API para
chegar até ele. Prefira sempre o modo **somente leitura** quando o agente só precisa consultar.

## Como usar (na tela)
1. Crie o instrumento **Banco de dados direto (SQL)**.
2. Configure a conexão: **host**, **porta**, **banco**, **usuário**, **senha** (segredo) e o modo de
   **SSL**.
3. Ligue **Somente leitura** se o agente só consulta — assim ele **recusa qualquer escrita** e **não
   exige portão**. Deixe desligado (permite escrita) só quando necessário, e aí ponha um **portão antes**.

## Exemplos
- Um agente de relatório com **somente leitura** que roda SELECTs num banco de vendas.
- Um lançamento pontual num banco (escrita → portão antes).

## Limites e cuidados
- Por ora, só **PostgreSQL**.
- Em modo somente leitura, um comando de escrita volta como recado ("reformule como consulta"), sem rodar.
- Um SELECT devolve até 100 linhas; um erro de SQL volta ao agente como dado (para ele corrigir), não como
  queda do instrumento.
- **Prefira parâmetros nomeados** (`:nome`) a concatenar valores no texto do SQL (evita injeção).

## Para a IA
Parâmetros no catálogo (`banco_sql`): `sql` e `parametros`. Se o instrumento está em **somente leitura**,
só proponha consultas. Escrita exige portão antes. Use `:nome` para os valores.

## Relacionado
- [[instrumentos/chamar-rest]]
- [[automacoes/portao-de-aprovacao]]
- [[segredos/segredos-de-instrumento]]
