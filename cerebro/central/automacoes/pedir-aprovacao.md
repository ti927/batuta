---
titulo: "Pedir aprovação e aguardar"
area: "automacoes"
slug: "pedir-aprovacao"
tags: ["aprovacao", "aprovar", "esperar", "humano", "instrumento", "pausa", "confirmar"]
revisado_em: "2026-09-21"
fontes: ["cerebro/instrumentos/pedir_aprovacao.py", "cerebro/mensageria/retoma.py", "cerebro/orquestracao/dono.py", "cerebro/orquestracao/espera.py", "PRODUTO.md §19", "docs/FALHAS-DO-MOTOR.md"]
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

### Vindo de um time que pedia aprovação "na mão"
Antes do instrumento, muita gente resolvia assim: o agente mandava o material pelo **canal
de Telegram comum** e o texto dele dizia *"espere o #aprovado#"*. Isso **não para nada** —
quem para a execução é o instrumento de aprovação, e só ele.

Ao converter um agente desses, **apague a instrução velha**. Ela costuma estar no
**`tools.md`** (o texto do cinto), enquanto a regra nova é escrita no `skill.md` — e com as
duas no mesmo agente ele obedece a velha, que é mais específica. O resultado é silencioso e
enganoso: a mensagem chega ao Telegram como sempre, a pessoa responde, e **nada acontece**,
porque a execução já terminou sem esperar. Foi exatamente o que aconteceu em 2026-09-02, no
primeiro disparo agendado depois de o portão deixar de existir.

Checklist da conversão: (1) instrumento de aprovação criado e **no cinto** do agente;
(2) regra escrita no `skill.md`; (3) instrução antiga **removida** dos outros markdowns;
(4) sem instrumento de aprovação duplicado no cinto — dois com o mesmo papel confundem
a escolha.

## Depois que a pessoa responde, o agente precisa DIZER por onde seguir
Esta é a parte que mais dá problema, e vale ler com calma.

Quando a aprovação chega, o Batuta religa o **mesmo agente**. Ele continua de onde parou —
mas o fluxo **só anda** se ele declarar por qual caminho seguir. Se ele conversar, refizer
o material, publicar e não declarar nada, a execução fica **parada naquele ponto para
sempre**, mesmo com tudo aprovado e feito.

Por isso, no `skill.md` do agente que pede aprovação, escreva o que ele faz **depois da
decisão**, citando os **nomes exatos das saídas** daquele passo. Por exemplo:

> *"Quando a pessoa APROVAR, a última coisa que você faz é declarar o caminho `aprovado`.
> Sem isso o fluxo não anda."*

Se o passo alimenta **dois** caminhos ao mesmo tempo (a capa aprovada indo para o carrossel
**e** para o story), diga para declarar **os dois** — declarar só um deixa metade do
trabalho sem acontecer.

**Como o Batuta te avisa quando isso está errado:** se o passo tem caminhos a escolher e o
agente conversa duas vezes seguidas sem decidir nada, entra um alarme nos registros
(`portao.indeciso`) dizendo o nome do agente e os nomes das saídas que ele ignorou. É quase
sempre o mesmo diagnóstico: **o markdown dele não conhece as saídas do passo.**

## Exemplos
- Redator escreve → **pede aprovação** com o texto completo → aprovado → publica.
- Atendente monta um lançamento no sistema do cliente → **pede aprovação** com os valores
  → confirmado → lança.

## Limites e cuidados
- **A mensagem é o que a pessoa aprova.** Passe nela tudo o que ela precisa para decidir
  (o texto, o link da imagem, os valores). Não escreva "posso publicar?" e deixe o
  conteúdo de fora — foi assim que aprovações viraram carimbo no escuro.
- **Se o agente não chamar o instrumento, o fluxo NÃO para.** A garantia mora no
  instrumento, não no desenho da automação — é a contrapartida de a aprovação ser do
  agente. Por isso a regra precisa estar escrita com clareza e **sem concorrente** nos
  markdowns dele. Como conferir depois: no rastro do passo, o instrumento de aprovação tem
  de aparecer entre os acionados; se aparecer o canal de mensageria no lugar dele, foi
  texto do agente, não defeito do motor.
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
- **Uma aprovação tem um teto de idas-e-vindas** (*Máx. de idas-e-vindas na aprovação*,
  8 por padrão). Enquanto ele não estoura, reprovar com um pedido de ajuste faz o agente
  refazer o material quantas vezes forem precisas. Ao estourar, o agente **diz o que
  aconteceu** e a sua resposta segue direto pelo caminho que ela indicar — o fluxo anda,
  o canal continua funcionando, e o material inteiro continua visível no Batuta.
