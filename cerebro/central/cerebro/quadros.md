---
titulo: "Quadros"
area: "cerebro"
slug: "quadros"
tags: ["quadros", "quadro", "colunas", "linhas", "tipos", "chave", "planilha", "tabela", "historico", "filtro", "totais", "limites", "cerebro"]
revisado_em: "2026-09-24"
fontes: ["cerebro/quadros/servico.py", "cerebro/quadros/tipos.py", "cerebro/quadros/filtros.py", "cerebro/quadros/limites.py", "docs/CEREBRO-PLANO.md §5"]
---

# Quadros

> **Em construção.** As regras abaixo já valem no Batuta, mas os agentes ainda não têm a ferramenta para
> usar um quadro e ainda não há tela.

## Em uma frase
Um quadro é como uma aba de planilha, só que o Batuta sabe o que tem em cada coluna: confere o que entra,
anota quem gravou e calcula os totais.

## Para que serve / quando usar
Para um agente deixar informação que outro agente (ou uma pessoa) vai usar depois: o resultado de cada
rodada, a situação de cada cliente, a lista de contas a pagar, os números da semana.

## Como usar (na tela)
Ainda não há tela.

## As colunas
Cada coluna tem um nome e um tipo:

| Tipo | Serve para | Aceita, por exemplo |
|---|---|---|
| Texto curto | nomes, títulos (até 500 caracteres) | "Padaria do João" |
| Texto longo | observações, resumos | um parágrafo |
| Número | quantidades, notas | 12 · 12,5 · 1.234,56 |
| Dinheiro | valores (2 casas) | R$ 1.234,56 |
| Data | dia | 21/09/2026 · 2026-09-21 |
| Data e hora | momento (sem fuso = horário de Brasília) | 21/09/2026 14:30 |
| Sim ou não | marcações | sim · não |
| Opção de uma lista | estados, categorias | pendente · aprovado · pago |

**O Batuta confere tudo o que entra.** Uma data que não é data, um número que não é número ou uma opção
que não está na lista são recusados, com o motivo. Um número escrito "1.000" também é recusado, porque não
dá para saber se é mil ou um: escreva 1000.

**Tudo ou nada:** se uma linha de uma gravação tem problema, **nada** é gravado, e a resposta diz qual
linha e qual coluna. Nunca fica meia gravação.

## A coluna que identifica cada linha
Você pode dizer qual coluna (ou quais) identifica cada linha: a data da rodada e o número da pergunta; o
tema do briefing; o número da nota fiscal. Chamamos isso de **chave**. Com ela:

- **acrescentar** recusa uma linha que já existe;
- **gravar pela chave** cria a linha se ela não existe e, se existe, muda só as colunas informadas (as
  outras ficam como estavam). É assim que o briefing de um tema substitui o da semana passada, em vez de
  empilhar.

Um quadro sem chave só acumula, como um registro.

## Encontrar linhas
Os filtros usam as colunas e comparações simples: igual, diferente, maior, menor, contém, está entre
estes, vazio, preenchido. Dá para ordenar por qualquer coluna e pedir **"só a mais recente de"** uma
coluna ("as lacunas da rodada mais recente"). A consulta sempre diz **quantas linhas existem ao todo** e,
se devolveu só parte, de onde continuar.

**Os totais são calculados pelo Batuta**, não pela IA: contar, somar, média, menor e maior, agrupando por
até três colunas.

**"Já existe?"**: em vez de ler o quadro inteiro para descobrir o que falta, pergunte quais destes valores
já estão gravados.

## Quem gravou, e o histórico
Toda linha diz quem a gravou por último: qual agente e em qual execução, ou qual pessoa. Toda mudança fica
no histórico, com o valor de antes e o de depois, **inclusive de linhas apagadas**. Nem o registro de quem
gravou nem o histórico podem ser editados.

Dá para **desfazer uma rodada**: apagar tudo o que uma execução gravou.

## Limites e cuidados
Todo quadro tem limites, e todos podem ser vistos e ajustados:

| Limite | Padrão | Máximo |
|---|---|---|
| Colunas no quadro | 60 | 200 |
| Linhas por gravação | 500 | 5.000 |
| Linhas devolvidas por consulta | 200 | 1.000 |
| Linhas no quadro | 100.000 | 1.000.000 |
| Caracteres num texto longo | 20.000 | 200.000 |

- Um quadro que precisa passar de 100 mil linhas quase sempre é sinal de que o dado mora num sistema
  oficial, e não no cérebro. Ver [[cerebro/o-que-e-o-cerebro]].
- Mudar o tipo de uma coluna converte o que já existe; o que não se converte trava a mudança (ou vira
  vazio, se você pedir).

## Para a IA
Ainda não há ferramenta para os agentes nem para você: **não monte quadros e não prometa ao consultor
que dá para usar agora.**

Quando estiver pronto, ao desenhar um quadro:
- dê a cada coluna o tipo certo (data como **Data**, não texto) — é o que permite filtrar e ordenar;
- use **Opção de uma lista** para estados (pendente/aprovado/pago), nunca texto livre;
- defina a **chave** quando cada coisa deve ter uma linha só (um tema, um cliente, uma semana);
- escreva a **descrição** do quadro e das colunas: é o que o agente vai ler para saber o que gravar;
- **não** ensine formato de dado no texto do agente — o quadro já recusa o que não serve e explica.

## Relacionado
- [[cerebro/o-que-e-o-cerebro]]
- [[times-agentes/memoria-do-agente]]
- [[automacoes/ficha-da-execucao]]
