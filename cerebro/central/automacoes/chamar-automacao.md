---
titulo: "O passo Chamar outra automação"
area: "automacoes"
slug: "chamar-automacao"
tags: ["chamar", "sub-fluxo", "subfluxo", "outra automação", "reaproveitar", "time chama time", "encadear", "compor"]
revisado_em: "2026-09-04"
fontes: ["cerebro/orquestracao/sub_fluxo.py", "cerebro/orquestracao/cadeia.py", "cerebro/orquestracao/grafo.py"]
---

# O passo Chamar outra automação

## Em uma frase
Um passo que **roda outra automação inteira e espera o resultado dela** para seguir.

## Para que serve / quando usar
Quando um time precisa do trabalho de outro **e precisa usar o que ele produziu**:

- o time de conteúdo chama o time de revisão e **usa o parecer** para decidir se publica;
- o time comercial chama o time financeiro para simular um valor e **segue com o número**;
- uma automação longa é quebrada em pedaços reaproveitáveis, cada um com vida própria.

Antes deste passo, a única forma de uma automação acionar outra era o instrumento
**Agendar automação** — que é *fogo-e-esquece*: ele dispara e a execução que chamou segue em
frente sem nunca saber o que aconteceu do outro lado. Dava para pedir o trabalho; não dava
para receber a resposta.

## Como usar (na tela)
1. No construtor, adicione o passo **Chamar outra automação**.
2. Em **Automação a chamar**, escolha qual automação da organização roda aqui (pode ser de
   outro time).
3. Ligue a saída dele ao passo que deve receber o resultado.
4. Se quiser tratar a falha da automação chamada, desenhe também uma saída
   **"Se der erro"**.

## O que vai e o que volta
- **Vai:** a ficha da execução atual e o texto do passo anterior. A automação chamada
  começa sabendo tudo o que o chamador sabia.
- **Volta:** o texto final dela vira a **entrada do próximo passo**, e a ficha dela é
  mesclada **por cima** da do chamador — como ela partiu de uma cópia, toda diferença é
  trabalho que ela fez.

## Exemplos
- Redator → **Chamar "Revisão de SEO"** → Publicador (que recebe o parecer da revisão).
- Atendimento → **Chamar "Simulação de crédito"** → Agente que responde com o valor.

## Limites e cuidados
- **A execução inteira espera.** Se o fluxo tinha outros caminhos abertos, todos param e
  voltam juntos.
- **Se a automação chamada parar para pedir aprovação, o chamador continua parado** até
  alguém responder lá. É o comportamento correto — e não há nada a configurar para isso.
- Enquanto espera, a execução aparece como **"rodando outra automação"**. Não pede nada de
  você. Abra o passo para ver o rastro da execução chamada.
- **Se a automação chamada falhar**, o chamador segue pela saída "Se der erro", se houver.
  **Sem essa saída, o chamador falha junto** — seguir adiante com um resultado que não
  existe entregaria trabalho pela metade narrado como inteiro.
- **Sem automação escolhida, o fluxo não salva.** Diferente do passo *Esperar* sem tempo
  (que apenas segue avisando): uma chamada sem alvo é trabalho que **não seria feito**, e o
  passo seguinte receberia uma entrada vazia como se estivesse tudo certo.
- **Máximo de 3 automações encadeadas**, e nenhuma pode chamar outra que já esteja rodando
  mais acima na mesma corrente — A→B→A rodaria para sempre, gastando dinheiro a cada volta.
- **O que o sub-fluxo gasta conta nos tetos** de custo e de tempo do chamador. Sem isso,
  bastaria pôr o trabalho caro numa automação chamada para o limite virar enfeite.
- **Reiniciar o Batuta não perde a espera:** ela vive no banco, não na memória do servidor.
- A automação chamada roda **de verdade**: aciona instrumentos, publica, cobra. Ela não
  sabe que foi chamada por outra — para ela é uma execução como qualquer outra.

## Para a IA
Tipo de nó `chamar`, com `chamar: {automacao_id}`. Estrutural: não roda agente e não
consome IA por si — mas **deixa passo no rastro** (`tipo: "sub_fluxo"`), com o elo para a
execução-filha, porque um passo que demorou oito minutos precisa poder ser inspecionado.

O alvo é fixado pelo **humano**, nunca escolhido pelo agente em tempo de execução — mesma
regra do instrumento `agendar_automacao`, e pela mesma razão: agente que escolhe alvo pode
apontar para o lugar errado.

Proponha este passo quando o consultor disser "aí passa pelo time X", "manda para a revisão
e usa o parecer". **Não** proponha `agendar_automacao` para isso: aquilo dispara e não
recebe resposta. Agendar continua certo quando o que se quer é um fluxo **novo**, no futuro,
com entrada própria e sem retorno.

Ao diagnosticar: `aguardando_sub_fluxo` **não é** travamento nem pendência de ninguém — é a
espera pela automação chamada. A execução chamada carrega `chamada_por_execucao_id` e a
origem `sub_fluxo`; falha dela **não conta** para o disjuntor da automação chamada, porque
quem rodou foi o chamador.

## Relacionado
- [[automacoes/cadeia-e-grafo]]
- [[automacoes/esperar]]
- [[automacoes/erros-no-fluxo]]
- [[automacoes/ficha-da-execucao]]
- [[instrumentos/agendar-automacao]]
- [[operacao/falhas-e-retentativa]]
