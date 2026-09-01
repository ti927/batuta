---
titulo: "A ficha da execução (como um dado chega ao próximo passo)"
area: "automacoes"
slug: "ficha-da-execucao"
tags: ["ficha", "dados", "anotar", "variavel", "entrada", "gatilho", "regra exata", "para cada item", "lista", "repetir"]
revisado_em: "2026-09-01"
fontes: ["cerebro/orquestracao/ficha.py", "cerebro/orquestracao/cadeia.py", "PRODUTO.md §14"]
---

# A ficha da execução (como um dado chega ao próximo passo)

## Em uma frase
Cada execução carrega uma **ficha** — valores com nome que atravessam a automação inteira e
chegam a **todos** os passos, sem depender de nenhum agente lembrar de repeti-los.

## Para que serve / quando usar
Entre um passo e outro trafega **texto**: o que o agente escreveu no fim vira a entrada do
próximo. Só isso não basta. Se o agente resume ("Aprovado, seguindo"), tudo o que ele não
repetiu **some** — e o passo seguinte trava pedindo dados que já existiam.

A ficha resolve isso. Ela guarda:

- **`entrada`** — o que o gatilho trouxe. Entra sozinha, no começo, e nunca se perde.
- **o que os agentes guardarem** — com o instrumento **`anotar`**: uma URL gerada, um total
  apurado, o nome do cliente. Quem vier depois lê da ficha.

## Como usar (na tela)
1. Na documentação do agente (**Habilidades**), diga o que ele deve guardar: *"guarde a URL
   da imagem em `url_da_capa`"*. Ele chama `anotar` sozinho.
2. Na **inspeção da execução**, abra **"A ficha desta execução"** para ver todos os valores,
   e em cada passo a linha **"Guardou na ficha"**.
3. Nomes são normalizados: `Total do Pedido`, `total do pedido` e `total_do_pedido` são o
   **mesmo** campo. Use nomes curtos e estáveis.

## O que a ficha destrava

### Regra exata na seta
Uma saída pode ter, além da frase "siga por aqui quando…", uma **regra exata** sobre um
campo da ficha: `total` `está entre` `1` e `10`. Quando ela existe, **quem confere é o
sistema, não a IA** — e a borda fica certa (10 entra, 11 não). Configure em
**Saídas → Regra exata (opcional)**.

Use quando a decisão for numérica ou de correspondência exata (faixa de valor, categoria,
campo preenchido). Deixe com o agente o que for de julgamento ("o texto ficou bom?").

### Nó "Para cada item"
Um passo que lê uma **lista** da ficha e repete o trecho seguinte **uma vez por item**. Cada
repetição é um caminho próprio — elas não se misturam. Dentro dela, os agentes leem `item`
(ou o nome que você escolher), `item_numero` e `item_total`.

Opcionalmente, o que cada repetição produzir é **somado** num campo da ficha
("Somar o resultado de cada repetição em"), e o fluxo segue com o apanhado.

## Exemplos
- **O caso que motivou a ficha:** o gatilho traz título, subtítulo e URL do artigo. O
  primeiro agente gera a capa e pede aprovação. Ao voltar, ele responde só "Aprovado" — e
  mesmo assim o gerador de carrossel recebe título, subtítulo e URL, porque estão na ficha.
- **Variável de fluxo:** o agente apura o total do pedido e guarda em `total`; três passos
  depois, outro agente escreve o e-mail usando esse número.
- **Regra exata:** `total` `é maior que` `5000` → Aprovação do gerente; `total` `está entre`
  `0` e `5000` → Segue direto.
- **Para cada item:** o agente lista os clientes inadimplentes em `inadimplentes`; o nó
  "Para cada item" faz o cobrador rodar uma vez por cliente, e soma os retornos em
  `relatorio`.

## Limites e cuidados
- **A ficha guarda texto**, não planilha. É um punhado de valores nomeados (até 40), não uma
  estrutura tipada com campos e tipos. Quem conduz o trabalho continua sendo o agente lendo
  e escrevendo em prosa.
- **O último a escrever vence.** Se dois caminhos anotam o mesmo campo, fica o último. Para
  valores de ramos diferentes, use nomes diferentes (`capa_1x1`, `capa_9x16`).
- **Uma lista tem teto de 20 itens** por repetição. Acima disso o excedente **não roda** — e
  a execução diz quantos ficaram de fora. Nunca corta em silêncio.
- **A regra exata precisa que o campo exista.** Se ninguém anotou aquele campo, ou se o
  valor não é número numa comparação numérica, o sistema **não** decide sozinho: devolve a
  escolha ao agente e escreve no rastro o que não deu para conferir.
- **Na conversa por mensageria não há ficha** — lá o que guarda contexto é a memória entre
  turnos do próprio atendimento. A ficha é da automação.

## Para a IA
`execucoes.dados` (JSONB) é a ficha; o módulo puro é `orquestracao/ficha.py`. Ela nasce em
`disparo.rodar_execucao` com `{"entrada": <texto do gatilho>}`, é mutada no lugar pelo motor
e persistida a cada passo (e no fim). Atravessa a pausa de aprovação: `retoma` e o portão
por canal a leem e a devolvem.

O agente recebe a ficha na **mensagem do turno** (não no prompt de sistema — ali ela
invalidaria o cache de prompt) e ganha a ferramenta `anotar` **apenas** quando roda dentro
de uma automação.

Na saída, a regra exata é `{"campo", "operador", "valor", "valor2"}`, com operadores
`igual | diferente | contem | nao_contem | maior | maior_ou_igual | menor | menor_ou_igual |
entre | preenchido | vazio`. `avaliar_regra` devolve `True`, `False` ou **`None`**; `None`
significa "não deu para decidir" e **nunca** é tratado como `False` — a saída volta para o
agente e o motivo vai ao rastro (`passo.saida.regras`).

O nó `{"tipo": "cada", "lista", "item_em", "acumular_em"}` é **estrutural**: não roda IA e
não conta como passo. Ele abre um ramo por item; a junção implícita passa a valer por
`(ramo, nó)`, então as repetições não se fundem. A lista é lida como array JSON ou uma
linha por item (marcadores `-`, `*`, `1.` são retirados).

Ao montar uma cadeia: **não** instrua o agente a "repetir os dados no texto final" — mande-o
`anotar`. Ao diagnosticar "o passo N não recebeu os dados", olhe a ficha da execução antes
de olhar o texto.

## Relacionado
- [[automacoes/condicoes-e-ramos]]
- [[automacoes/cadeia-e-grafo]]
- [[automacoes/execucoes-e-inspecao]]
- [[automacoes/erros-no-fluxo]]
- [[automacoes/pedir-aprovacao]]
