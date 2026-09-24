---
titulo: "O cérebro da organização"
area: "cerebro"
slug: "o-que-e-o-cerebro"
tags: ["cerebro", "quadros", "biblioteca", "arquivos", "compartilhar", "entre agentes", "entre times", "planilha", "memoria"]
revisado_em: "2026-09-24"
fontes: ["docs/CEREBRO-PLANO.md", "PRODUTO.md §9"]
---

# O cérebro da organização

> **Em construção.** A base dos quadros já existe, mas os agentes ainda não conseguem usá-la e ainda
> não há tela. Este capítulo diz o que o cérebro é e para onde ele vai.

## Em uma frase
O lugar onde a organização guarda o que os agentes precisam **passar uns para os outros**, inclusive
entre times diferentes.

## Para que serve / quando usar
Um agente produz uma informação e outro precisa dela depois, às vezes em outro time e em outro dia. Em vez
de uma planilha no meio, o cérebro guarda essa informação dentro do Batuta.

O cérebro tem três partes:

- **Quadros** — dados organizados em colunas, que agentes e pessoas escrevem e leem. É a primeira parte a
  ficar pronta. Ver [[cerebro/quadros]].
- **Arquivos** — PDF, Word ou planilha anexados a uma linha de um quadro (a nota fiscal na conta a pagar,
  o currículo no candidato), com o agente lendo o conteúdo. Vem depois.
- **Biblioteca** — documentos da empresa em que o agente procura a resposta pelo sentido ("o que dizem
  nossos contratos sobre reajuste?"). Vem depois dos arquivos.

A **memória do agente** continua existindo e é outra coisa: é o que **um** agente aprende para ele mesmo.
Os outros agentes não enxergam.

## Como usar (na tela)
Ainda não há tela. Quando houver, o cérebro vai ficar no menu, no nível da organização.

## Exemplos
- O agente do Radar grava toda semana se as IAs citaram a empresa; o agente do Painel lê essas linhas e
  junta com os números do site; os analistas de cinco times leem o resumo antes de escolher a pauta.
- Um agente lê as notas fiscais que chegam e registra cada uma; outro pede aprovação; um terceiro agenda o
  pagamento. Os três trabalham nas mesmas linhas.

## Limites e cuidados
- **O cérebro não substitui o sistema oficial da empresa.** Se o dado já mora num sistema (estoque,
  contabilidade, folha, um app próprio), a fonte é esse sistema, e o agente lê e escreve lá. O cérebro
  guarda o trabalho dos agentes: o que já foi feito, o que um deixou para o outro, o histórico.
- Não é ferramenta de gráficos e relatórios gerenciais. Ele faz tabela, filtro e totais.
- Até existir proteção por coluna, **não guarde CPF, salário nem dados de saúde** num quadro.

## Para a IA
O cérebro ainda está em construção: **não ofereça quadros ao consultor como algo pronto para usar**. Se
ele perguntar, explique o que vem e diga que ainda não dá para montar.

Quando estiver pronto, a pergunta a fazer para decidir onde guardar uma informação é **"quem mais precisa
disso, e quando?"**:

| A informação… | Guarde em |
|---|---|
| serve só para o próximo passo desta mesma execução | a ficha da execução (`anotar`) |
| é algo que um agente aprende para si mesmo | a memória do agente |
| precisa chegar a outro agente, outro time ou outro dia | um **quadro** |
| já mora num sistema oficial da empresa | o próprio sistema, por um instrumento |
| é um documento longo que se consulta pelo sentido | a Biblioteca (quando existir) |

## Relacionado
- [[cerebro/quadros]]
- [[times-agentes/memoria-do-agente]]
- [[automacoes/ficha-da-execucao]]
