---
titulo: "Condições e ramos (como o fluxo escolhe o caminho)"
area: "automacoes"
slug: "condicoes-e-ramos"
tags: ["condicao", "quando", "bifurcacao", "ramo", "fan-out", "grafo", "saida", "seta"]
revisado_em: "2026-08-31"
fontes: ["PRODUTO.md §14", "cerebro/orquestracao/cadeia.py", "cerebro/orquestracao/grafo.py"]
---

# Condições e ramos (como o fluxo escolhe o caminho)

## Em uma frase
Cada seta que sai de um passo carrega uma **condição escrita**, e o fluxo segue **todas** as
setas cuja condição for atendida.

## Para que serve / quando usar
Para o fluxo se ramificar de verdade. Um passo pode terminar de três jeitos e cada jeito
seguir para um lugar diferente — ou o mesmo resultado alimentar **dois** passos ao mesmo
tempo (a mesma capa aprovada indo para o carrossel **e** para o story).

## Como usar (na tela)
1. No construtor, clique no passo e abra **Saídas**.
2. Em cada saída preencha:
   - **Nome (aparece na seta)** — o rótulo curto: "aprovado", "refazer".
   - **Siga por aqui quando…** — a **condição**. É esta frase que o agente lê para decidir.
   - **vai para** — o passo de destino.
3. Com duas ou mais saídas, a condição é **obrigatória**: sem ela a automação não salva.
4. Para fazer duas coisas ao mesmo tempo, crie **duas saídas com a mesma condição** e
   destinos diferentes.

## Exemplos
- Triagem: "é urgente" → Atendimento imediato · "é rotina" → Fila normal.
- Duas de uma vez: "a capa foi aprovada" → Gerador de carrossel **e** "a capa foi
  aprovada" → Gerador de story. As duas rodam.
- Volta atrás: "pediram ajuste" → volta para o redator (loop).

## Limites e cuidados
- **O nome da seta não é a condição.** O nome é para você ler no desenho; a condição é o
  que o agente lê. Um rótulo sozinho ("aprovado1", "aprovado2") não diz nada a ele.
- **Se nada casar, aquele ramo termina ali** e o motivo aparece na execução. O fluxo nunca
  mais escolhe um caminho no escuro. Para tratar esse caso, use a saída
  **"Se nenhuma"** — ver [[automacoes/erros-no-fluxo]].
- **Dois ramos que se reencontram no mesmo passo:** ele roda **uma vez só**, recebendo os
  textos dos dois. Não há risco de publicar em dobro e não é preciso desenhar nada para
  juntá-los.
- Escreva a condição do ponto de vista do **resultado daquele passo**, não do passo
  seguinte: "o texto foi aprovado", não "publicar no blog".
- **Decisão numérica não é caso para frase.** Quando o caminho depende de um número ou de
  uma correspondência exata (faixa de valor, campo preenchido), use a **regra exata** da
  saída: quem confere é o sistema, e a borda fica certa. Ver
  [[automacoes/ficha-da-execucao]].

## Para a IA
Cada saída é `{"rotulo", "quando", "tipo", "destino"}`. O `quando` é **obrigatório** quando
o nó tem 2+ saídas condicionais — `validar_cadeia` recusa a cadeia sem ele, com mensagem
apontando o passo e as saídas em falta.

O motor faz **fan-out**: o agente declara pela ferramenta `seguir_para` uma **lista** de
rótulos, e o fluxo percorre todos. Duas saídas com a mesma condição e destinos diferentes
é a forma canônica de "faça os dois" — não monte um agente-multiplicador nem encadeie um
destino após o outro para conseguir isso.

Se o agente não declarar caminho nenhum (modelo que ignorou a ferramenta, automação
antiga), uma LLM roteadora lê as condições e devolve as que se aplicam; pode devolver
nenhuma, e nesse caso vale a saída "senão", ou o ramo termina com aviso no rastro.

Ao propor uma cadeia, escreva sempre a condição de cada seta em português direto. Ao
diagnosticar "o fluxo só seguiu um caminho", confira primeiro se as condições estão
preenchidas: automações criadas antes de 2026-08-31 têm todas vazias.

## Relacionado
- [[automacoes/cadeia-e-grafo]]
- [[automacoes/ficha-da-execucao]]
- [[automacoes/erros-no-fluxo]]
- [[automacoes/execucoes-e-inspecao]]
- [[automacoes/pedir-aprovacao]]
