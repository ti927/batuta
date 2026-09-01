---
titulo: "Instrumento — Instagram: responder ou moderar comentário"
area: "instrumentos"
slug: "instagram-responder-comentario"
tags: ["instagram", "responder", "comentario", "ocultar", "apagar", "moderar", "escrita", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/instagram_responder_comentario.py"]
---

# Instrumento — Instagram: responder ou moderar comentário

## Em uma frase
Age sobre um comentário do Instagram: **responde**, **oculta**, **reexibe** ou **apaga**.

## Para que serve / quando usar
O passo de **escrita** da moderação: publicar uma resposta pública, esconder um comentário indevido ou
removê-lo. É o par do [[instrumentos/instagram-ler-comentarios]].

## Como usar (na tela)
1. Crie o instrumento **Instagram: responder ou moderar comentário**.
2. Em **Credencial da central**, aponte para a credencial `instagram`.
3. Como é **ação irreversível** (age publicamente), dê ao agente que apresenta o instrumento **Pedir aprovação e aguardar**.

## Exemplos
- [ler o comentário + redigir a resposta → **pede aprovação**] → [responder].
- Um fluxo que oculta automaticamente comentários com palavras proibidas (com aprovação antes, se quiser).

## Limites e cuidados
- É `acao_irreversivel = true` → exige [[automacoes/pedir-aprovacao]] antes.
- **Apagar não dá para desfazer.**
- Para `responder`, a mensagem é obrigatória (não publica resposta vazia).
- Precisa da credencial `instagram` conectada.

## Para a IA
Parâmetros no catálogo (`instagram_responder_comentario`): `comment_id`, `acao`
(`responder`/`ocultar`/`reexibir`/`apagar`) e `mensagem` (só para responder). Monte com aprovação antes; o nó
que executa deve receber **pronto** o id do comentário e o texto da resposta.

## Relacionado
- [[instrumentos/instagram-ler-comentarios]]
- [[instrumentos/instagram-ler-post]]
- [[automacoes/pedir-aprovacao]]
