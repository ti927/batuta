---
titulo: "Uso e custos"
area: "operacao"
slug: "uso-e-custos"
tags: ["uso", "custo", "medicao", "categoria", "origem", "provedor", "consumo",
       "teto", "limite de gastos", "orcamento"]
revisado_em: "2026-09-03"
fontes: ["cerebro/precos.py", "cerebro/medicao_instrumentos.py",
         "cerebro/orquestracao/cadeia.py", "cerebro/mensageria/config.py"]
---

# Uso e custos

## Em uma frase
O Batuta **mede** o consumo de IA e de instrumentos pagos, por categoria e origem — e, **se você pedir**,
também **para** uma execução que passar de um teto em dólares.

## Para que serve / quando usar
Para enxergar quanto um time (ou a organização) está consumindo: chamadas de IA dos agentes, a IA de
conversa, geração de imagem/vídeo, mensageria, transcrição de áudio.

A medição em si é **informativa** (é estimativa, não a fatura do provedor) e por si só não corta nada. O
que corta é o **teto de custo por execução**, abaixo — e ele nasce **desligado**.

## Como usar (na tela)
1. O **resumo de uso** aparece por organização e a página do time mostra o **custo acumulado** daquele time.
2. O consumo é quebrado por **categoria** e **origem/provedor**, então você vê de onde vem o gasto (agentes,
   mensageria, Whisper, imagem…).
3. A consultoria tem uma visão própria do que passou pela **chave-mãe** (fallback).

## O teto de custo por execução

Em **Fluxo › Limites da execução** você define quanto uma execução daquela automação pode gastar, em
dólares. Passou do teto, ela **para** — com um recado que diz quanto gastou, qual era o teto e o que fazer.

- **Nasce desligado** (`0` = sem teto). É opcional de propósito: um teto ligado sem você pedir
  interromperia fluxos legitimamente caros — gerar vídeo, um "Para cada item" com 20 itens — como se
  fossem defeito.
- **Vale por execução, não por passo**, e **atravessa a aprovação**: o que foi gasto antes de a execução
  parar para alguém aprovar continua contando depois. Sem isso, uma execução que espera duas vezes gastaria
  o teto três vezes.
- **O passo que estourou fica no rastro.** O trabalho já foi pago; escondê-lo faria a conta não fechar
  na aba Uso.
- **A execução fica como `falhou`**, então ela conta para o disjuntor: uma automação que estoura o teto
  três vezes seguidas rodando sozinha é desligada (veja [[operacao/falhas-e-retentativa]]). É o
  comportamento desejado — ou o teto está baixo demais, ou o fluxo disparou em custo; nos dois casos
  alguém precisa olhar.

Escolher o número: veja na aba **Uso** quanto uma execução saudável daquele fluxo costuma custar e deixe
uma folga. Teto colado no custo real transforma qualquer variação (um artigo mais longo, uma retentativa)
em falha.

## Exemplos
- Ver que a maior parte do custo de um time veio de geração de vídeo, e ajustar a duração dos clipes.
- Pôr um teto de US$ 1 num fluxo que costuma custar US$ 0,20 — assim um laço inesperado para em vez de
  gastar até o teto de passos.

## Limites e cuidados
- É **estimativa informativa** de custo, com base nos preços por provedor — não é a fatura oficial do
  provedor.
- Vídeo é medido **por segundo**; imagem, **por imagem**; IA, por tokens. Clipes longos e qualidade alta
  pesam mais.

## Para a IA
Não prometa "custo zero". Se o consultor quer economizar, aponte os ajustes reais: duração/qualidade de
mídia, recência/profundidade de busca, modelo de IA mais barato. Num fluxo que consulta APIs que devolvem
listas grandes (CRM, Bubble, ERP), o maior gasto costuma ser a **resposta gorda reenviada a cada passo** —
filtre com `campos_resposta` no [[instrumentos/chamar-rest]] para trazer só os campos usados (corte típico
de tokens grande). O uso é medido por categoria/origem.

Quando uma execução falhar com **"passou do teto de custo do fluxo"**, não trate como bug: foi uma regra
que o consultor ligou, funcionando. Diga quanto gastou e qual era o teto, e ofereça as duas saídas
honestas — subir o teto (se o fluxo é caro por natureza) ou achar o passo caro na aba Uso. O teto vive na
config do fluxo (`teto_usd_execucao`, `0` = desligado), na mesma cascata dos outros limites
(global < perfil < ajustes).

## Relacionado
- [[segredos/chaves-de-ia]]
- [[automacoes/execucoes-e-inspecao]]
- [[operacao/falhas-e-retentativa]]
