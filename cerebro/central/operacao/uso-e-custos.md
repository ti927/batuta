---
titulo: "Uso e custos"
area: "operacao"
slug: "uso-e-custos"
tags: ["uso", "custo", "medicao", "categoria", "origem", "provedor", "consumo"]
revisado_em: "2026-07-17"
fontes: ["cerebro/precos.py", "cerebro/medicao_instrumentos.py", "project_estado-atual-build-plan"]
---

# Uso e custos

## Em uma frase
O Batuta **mede** (de forma informativa) o consumo de IA e de instrumentos pagos, por categoria e origem —
para você acompanhar o custo, não para bloquear.

## Para que serve / quando usar
Para enxergar quanto um time (ou a organização) está consumindo: chamadas de IA dos agentes, a IA de
conversa, geração de imagem/vídeo, mensageria, transcrição de áudio. A medição é **informativa** — ela
mostra, não corta o fluxo.

## Como usar (na tela)
1. O **resumo de uso** aparece por organização e a página do time mostra o **custo acumulado** daquele time.
2. O consumo é quebrado por **categoria** e **origem/provedor**, então você vê de onde vem o gasto (agentes,
   mensageria, Whisper, imagem…).
3. A consultoria tem uma visão própria do que passou pela **chave-mãe** (fallback).

## Exemplos
- Ver que a maior parte do custo de um time veio de geração de vídeo, e ajustar a duração dos clipes.

## Limites e cuidados
- É **estimativa informativa** de custo, com base nos preços por provedor — não é a fatura oficial do
  provedor.
- Vídeo é medido **por segundo**; imagem, **por imagem**; IA, por tokens. Clipes longos e qualidade alta
  pesam mais.

## Para a IA
Não prometa "custo zero". Se o consultor quer economizar, aponte os ajustes reais: duração/qualidade de
mídia, recência/profundidade de busca, modelo de IA mais barato. O uso é medido por categoria/origem.

## Relacionado
- [[segredos/chaves-de-ia]]
- [[automacoes/execucoes-e-inspecao]]
