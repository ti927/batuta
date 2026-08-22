---
titulo: "Instrumento — Chamar API REST"
area: "instrumentos"
slug: "chamar-rest"
tags: ["rest", "api", "http", "integracao", "get", "post", "leitura", "escrita", "instrumento"]
revisado_em: "2026-08-08"
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
5. Se a consulta devolve uma **lista** de registros, use **Campos da resposta** para trazer só os campos que
   o agente vai usar — enxuga a resposta e corta o custo de tokens (veja abaixo).

## Exemplos
- GET num endpoint de consulta (leitura, sem portão).
- POST que cria um registro num sistema (escrita → portão antes).

## Limites e cuidados
- A irreversibilidade depende do **método**: leitura (GET/HEAD/OPTIONS) **não** exige portão; escrita sim.
- Respostas legítimas (2xx e mesmo um 404) voltam ao agente como dado; 401/403 e 5xx viram falha do
  instrumento (a de servidor é retentável).
- Não coloque segredos nos cabeçalhos fixos — use o campo de token.
- **API de banco** (Pix, boleto) exige mais do que token: pede um **certificado digital** na conexão.
  Isso não se configura aqui — cadastre uma credencial do tipo certificado e aponte para ela; o token
  de acesso, quando o banco pedir, é obtido e renovado sozinho. Ver
  [[segredos/certificado-digital-mtls]].
- **Respostas grandes custam tokens.** A resposta inteira é reenviada ao agente a cada passo do fluxo. Uma
  busca que traz dezenas de registros com dezenas de campos cada (comum em CRMs e no Bubble) pode custar
  milhares de tokens por chamada. Use **Campos da resposta** (`campos_resposta`) para trazer só os campos
  úteis — não muda o que a busca filtra, só enxuga o que volta ao agente.

## Para a IA
Parâmetros no catálogo (`chamar_api_rest`): `parametros_query` e `corpo` (JSON, para POST/PUT/PATCH). A URL,
o método, a autenticação e o filtro **`campos_resposta`** são da **config** do humano. Se o método escreve,
garanta portão antes. O par de "só notificar/disparar" é o [[instrumentos/webhook-saida]].

**Corte de custo (importante ao montar um GET que lê listas):** preencha `campos_resposta` com apenas os
campos que o agente usa (nome exato da API, ex.: `["_id","cpo.NomeCliente"]`). A resposta é reenviada ao
modelo a cada passo — trazer tudo quando o agente usa poucos campos multiplica o custo. Vazio = resposta
inteira; só deixe assim quando o agente precisar mesmo de todos os campos. O filtro reconhece listas no topo
e o formato `results` do Bubble; formato não reconhecido volta intacto (nunca descarta dado por engano).

## Relacionado
- [[instrumentos/webhook-saida]]
- [[instrumentos/mcp]]
- [[automacoes/portao-de-aprovacao]]
- [[segredos/certificado-digital-mtls]]
