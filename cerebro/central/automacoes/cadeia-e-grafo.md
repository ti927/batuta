---
titulo: "Cadeia e grafo (o construtor do fluxo)"
area: "automacoes"
slug: "cadeia-e-grafo"
tags: ["cadeia", "grafo", "construtor", "no", "bifurcacao", "loop", "fluxo"]
revisado_em: "2026-08-31"
fontes: ["PRODUTO.md §14", "cerebro/orquestracao/cadeia.py", "cerebro/orquestracao/grafo.py"]
---

# Cadeia e grafo (o construtor do fluxo)

## Em uma frase
A cadeia é o **desenho do fluxo** de uma automação: nós (os passos) ligados por setas, montado num
construtor visual.

## Para que serve / quando usar
Para dizer **em que ordem** os agentes trabalham e **para onde** o fluxo segue depois de cada passo. A
orquestração do Batuta é por **bifurcação**: cada saída tem uma condição escrita, e o fluxo segue
**todas as que forem atendidas** — pode ser mais de uma ao mesmo tempo. Não é uma fila reta.
Loops são permitidos (voltar a um passo anterior). Como se escreve cada condição está em
[[automacoes/condicoes-e-ramos]].

## Como usar (na tela)
1. No construtor (tela cheia), o primeiro nó é o **Gatilho**; depois vêm os nós de **agente**.
2. Ligue os nós com setas para definir a ordem; num ponto de decisão, saia para **ramos diferentes**.
3. Em cada saída, escreva a **condição** ("siga por aqui quando…"). Com duas ou mais saídas ela é
   obrigatória.
4. Se algum passo precisar do aval de uma pessoa, dê ao agente dele o instrumento
   **Pedir aprovação e aguardar** ([[automacoes/pedir-aprovacao]]) — não há interruptor
   de aprovação no desenho.
5. Salve — o Batuta valida a cadeia (referências corretas, condições preenchidas, sem becos sem saída).

## Exemplos
- Reta: idealizador → redator → revisor → **pede aprovação** → publica.
- Com bifurcação: um atendente que decide entre "resolver", "escalar para humano" ou "encerrar".
- Em Y: a capa aprovada segue por **duas** saídas de mesma condição, alimentando o gerador de
  carrossel **e** o de story na mesma execução.

## Limites e cuidados
- **Cada nó de agente = uma função.** Se um passo faz coisas demais, quebre em mais nós.
- Um agente que apresenta e depois executa pode fazer as duas coisas no MESMO nó: ele
  pede a aprovação, o fluxo para, e ele continua com a resposta.
- **O dado que um passo precisa não depende do texto do passo anterior.** A entrada do
  gatilho e tudo o que os agentes guardarem com `anotar` viajam na **ficha da execução** e
  chegam a todos os passos — ver [[automacoes/ficha-da-execucao]]. Não escreva na
  documentação do agente "repita os dados no texto final": mande-o **anotar**.
- Além de agente e roteador, há três passos que **não rodam IA** e existem para dirigir o
  fluxo:
  - **"Para cada item"** — repete o trecho seguinte uma vez por item de uma lista da ficha;
  - **"Esperar"** — segura o fluxo por minutos/horas/dias e continua daqui
    ([[automacoes/esperar]]);
  - **"Chamar outra automação"** — roda outra automação inteira e espera o resultado dela
    ([[automacoes/chamar-automacao]]).
- **Cancelar** é embutido (não se desenha uma saída de cancelar).
- **Um nó sem saída ligada encerra o fluxo ali** e a execução mostra um aviso dizendo isso — não
  é um "verde" silencioso.

## Para a IA
Modele por bifurcação, não só linear; loops são válidos. Para publicação, o agente que
apresenta chama `pedir_aprovacao` e, com o sim, publica — não existe mais `gate` no nó.
Confira sempre a cadeia real antes de propor mudanças.
Toda saída de um nó que bifurca precisa de `quando` preenchido, e o fluxo segue **todas** as
condições atendidas — detalhes em [[automacoes/condicoes-e-ramos]] e [[automacoes/erros-no-fluxo]].
Tipos de nó: `gatilho`, `agente`, `roteador`, `fim` e os três estruturais (não rodam IA):
`cada` ("Para cada item"), `esperar` ("Esperar") e `chamar` ("Chamar outra automação").

## Relacionado
- [[automacoes/automacao]]
- [[automacoes/condicoes-e-ramos]]
- [[automacoes/esperar]]
- [[automacoes/chamar-automacao]]
- [[automacoes/ficha-da-execucao]]
- [[automacoes/erros-no-fluxo]]
- [[automacoes/pedir-aprovacao]]
- [[automacoes/execucoes-e-inspecao]]
