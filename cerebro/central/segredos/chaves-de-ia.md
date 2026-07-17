---
titulo: "Chaves de IA"
area: "segredos"
slug: "chaves-de-ia"
tags: ["chave", "ia", "openai", "anthropic", "google", "provedor", "pool", "consultoria", "custo"]
revisado_em: "2026-07-17"
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
- `gerar_imagem`/busca não pedem chave própria: reusam a do pool.

## Como usar (na tela)
1. Em **Chaves e credenciais** da organização, cadastre a chave de cada provedor que for usar.
2. A chave vai **cifrada** e nunca é reexibida (só os últimos dígitos).
3. Escolha o **modelo** de IA em cada agente — o provedor daquele modelo define qual chave é usada.

## Exemplos
- Cadastrou a chave OpenAI da org → o `gerar_imagem` e agentes com modelo OpenAI passam a funcionar.
- Sem chave na org, mas com chave na consultoria → funciona pelo fallback.

## Limites e cuidados
- **Sem a chave do provedor certo, a chamada falha** com um recado claro.
- O **uso é medido** (informativo) por provedor/origem — veja [[operacao/uso-e-custos]].

## Para a IA
Não peça ao consultor uma "chave da executora/da conversa" — é **uma por provedor**. Se um instrumento
reusa o pool (ex.: imagem→OpenAI) e a org já tem a chave, não acuse falta de chave. Segredo você **nunca**
vê nem pede em texto; oriente a cadastrar na tela.

## Relacionado
- [[segredos/credenciais-nomeadas]]
- [[segredos/segredos-de-instrumento]]
- [[operacao/uso-e-custos]]
