---
titulo: "Construir um Conector (integração com API, sem código)"
area: "instrumentos"
slug: "construir-conector"
tags: ["conector", "api", "http", "integracao", "bubble", "constraints", "rest", "get", "post", "patch", "operacoes", "campos", "montar_conector", "instrumento"]
revisado_em: "2026-08-12"
fontes: ["cerebro/instrumentos/conector.py", "cerebro/criacao/ferramentas.py"]
---

# Construir um Conector

## Em uma frase
Um **conector** é um instrumento que reúne VÁRIAS operações de uma mesma API (buscar, criar,
alterar…), cada operação virando uma ação no cinto do agente — declarado como DADO, sem código.

## Para que serve / quando usar
Quando o time precisa falar com um sistema externo que tem API (um CRM, um ERP, um app Bubble) e
esse sistema tem MAIS DE UMA chamada útil. Em vez de um "Chamar API REST" por endpoint, um único
conector agrupa todas as operações do serviço. Você (a IA) monta com `montar_conector`; o consultor
só cola o token no cofre.

## Como você monta (com `montar_conector`)
Você passa um objeto `conector` com identidade + autenticação + a lista de operações. Cada operação
tem um `metodo`, uma `url`, os `campos` (o que entra na requisição) e, opcional, `campos_resposta`
(o que volta ao agente). Cada CAMPO tem:
- **`papel`**: `"ia"` (a IA preenche na hora de acionar — vira um argumento; dê uma `descricao` boa)
  ou `"fixo"` (valor constante que você define em `valor`).
- **`destino`**: `"query"` (vai na URL depois do `?`), `"corpo"` (entra no JSON — para POST/PATCH/PUT)
  ou `"url"` (substitui um `[colchete]` na URL).

Regra de ouro: **um campo só existe se você o DECLARA**. Para a IA poder mandar um dado (o corpo de
um POST, o filtro de uma busca), esse campo precisa estar na lista `campos` com o `destino` certo.

## Autenticação — você NÃO pluga o token
Você declara só COMO a API autentica (`auth_tipo`: `bearer`, `cabecalho`, `query` ou `nenhuma`) e,
para `cabecalho`/`query`, o `auth_nome`. O **token em si é segredo**: fica PENDENTE e o consultor o
cola no cofre. Nunca ponha o token no objeto — ele é ignorado de propósito.

## APIs do Bubble (o caso mais comum aqui — leia com atenção)
A **Data API** do Bubble tem um endereço por tabela: `https://<app>/api/1.1/obj/<Tabela>`.

- **Buscar (GET)**: o filtro vai num ÚNICO parâmetro de query chamado **`constraints`** (destino
  `query`), cujo VALOR é um **array JSON**:
  `[{"key":"cpo.NomeCliente","constraint_type":"contains","value":"Maria"}]`.
  `constraint_type` pode ser `equals`, `contains`, `greater than`, `less than`, `in`, etc.
  ⚠️ O nome do campo tem de ser EXATAMENTE `constraints` — um erro de digitação (ex.: `contraints`)
  faz o Bubble IGNORAR o filtro e devolver o lote INTEIRO, como se não houvesse busca. Se um teste
  voltar registros demais e sem filtrar, o primeiro suspeito é o nome desse campo.
  Para ordenar: campos `sort_field` (ex.: `Created Date`) e `descending` (`true`) — também na query.
- **Criar (POST)** em `obj/<Tabela>`: os campos do registro vão no **corpo** (destino `corpo`),
  cada um um campo declarado (papel `ia` para os que a IA preenche).
- **Alterar (PATCH)** em `obj/<Tabela>/[id]`: use **PATCH** (mudança PARCIAL — só os campos enviados
  mudam). Evite **PUT**, que substitui o registro inteiro e ZERA o que você omitir. O `id` entra pela
  URL: coloque `[id]` na `url` e declare um campo `nome:"id", destino:"url", papel:"ia"`. Os campos a
  alterar vão no corpo.
- O Bubble **omite campos vazios** de cada registro — dois registros da mesma tabela podem trazer
  chaves diferentes. Por isso o "testar e detectar" une os campos de TODOS os registros retornados.

## Campos da resposta (corte de custo — importante)
A resposta é reenviada ao agente a cada passo do fluxo. Uma busca do Bubble traz dezenas de registros
com dezenas de campos — isso custa MUITOS tokens. Em `campos_resposta` liste só os campos que o agente
usa, com o nome EXATO da API (ex.: `["_id","cpo.NomeCliente","cpo.Valor"]`). Vazio = resposta inteira
(só deixe assim quando o agente precisar mesmo de tudo). O filtro reconhece listas no topo e o formato
`results` do Bubble; formato não reconhecido volta intacto (nunca descarta dado por engano).

## Testar e detectar
Depois de montar, use `testar_operacao_conector` para RODAR a operação com valores de exemplo e ver a
resposta real + os campos detectados — é assim que você confere que funciona e escolhe os
`campos_resposta`, sem envolver o consultor. Se a API pede token e ele ainda não está no cofre, o
teste volta com `ok=false` (autenticação): peça o token ao consultor e teste de novo.

## Limites e cuidados
- **Escrita exige portão.** Se QUALQUER operação escreve (POST/PUT/PATCH/DELETE), o conector inteiro
  passa a exigir a parede de aprovação — ponha `gate` no nó do agente que vem ANTES, na cadeia.
- Respostas legítimas (2xx e até um 404) voltam ao agente como dado; 401/403 e 5xx viram falha do
  instrumento (a de servidor é retentável).
- Não coloque segredos nos cabeçalhos fixos — use a autenticação (o token vai ao cofre).

## Para a IA
- Monte/edite com **`montar_conector(conector, conector_id?)`** — sem `conector_id` cria; com ele edita
  (por exemplo, para acrescentar uma operação ou preencher `campos_resposta` depois do teste). O objeto
  precisa de `nome` ao criar; os campos secretos (token) NUNCA entram aqui.
- Teste com **`testar_operacao_conector(conector_id, operacao, valores?)`** antes de encaixar no cinto.
- Encaixe as ferramentas no cinto encaixando o CONECTOR no agente (`encaixar_instrumento`): cada
  operação declarada vira uma ação separada para o agente.
- O par "um endpoint só, sem operações" é o [[instrumentos/chamar-rest]]; o "só disparar/notificar" é o
  [[instrumentos/webhook-saida]].

## Relacionado
- [[instrumentos/chamar-rest]]
- [[instrumentos/webhook-saida]]
- [[segredos/segredos-de-instrumento]]
- [[automacoes/portao-de-aprovacao]]
