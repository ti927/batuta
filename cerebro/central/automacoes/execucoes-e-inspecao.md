---
titulo: "Execuções e inspeção"
area: "automacoes"
slug: "execucoes-e-inspecao"
tags: ["execucao", "inspecao", "rodar", "ao-vivo", "diagnostico", "passo-a-passo",
       "testar", "teste", "um passo"]
revisado_em: "2026-09-03"
fontes: ["PRODUTO.md §15", "cerebro/orquestracao/disparo.py", "cerebro/orquestracao/grafo.py (desenho_que_roda)", "cerebro/diagnostico_execucao.py", "project_navegacao-time-centrica", "feedback_feedback-constante-ao-usuario"]
---

# Execuções e inspeção

## Em uma frase
Uma execução é **uma rodada** de uma automação; a tela de inspeção mostra o fluxo **rodando passo a passo**,
ao vivo.

## Para que serve / quando usar
Para acompanhar e diagnosticar: ver qual agente está trabalhando agora, o que cada passo produziu, onde
parou (esperando uma pessoa) ou por que falhou. Toda operação longa mostra **progresso ao vivo** (cronômetro + "o que
está acontecendo agora") — você nunca fica no escuro achando que travou.

## Como usar (na tela)
1. As execuções vivem **na página do time** (`/times/[id]`) — não há uma página de execuções separada.
2. Dispare uma automação manual pelo **"Rodar agora"**, ou veja as execuções que os gatilhos iniciaram.
3. Abra uma execução para **inspecionar**: os passos, as entradas/saídas, o tempo e o estado.

## Rodar de novo a partir daqui
Quando um fluxo longo morre perto do fim, você não precisa pagar tudo outra vez. Abra o
passo na inspeção e use **"Rodar de novo a partir daqui"**: nasce uma **execução nova**
que começa naquele passo, com a **mesma entrada** que ele recebeu e a **ficha** da
execução original. A execução antiga fica intacta — histórico não se reescreve —, e a
nova diz de quem nasceu.

- Só depois que a execução **parou de andar** (concluída, falhou ou cancelada). Se ela
  ainda está rodando ou esperando uma aprovação, resolva isso primeiro: re-rodar por
  cima duplicaria o trabalho.
- Só a partir de um passo que **de fato rodou** — é dele que sai a entrada. Se o mesmo
  agente rodou duas vezes no mesmo ponto (voltou depois de uma aprovação), vale a última.
- **Repetir um passo repete o que ele faz.** Se o agente daquele passo publica, envia ou
  lança em sistema externo, isso acontece de novo — a tela avisa quais instrumentos dele
  são irreversíveis antes de você confirmar.
- A re-rodada percorre o **desenho da execução original**, mesmo que a automação tenha
  mudado desde então.

## Testar este passo (um agente de cada vez)

Enquanto você desenha um fluxo, dá para experimentar **um passo sozinho**: escreva à mão
o texto que ele receberia e mande rodar. Sem isso, ajustar o 4º passo de um fluxo de 6
custava rodar os 3 anteriores a cada tentativa.

**O teste é real, e essa é a parte que importa.** Ele usa os **instrumentos de verdade**
do agente: testar um passo que publica **publica mesmo**; um que envia, envia. Não existe
modo de mentira aqui — um instrumento que só fingisse enganaria justamente sobre o que o
teste deveria provar. A tela lista os instrumentos irreversíveis daquele agente antes de
você confirmar.

- **Roda um passo e para**, sem seguir as setas. O que vem depois não acontece.
- Aparece nas execuções **marcado como teste** — ele custou dinheiro e agiu no mundo, então
  esconder seria mentir sobre o gasto. E você inspeciona o passo a passo como em qualquer
  execução.
- Se o agente **pedir aprovação** durante o teste, o pedido é enviado de verdade, mas o
  fluxo **não fica esperando**: o teste termina ali e o rastro avisa que, num fluxo de
  verdade, ele pararia. Deixar uma aprovação pendente nascida de um teste seria pedir a
  alguém que decidisse sobre algo que não vai a lugar nenhum.
- **Um teste que falha nunca desliga a automação** — ele fica fora da conta do disjuntor
  (veja [[operacao/falhas-e-retentativa]]). Testar tem de ser seguro.
- É ação de **operador** para cima, e usa o fluxo como está salvo: salve antes de testar um
  passo recém-criado.

## Exemplos
- Acompanhar uma publicação: gera imagem → escreve legenda → **espera aprovação** → publica.
- Investigar por que um fluxo parou: a inspeção mostra o passo e o motivo (em português).
- Um artigo que passou por 4 agentes e morreu no publicador: **rodar de novo a partir do
  publicador**, em vez de refazer a pesquisa, a redação e a revisão.

## Limites e cuidados
- Um fluxo pode ficar **parado esperando uma pessoa** (o agente pediu aprovação) — isso é normal, não é falha.
- Uma execução pode **falhar** e, dependendo do erro, ser **retentada** automaticamente — veja
  [[operacao/falhas-e-retentativa]].
- **Execução "concluída" não garante que tudo deu certo.** Uma ferramenta pode ter respondido "não deu" sem
  derrubar o fluxo; o passo guarda essa falha crua e o diagnóstico a levanta como aviso, mesmo quando o
  agente escreveu que deu certo.
- **As conversas também deixam rastro.** O atendimento por mensageria gera sua própria linha do tempo, com
  os mesmos passos, instrumentos acionados e custo — dá para inspecionar um agente conversacional como se
  inspeciona uma automação.
- **"O passo N não recebeu os dados" tem um lugar próprio de olhar:** o painel
  **"A ficha desta execução"**, na inspeção, mostra tudo o que atravessou o fluxo. Cada passo
  ainda diz o que **guardou na ficha** e quais **regras exatas** o sistema conferiu (com o
  resultado de cada uma). Ver [[automacoes/ficha-da-execucao]].
- **Cada execução roda o desenho que existia quando ela foi disparada.** A automação é
  fotografada no disparo, e é essa foto que o fluxo percorre até o fim — inclusive depois
  de uma pausa para aprovação. Então **editar a automação não mexe no que já está
  rodando**: a mudança vale da próxima execução em diante. Quando o fluxo mudou depois, a
  inspeção diz isso em cima da linha do tempo, para você não comparar o rastro com um
  desenho que não é o que rodou ali. Execuções anteriores a 02/09/2026 não têm foto e
  continuam sendo lidas pelo desenho atual — nelas, esse aviso não aparece.

## Para a IA
Ao diagnosticar com o consultor, baseie-se no **estado real** da execução (o que a inspeção mostra), não em
suposição. E cuidado com uma armadilha nova: a execução guarda o **desenho que rodou**, então ler a
automação de hoje para explicar uma execução de ontem pode explicar a coisa errada — se o fluxo foi
editado no meio, a inspeção avisa, e é a foto que vale.
Quando um fluxo morreu no meio, **não mande refazer tudo**: oriente o consultor a abrir a execução e usar
**"Rodar de novo a partir daqui"** no passo em que parou — e lembre-o de que repetir um passo repete o
que ele faz (se publica, publica de novo). Você **não tem ferramenta** para disparar isso; é ação de tela. Um fluxo "parado" costuma ser um agente aguardando uma aprovação, não um erro.
O diagnóstico já entrega, quando dá para saber: **qual instrumento** falhou (pelo nome que o próprio erro
cita), **qual agente** o carrega e uma **ação sugerida derivada do tipo de erro** — arquivo grande demais
pede ajuste de configuração, não cadastro de credencial. Use essas referências em vez de deduzir pelo
instrumento que aparece por último no passo: o que falhou pode nem ter chegado a registrar passo, se o
agente estourou antes.
Quando o consultor estiver **ajustando um agente** (mexendo no markdown, trocando um instrumento),
lembre-o de **"Testar este passo"** em vez de rodar a automação inteira a cada tentativa — mas sempre com
a ressalva de que os instrumentos são **reais** (testar um passo que publica publica de verdade). Também
é ação de tela: você não tem ferramenta para disparar. Uma execução marcada como **teste** rodou um passo
só de propósito — não a diagnostique como um fluxo que morreu no primeiro passo.

## Relacionado
- [[automacoes/automacao]]
- [[automacoes/ficha-da-execucao]]
- [[automacoes/pedir-aprovacao]]
- [[operacao/falhas-e-retentativa]]
- [[operacao/uso-e-custos]]
