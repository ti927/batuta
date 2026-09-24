---
titulo: "O cérebro da organização"
area: "cerebro"
slug: "o-que-e-o-cerebro"
tags: ["cerebro", "quadros", "biblioteca", "arquivos", "compartilhar", "entre agentes", "entre times", "planilha", "memoria"]
revisado_em: "2026-09-24"
fontes: ["docs/CEREBRO-PLANO.md", "PRODUTO.md §9"]
---

# O cérebro da organização

> Os **quadros** já funcionam: os agentes leem e gravam neles, e você vê e edita tudo no menu
> **Cérebro**. **Arquivos** e **Biblioteca** vêm depois.

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
1. No menu à esquerda, abra **Cérebro**. Ele mostra os quadros da organização ativa, cada um com quem
   grava e quem lê. Use a busca e os filtros por time e por agente.
2. **Novo quadro** para criar do zero, ou **Importar planilha** para começar de uma planilha que você já tem.
3. Para um agente usar o quadro, no time dele crie um instrumento do tipo **Quadro**, escolha o quadro e se
   ele só lê ou também grava, e encaixe no agente.

Você também pode pedir à IA que monta o time: "crie um quadro para os agentes deixarem o resultado de cada
rodada".

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
Os **quadros estão prontos para usar** (criar, alterar, importar CSV, dar o instrumento `quadro` aos
agentes), e o consultor os vê e edita no menu **Cérebro**. **Arquivos e Biblioteca ainda não existem** —
não os ofereça.

A pergunta a fazer para decidir onde guardar uma informação é **"quem mais precisa disso, e quando?"**:

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
