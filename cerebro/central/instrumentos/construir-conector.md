---
titulo: "Construir um Conector (integração com API, sem código)"
area: "instrumentos"
slug: "construir-conector"
tags: ["conector", "api", "http", "integracao", "bubble", "constraints", "rest", "get", "post", "patch", "operacoes", "campos", "montar_conector", "instrumento", "oauth2", "conta de servico", "google", "somente leitura", "search console"]
revisado_em: "2026-09-22"
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

No destino `corpo`, o valor pode ser **JSON de verdade**: o que começa com `[` ou `{` (e é JSON
válido) e os literais `true`/`false`/`null` viram lista, objeto e booleano. É como se declara
`{"nome": "dimensions", "papel": "fixo", "destino": "corpo", "valor": "[\"query\"]"}` — o Google
recusa `dimensions` em texto. **Número NÃO é convertido**, de propósito: `"0055"` e ids longos viram
outra coisa ao virar número, e as APIs aceitam número em texto.

Regra de ouro: **um campo só existe se você o DECLARA**. Para a IA poder mandar um dado (o corpo de
um POST, o filtro de uma busca), esse campo precisa estar na lista `campos` com o `destino` certo.

## Autenticação — você NÃO pluga o segredo
Você declara só COMO a API autentica; o **segredo em si fica PENDENTE** para o consultor preencher na
tela do instrumento. Nunca ponha token, senha ou certificado no objeto — são ignorados de propósito.

`auth_tipo` aceita:
- **`nenhuma`** — API aberta.
- **`bearer`** — token no cabeçalho `Authorization`.
- **`cabecalho`** / **`query`** — chave num cabeçalho ou parâmetro; diga qual em `auth_nome`.
- **`basic`** — usuário e senha. O usuário (não-secreto) vai em `auth_usuario`; a senha é o segredo.
- **`oauth2`** — o serviço emite um token de curta duração. Preencha `auth_usuario` (o Client ID),
  `url_token` (o endereço que emite) e, se o serviço pedir, `escopo`. O Client Secret é o segredo. **O
  Batuta busca e renova esse token sozinho** — não invente uma operação "pegar token" nem peça ao
  agente que carregue o token entre chamadas: não funcionaria (os cabeçalhos são fixos) e já está
  resolvido pela plataforma.
- **`google_conta_servico`** — para QUALQUER API do Google (Search Console, Drive, Sheets, Agenda).
  Use este, e não `oauth2`, quando o serviço for do Google: a conta de serviço é uma identidade de
  **máquina**, então não tem tela de consentimento, não depende de app verificado pelo Google e **não
  expira**. O segredo é o **JSON inteiro** da chave (o consultor baixa no Google Cloud e cola no
  cofre). **`escopo` é obrigatório** — declare o mais estreito que a operação usa (Search Console só
  leitura: `https://www.googleapis.com/auth/webmasters.readonly`); pedir acesso amplo seria pior.
  Avise o consultor do passo que todo mundo esquece: **dar acesso ao e-mail da conta de serviço** no
  serviço de destino (no Search Console, como usuário da propriedade). Sem isso o Google responde 403
  e o erro parece ser da chave.

**Certificado digital (mTLS)** é outra coisa e **combina** com qualquer `auth_tipo`: é o arquivo com
que o cliente se identifica na conexão. Você não o configura — o consultor sobe o arquivo na tela do
instrumento —, mas você escolhe o `auth_tipo` que vai **junto** com ele:
- serviço que pede **só o certificado** (o caso comum de API de governo com e-CNPJ: Receita, SEFAZ,
  e-Social, nota fiscal) → `auth_tipo: "nenhuma"`. Aqui "nenhuma" significa "nada além do
  certificado", não "sem segurança";
- **banco** (Pix, boleto) → quase sempre `auth_tipo: "oauth2"`, certificado **e** token.

Se o consultor não souber qual é o caso, pergunte **com qual serviço** o instrumento vai falar antes
de montar. Ver [[segredos/certificado-digital-mtls]].

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
(só deixe assim quando o agente precisar mesmo de tudo). O filtro reconhece uma lista no topo, o
`response.results` do Bubble e as chaves de lista das APIs conhecidas (`results`, `rows`, `items`,
`data`, `records`); formato não reconhecido volta intacto.

### ⚠️ A armadilha: são os campos DE DENTRO da linha, não o nome da lista
`campos_resposta` filtra **cada registro**, não o envelope. O erro clássico é listar a chave que
CONTÉM os registros.

Resposta do Search Console:
```json
{"rows": [{"keys": ["2026-09-20"], "clicks": 5, "impressions": 900, "ctr": 0.005, "position": 8.2}],
 "responseAggregationType": "byProperty"}
```
- ✅ `["keys","clicks","impressions","ctr","position"]` — os campos da linha.
- ❌ `["rows","responseAggregationType"]` — nomes do envelope. Nenhuma linha tem um campo chamado
  `rows`, então **toda linha viraria vazia**.

Em 2026-09-22 isso aconteceu de verdade: a chamada voltava `200` com N linhas, todas sem cliques nem
impressões, e o agente — que só vê o resultado depois do filtro — concluiu que era falha do Google e
seguiu a análise com dado de dois meses antes.

