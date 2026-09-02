---
titulo: "Pedir aprovação e aguardar"
area: "automacoes"
slug: "pedir-aprovacao"
tags: ["aprovacao", "aprovar", "esperar", "humano", "instrumento", "pausa", "confirmar"]
revisado_em: "2026-08-31"
fontes: ["cerebro/instrumentos/pedir_aprovacao.py", "cerebro/mensageria/retoma.py", "PRODUTO.md §19"]
---

# Pedir aprovação e aguardar

## Em uma frase
Um **instrumento** do cinto: o agente apresenta algo a uma pessoa, o trabalho **para**, e
ele continua quando ela responde.

## Para que serve / quando usar
Para segurar o que não dá para desfazer — publicar, enviar, lançar num sistema — até
alguém confirmar. Quem decide que aquele momento precisa de gente é o **agente**, porque
a documentação dele manda; não existe mais um interruptor no desenho da automação.

## Como usar (na tela)
1. Em **Instrumentos**, crie um do tipo **Pedir aprovação e aguardar**.
2. Em **Canal do pedido**, escolha por onde a pessoa recebe (um bot do Telegram do time).
   Quem responde é o **destinatário configurado nesse canal**. Deixe em branco para
   aprovar só pela tela da execução.
3. Pendure o instrumento no cinto do agente que precisa esperar.
4. Escreva no **skill.md** dele quando usar — ex.: *"antes de publicar, chame Pedir
   aprovação e aguardar com a arte e a legenda prontas; só publique depois do sim"*.

### Onde se diz PARA QUEM o pedido vai
No instrumento do **canal**, não no de aprovação. O "Pedir aprovação e aguardar" tem uma
configuração só — **Canal do pedido** —, e o destino vem do campo **Destinatário** do
canal escolhido.

É de propósito, e conserta um erro antigo: quando o destinatário era um campo separado, os
dois divergiam — o pedido ia para um chat e o sistema esperava a resposta em outro, e a
execução ficava órfã. Agora vale uma regra só: **quem recebe é quem aprova.**

- **Dois instrumentos precisam existir no time** (o de aprovação e o canal), mas **só o de
  aprovação vai no cinto** do agente. O canal é referenciado, não encaixado — assim o
  token do bot continua morando num lugar só.
- **Não sabe o chat_id?** Mande qualquer mensagem ao bot e abra **Time → Conversas**: o id
  aparece no cabeçalho da conversa. A pessoa precisa ter dado **/start** no bot antes;
  sem isso o Telegram recusa e o instrumento diz exatamente isso.
- **Aprovador diferente de quem o canal já atende?** Crie um **segundo** instrumento de
  Telegram (pode apontar para a mesma credencial, sem recolar o token) com outro
  Destinatário, e aponte a aprovação para ele. Um canal = um destino.

## Exemplos
- Redator escreve → **pede aprovação** com o texto completo → aprovado → publica.
- Atendente monta um lançamento no sistema do cliente → **pede aprovação** com os valores
  → confirmado → lança.

## Limites e cuidados
- **A mensagem é o que a pessoa aprova.** Passe nela tudo o que ela precisa para decidir
  (o texto, o link da imagem, os valores). Não escreva "posso publicar?" e deixe o
  conteúdo de fora — foi assim que aprovações viraram carimbo no escuro.
- **Depois de pedir, o agente não faz mais nada** naquele turno. É o Batuta que garante
  isso: qualquer outra ação é recusada até a resposta chegar.
- **Sem destinatário no canal, o pedido falha na hora** — e com razão: não haveria para
  quem mandar nem de quem esperar. O erro diz exatamente isso.
- **Se o pedido não for entregue, a execução falha** em vez de esperar para sempre.
- **A pessoa pode cancelar** (botão na tela, ou responder "cancelar" pelo canal). Você não
  desenha uma saída de cancelar.
- Quem não responde não trava o fluxo para sempre: o **Tipo de fluxo** define quanto
  esperar e o que fazer no silêncio (estacionar ou cancelar), e dá para ajustar isso só
  num passo, no construtor.

## Para a IA
Tipo `pedir_aprovacao`. Config: `canal_instrumento_id` (id de um instrumento de
mensageria do MESMO time; vazio = só pela tela). Args: `mensagem` — é o texto
apresentado, e é ele que segue adiante como "o aprovado".

No motor, o instrumento tem `pausa_para_humano = True`: ao ser acionado com sucesso, o
turno do agente termina numa espera, a execução vira `aguardando_humano` e o passo é
gravado como `espera_humano`, carregando o canal e o destinatário. A resposta religa o
MESMO agente, que continua de onde parou (memória por `execucao:nó`) e então declara os
caminhos com `seguir_para`.

Ao montar um time: **não desenhe portão** (não existe mais) e **não exija aprovação para
leitura** — só para o que muda o mundo. Ponha o instrumento no cinto de quem apresenta,
não no de quem publica, e escreva a regra no markdown do agente.

## Relacionado
- [[automacoes/condicoes-e-ramos]]
- [[automacoes/erros-no-fluxo]]
- [[instrumentos/cinto]]
- [[mensageria/canal-telegram]]
