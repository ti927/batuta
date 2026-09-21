---
titulo: "Quando um passo dá erro"
area: "automacoes"
slug: "erros-no-fluxo"
tags: ["erro", "falha", "senao", "fallback", "aviso", "resiliencia", "saida"]
revisado_em: "2026-09-21"
fontes: ["cerebro/orquestracao/cadeia.py", "cerebro/mensageria/aviso.py", "PRODUTO.md §16"]
---

# Quando um passo dá erro

## Em uma frase
Um passo que falha pode **seguir por uma seta de erro** em vez de derrubar a automação — e,
quando não há para onde seguir, a falha é registrada **e avisada**, nunca silenciosa.

## Para que serve / quando usar
Fluxo real quebra: um site fora do ar, uma API que recusa, uma chave vencida. Desenhe a
saída de erro sempre que a falha daquele passo merecer um tratamento — avisar alguém,
tentar por outro caminho, registrar o ocorrido.

## Como usar (na tela)
1. No passo, adicione uma saída e escolha o papel **"Se der erro"**.
2. Aponte-a para quem trata a falha (por exemplo, um agente que avisa o responsável).
3. A seta fica **vermelha** no desenho — a cor vem do papel, não é escolha de cor.
4. Para o caso "nenhuma condição casou", adicione uma saída com o papel **"Se nenhuma"**.

## Exemplos
- Publicador com saída "Se der erro" → agente "Avisar responsável", que manda um Telegram
  com o motivo em vez de a automação morrer calada.
- Triagem com três condições e uma saída "Se nenhuma" → agente de tratamento padrão.

## Limites e cuidados
- **O passo que falhou fica gravado** na linha do tempo da execução, com o nó, a entrada e
  o erro. Antes a timeline pulava do último passo bom direto para "falhou".
- **Sem saída de erro, a execução falha** — como sempre foi. A diferença é que agora ela
  **avisa** pelo canal do time (Telegram) dizendo o que quebrou, em qual passo e o que
  fazer. Se o time não tem canal com destinatário configurado, isso vira um alerta no
  registro de eventos.
- **Falha devolvida como resposta também é falha** — mas o que acontece depois depende do
  instrumento. Se ele faz algo **irreversível** (publicar, lançar, enviar) e responde "não
  deu certo", o turno para ali: nada mais roda naquele passo, porque a ação não aconteceu
  e seguir em frente seria trabalhar sobre um resultado que não existe. Se ele é de
  **leitura ou geração**, o fluxo segue — o agente recebe a falha como dado e decide —, e
  desde 2026-09-21 o passo carrega um **aviso** dizendo que um instrumento respondeu falha
  e nomeando qual. Nos dois casos vale a mesma regra: **o texto do agente nunca é prova de
  que a ação aconteceu.**
- **O fluxo não desvia sozinho para a saída de erro por causa de um `ok: false` de
  leitura.** É de propósito: o agente pode ter tentado de novo e conseguido, e desviar à
  força inventaria uma falha que talvez não exista. O que mudou foi a **visibilidade**, não
  o caminho.
- **Estourar o máximo de passos diz onde.** A mensagem nomeia o passo que está girando e
  quantas voltas deu — é quase sempre uma seta voltando para ele sem condição que feche o
  ciclo. Antes dizia só "possível laço infinito", que não ajudava a achar o nó.
- **A saída de erro não repete o passo.** Ela é um caminho, não uma retentativa; para
  tentar de novo, aponte-a para um passo que tente por outro meio.
- **Falhar sozinha 3 vezes seguidas desliga a automação.** Quando ela dispara por conta
  própria (agendamento, webhook, comentário), a terceira falha seguida tira a automação do
  ar e avisa pelo canal do time — para não repetir o erro todo dia. Disparo manual não
  conta. Ver [[operacao/falhas-e-retentativa]].

## Para a IA
Papéis de saída (`saidas[].tipo`): `condicional` (padrão), `erro`, `senao`. As de erro e
"senão" **não levam `quando`** — quem as aciona é o motor, não o agente, e por isso elas
não entram na lista que o agente vê em `seguir_para`.

Quando o nó levanta exceção: o motor grava o passo com `estado="falhou"` e, se houver
saída de erro, encaminha por ela um texto com o erro e a entrada original. Sem saída de
erro, propaga — a execução fica `falhou`, o evento vai ao banco de logs e
`mensageria/aviso.avisar_falha` manda o recado pelo canal do time.

Ao montar uma automação com publicação, ofereça a saída de erro ao consultor: é barata e
transforma uma quebra muda num aviso acionável.

## Relacionado
- [[automacoes/condicoes-e-ramos]]
- [[automacoes/execucoes-e-inspecao]]
- [[operacao/falhas-e-retentativa]]
- [[operacao/sinais-e-diagnostico]]