- **Gerar imagem ou vídeo não consome o teto de custo da CONVERSA.** São contas
  diferentes de propósito: o teto da conversa vigia a IA que conversa; o trabalho pesado
  é do fluxo e responde ao *Teto de custo por execução*. Sem essa separação, um carrossel
  de três imagens estourava sozinho o teto de uma conversa inteira na primeira
  reprovação.
- **Uma porta de cada vez.** A mesma aprovação pode ser respondida na **tela** ou pelo
  **canal**, e as duas conversam com a mesma execução. Enquanto uma está processando, a
  outra é recusada com um aviso claro ("esta aprovação está sendo respondida pelo Telegram
  neste momento") — na tela os botões ficam travados até o outro turno terminar, e a página
  se atualiza sozinha. **Nada se perde:** a mensagem recusada continua na conversa e pode
  ser reenviada. Isso existe porque responder pelos dois lugares ao mesmo tempo corrompia
  a memória do agente e derrubava a execução inteira (21/09/2026).
- **Uma espera esquecida deixa de ser invisível.** Toda espera por aprovação tem prazo
  próprio (*Tempo parada até avisar que ninguém aprovou*, 24 h por padrão, 0 = nunca
  avisar). Ao vencer, o time recebe **um** aviso dizendo há quanto tempo aquilo está
  parado. Ele **não encerra nada** — esperar dias por uma aprovação é legítimo; o que não
  era legítimo é ninguém ficar sabendo. Antes disso, uma aprovação pedida só pela tela
  (sem canal) não era varrida por vigia nenhum e podia ficar parada meses em silêncio.
- **Um pedido de aprovação novo devolve a conversa ao bot.** Se o canal tinha sido
  passado para uma pessoa automaticamente e ninguém assumiu, o Batuta volta a ler as
  respostas — em vez de continuar pedindo aprovação por um canal em que não escuta.

## Para a IA
Tipo `pedir_aprovacao`. Config: `canal_instrumento_id` (id de um instrumento de
mensageria do MESMO time; vazio = só pela tela). Args: `mensagem` — é o texto
apresentado, e é ele que segue adiante como "o aprovado".

No motor, o instrumento tem `pausa_para_humano = True`: ao ser acionado com sucesso, o
turno do agente termina numa espera, a execução vira `aguardando_humano` e o passo é
gravado como `espera_humano`, carregando o canal e o destinatário. A resposta religa o
MESMO agente, que continua de onde parou (memória por `execucao:nó`) e então declara os
caminhos com `seguir_para`.

A execução tem **dono** enquanto alguém mexe nela (`execucoes.dono` = `tela` | `canal` |
`fila`, com `dono_ate` como prazo). Quem chega segundo recebe recusa honesta: a rota
`POST /execucoes/{id}/responder` devolve 409 com a frase pronta, e o turno por canal manda
um recado e não processa. É o que impede dois processos de abrirem o mesmo fio de memória
do agente (`{execucao}:{nó}` no checkpointer) e bifurcarem o checkpoint.

A espera carrega `espera_ate`; o vigia `esperas_humanas` avisa uma vez e zera o campo, sem
mudar o estado. Reprovação que vem **com** o feedback não deve gerar uma pergunta de volta:
oriente o agente a usar o que a pessoa já disse.

Ao montar um time: **não desenhe portão** (não existe mais) e **não exija aprovação para
leitura** — só para o que muda o mundo. Ponha o instrumento no cinto de quem apresenta,
não no de quem publica, e escreva a regra no markdown do agente — **inclusive o que ele
declara depois da decisão, com os rótulos exatos das saídas daquele nó**. Markdown que não
cita os rótulos é a causa nº 1 de fluxo que para depois de aprovado.

## Relacionado
- [[automacoes/condicoes-e-ramos]]
- [[automacoes/erros-no-fluxo]]
- [[instrumentos/cinto]]
- [[mensageria/canal-telegram]]
