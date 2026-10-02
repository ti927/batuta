---
titulo: "Chaves de IA"
area: "segredos"
slug: "chaves-de-ia"
tags: ["chave", "ia", "openai", "anthropic", "google", "provedor", "pool", "consultoria", "custo"]
revisado_em: "2026-10-02"
fontes: ["PRODUTO.md §24-26", "cerebro/chaves.py", "reference_chaves-unificadas"]
---

# Chaves de IA

## Em uma frase
As chaves dos provedores de IA (Anthropic, OpenAI, Google) ficam cifradas na organização; os
instrumentos e agentes as reusam conforme o **provedor do modelo** escolhido.

## Para que serve / quando usar
Toda chamada de IA (agentes, IA de conversa, gerar imagem, transcrição) precisa de uma chave do provedor
certo. O Batuta resolve isso por um **pool**: primeiro a chave da **organização**; se não houver, cai na
chave da **consultoria** (fallback).

- É **uma chave por provedor** — a escolha de qual IA usar fica no **modelo** do agente.
- Os **prontos de IA** não pedem chave própria: reusam a do pool.
- **A chave libera os instrumentos daquela IA** (desde 01/10/2026): com a chave da **OpenAI**, a
  organização ganha **Gerar imagem** e **Montar imagem**; com a do **Google**, também Gerar imagem e
  Montar imagem, além de **Gerar vídeo** (Veo) e **Narrar texto**; com a de **qualquer uma das três**,
  **Pesquisar na web**, **Ler página da web** e **Ler documento (PDF)**; com a da **Anthropic ou a da
  OpenAI**, **Gerar arquivo e analisar dados**; e **Descrever imagem** com qualquer uma. A IA que faz o
  trabalho é a do modelo escolhido no instrumento.
- **Áudio do Telegram:** com a chave do Google, a transcrição vai por ele (aceita o áudio como chega);
  sem ela, pela OpenAI. Se o Google falhar e houver chave da OpenAI, a OpenAI transcreve.
- **Conta do Google pré-paga:** se o crédito acabar, os instrumentos do Google avisam "a conta do Google
  da empresa está sem crédito" com o caminho (ai.studio/projects → Billing). Sem a chave, esses instrumentos não aparecem em "Instrumento pronto" e criar
  um é recusado, dizendo qual chave falta. A tela de chaves mostra o que cada chave libera.

## Como usar (na tela)
1. Em **Chaves de IA** da organização, cadastre a chave de cada provedor que for usar.
2. A chave vai **cifrada** e nunca é reexibida (só os últimos dígitos).
3. Escolha o **modelo** de IA em cada agente — o provedor daquele modelo define qual chave é usada.

## Exemplos
- Cadastrou a chave OpenAI da org → Gerar imagem e Montar imagem aparecem para criar, e
  agentes com modelo OpenAI passam a funcionar.
- Sem chave na org, mas com chave na consultoria → funciona pelo fallback.

## Limites e cuidados
- **Sem a chave do provedor certo, a chamada falha** com um recado claro. Um instrumento de IA que já
  existe e perdeu a chave aparece como **precisa de atenção** (falta a chave).
- O **uso é medido** (informativo) por provedor/origem — veja [[operacao/uso-e-custos]].

## Para a IA
Não peça ao consultor uma "chave da executora/da conversa" — é **uma por provedor**. Se um instrumento
reusa o pool (ex.: imagem→OpenAI) e a org já tem a chave, não acuse falta de chave. No catálogo,
`precisa_chave_de_ia` diz qual IA libera cada pronto; sem ela a criação é recusada — confira em
`ver_chaves_de_ia` e oriente um admin a cadastrar. Segredo você **nunca**
vê nem pede em texto; oriente a cadastrar na tela.

## Relacionado
- [[segredos/segredos-de-instrumento]]
- [[operacao/uso-e-custos]]