**Hoje o Batuta te protege:** se o filtro esvaziaria TODOS os registros, ele devolve a resposta
intacta (filtro que não casa com nada é engano de configuração, não economia). E o "testar e detectar"
avisa na tela quando isso acontece. Mesmo assim, **liste os campos certos** — a proteção evita o
estrago, não faz a economia que você queria.

**Atenção ao TESTE:** "testar e detectar" roda de propósito **sem** `campos_resposta`, para mostrar a
resposta inteira e detectar todos os campos. Ou seja, o teste **não** reproduz o que o agente vai
receber. Depois de preencher `campos_resposta`, confira os nomes contra a lista de campos detectados.

## Testar e detectar
Depois de montar, use `testar_operacao_conector` para RODAR a operação com valores de exemplo e ver a
resposta real + os campos detectados — é assim que você confere que funciona e escolhe os
`campos_resposta`, sem envolver o consultor. Se a API pede token e ele ainda não está no cofre, o
teste volta com `ok=false` (autenticação): peça o token ao consultor e teste de novo.
Quando a API recusa (4xx), a resposta traz o **motivo que o serviço deu**, não um "falhou" genérico —
leia o campo `erro` e o `corpo`: é ali que está a explicação (ex.: `"startDate field is required"`,
`"User does not have sufficient permission for site"`). Não adivinhe a causa; ela está escrita.

## Limites e cuidados
- **Escrita pede aprovação — por OPERAÇÃO, não pelo conector inteiro.** O método é o sinal
  (GET lê; POST/PUT/PATCH/DELETE escrevem), e cada operação que escreve para e pede aprovação; as de
  leitura correm livres no mesmo instrumento. Para alguém confirmar antes, dê ao agente o instrumento
  **Pedir aprovação e aguardar** e escreva a regra no markdown dele.
- **Nem todo POST escreve.** Há API que CONSULTA por POST porque o filtro não cabe na URL — o
  `searchAnalytics/query` do Google Search Console é exatamente isso. Nesses casos marque
  `somente_leitura: true` na operação: sem isso, **cada consulta** pararia para pedir aprovação e o
  instrumento fica inutilizável. É declaração consciente de quem monta — o Batuta não tem como
  conferir se um POST escreve. Nunca marque por conveniência.
- Respostas legítimas (2xx e até um 404) voltam ao agente como dado; 401/403 e 5xx viram falha do
  instrumento (a de servidor é retentável).
- Não coloque segredos nos cabeçalhos fixos — use a autenticação (o token vai ao cofre).
- **⚠️ Destino errado é o erro mais caro daqui, porque ele é SILENCIOSO.** O agente manda o valor
  certo, o campo vai para o lugar errado da requisição, o serviço responde "criado com sucesso" — e o
  dado simplesmente não está lá. Caso real: num POST do Bubble, um campo de valor ficou com destino
  `query` enquanto os outros doze iam no `corpo`; todo reembolso era criado **sem o valor**, por
  semanas, e o agente jurava ter lançado (ele não enxerga em que parte da requisição o campo caiu).
  **Sintoma → causa:** *registro criado, mas um campo veio vazio* = esse campo está no destino errado.
  Confira se ele está no mesmo destino dos demais campos do registro (`corpo`, num POST/PATCH).
- **`[colchete]` na URL exige um campo de destino `url`.** Se sobrar um `[campo]` no endereço na hora
  de chamar, o Batuta **falha na hora e diz qual campo é** — em vez de chamar um endereço quebrado e
  deixar o agente inventar o motivo do erro. É falha definitiva: insistir não conserta montagem.

## Para a IA
- Monte/edite com **`montar_conector(conector, conector_id?)`** — sem `conector_id` cria; com ele edita
  (por exemplo, para acrescentar uma operação ou preencher `campos_resposta` depois do teste). O objeto
  precisa de `nome` ao criar; os campos secretos (token) NUNCA entram aqui.
- Teste com **`testar_operacao_conector(conector_id, operacao, valores?)`** antes de encaixar no cinto.
- Encaixe as ferramentas no cinto encaixando o CONECTOR no agente (`encaixar_instrumento`): cada
  operação declarada vira uma ação separada para o agente.
- O par "um endpoint só, sem operações" é o [[instrumentos/chamar-rest]]; o "só disparar/notificar" é o
  [[instrumentos/webhook-saida]].
- **Ao montar um POST/PATCH, confira o destino campo a campo antes de salvar:** os dados do registro vão
  todos no `corpo`; a query é para filtro/paginação; a `url` é só para `[colchete]`. Um campo sozinho na
  query no meio de um POST é quase sempre engano — e ninguém vai perceber, porque a API responde
  sucesso do mesmo jeito.
- **Se o consultor disser que um campo está vindo vazio no sistema dele, NÃO conclua que foi erro do
  agente** (nem invente que "mandei como texto"): leia a configuração da operação com
  `ver_instrumento` e confira o destino daquele campo. O agente não tem como saber onde o dado caiu.

## Relacionado
- [[instrumentos/chamar-rest]]
- [[instrumentos/webhook-saida]]
- [[segredos/segredos-de-instrumento]]
- [[automacoes/pedir-aprovacao]]
