---
titulo: "O agente lendo e gravando num quadro"
area: "cerebro"
slug: "instrumento-quadro"
tags: ["quadro", "instrumento", "gravar", "ler", "consultar", "agente", "compartilhar", "entre times", "cerebro", "carimbo"]
revisado_em: "2026-09-24"
fontes: ["cerebro/instrumentos/quadro.py", "cerebro/quadros/servico.py", "docs/CEREBRO-PLANO.md §5.3"]
---

# O agente lendo e gravando num quadro

## Em uma frase
Para um agente ler ou gravar num quadro, ele precisa de um instrumento **Quadro** no cinto, apontando para
aquele quadro, com acesso de **leitura** ou de **leitura e escrita**.

## Para que serve / quando usar
É assim que a informação passa de um agente para outro: quem produz grava, quem precisa lê. Os dois podem
estar em times diferentes e rodar em dias diferentes. Como cada agente só enxerga o quadro se tiver o
instrumento, dá para saber exatamente quem usa cada quadro.

## Como usar (na tela)
1. No time, aba **Instrumentos** › novo instrumento do tipo **Quadro**.
2. Escolha o quadro na lista (ela mostra as colunas e quem já usa) e se o agente **só lê** ou **lê e grava**.
3. Encaixe o instrumento no agente.

Ou peça à IA que monta o time: "dê ao Coletor acesso de escrita ao quadro Painel – semanas, e ao Briefing só
de leitura".

## Exemplos
- O agente do Radar grava uma linha por pergunta de cada rodada. O agente do Briefing lê só as lacunas da
  rodada mais recente.
- O Briefing grava uma linha por tema, substituindo a da semana anterior. Os analistas de cada blog leem só
  a linha do seu tema.

## O que o agente consegue fazer
Com acesso de **leitura**:
- **consultar** linhas, com filtro, ordem e "só a mais recente de";
- **totais**: contar, somar, média, menor, maior — calculados pelo Batuta;
- **já existe?**: quais destes valores já estão gravados.

Com acesso de **leitura e escrita**, também:
- **acrescentar** linhas;
- **gravar pela chave** (cria ou substitui a linha daquele tema, cliente, semana…);
- **atualizar** colunas das linhas achadas por um filtro.

Apagar linhas não está entre as ações do agente: isso é feito por uma pessoa.

## Limites e cuidados
- O agente já recebe as colunas e os tipos do quadro. **Não escreva no texto do agente como formatar data,
  número ou célula** — o quadro recusa o que não serve e diz o que corrigir.
- Se alguma linha tiver problema, **nada** é gravado. O agente recebe o motivo e pode corrigir.
- Toda linha fica marcada com o agente e a execução que a gravou. O que o agente diz na resposta não é
  prova de que gravou; o diagnóstico da execução mostra o que ficou gravado de fato.
- Gravar num quadro não pede aprovação: tudo fica no histórico e dá para desfazer.
- Um instrumento só alcança quadros da própria organização.

## Para a IA
- Crie com `configurar_instrumento`, tipo `quadro`, configuração `{"quadro": "<nome>", "acesso": "ler" |
  "ler_e_escrever"}`. O Batuta confere na hora se o quadro existe na organização e guarda o id dele
  (renomear o quadro depois não quebra nada). **Um instrumento por quadro.**
- Dê **escrita** só a quem produz a informação; a quem consome, **leitura**.
- No markdown do agente, diga **o que** gravar ou ler e **quando** ("ao fim da rodada, grave uma linha por
  pergunta"; "antes de escolher a pauta, consulte a linha do seu tema"). Para "o que falta coletar", mande
  usar **já existe?**; para números, **totais**.
- Se o quadro sumir ou o instrumento apontar para um quadro que não existe, o instrumento sai do cinto
  naquele passo, com aviso registrado — o passo segue com os outros instrumentos.

## Relacionado
- [[cerebro/quadros]]
- [[cerebro/o-que-e-o-cerebro]]
- [[instrumentos/cinto]]
