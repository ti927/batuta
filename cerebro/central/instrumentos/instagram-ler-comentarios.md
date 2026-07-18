---
titulo: "Instrumento — Instagram: ler comentários"
area: "instrumentos"
slug: "instagram-ler-comentarios"
tags: ["instagram", "comentarios", "ler", "moderacao", "leitura", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/instagram_ler_comentarios.py"]
---

# Instrumento — Instagram: ler comentários

## Em uma frase
Lê os comentários de um post do Instagram (texto, autor, data e curtidas) a partir do id do post.

## Para que serve / quando usar
Para o agente **revisar os comentários** de um post — moderar, responder em lote ou levantar o que as
pessoas estão dizendo. É o par de leitura do [[instrumentos/instagram-responder-comentario]].

## Como usar (na tela)
1. Crie o instrumento **Instagram: ler comentários**.
2. Em **Credencial da central**, aponte para a credencial `instagram`.
3. Pendure no cinto do agente que trata comentários.

## Exemplos
- Um agente que, todo dia, lê os comentários dos últimos posts e responde os que forem dúvidas.

## Limites e cuidados
- Precisa da credencial `instagram` conectada.
- Traz de 1 a 50 comentários por chamada.
- Só leitura → não exige portão.

## Para a IA
Parâmetros no catálogo (`instagram_ler_comentarios`): `media_id` e `limite`. Para responder em tempo real
a cada comentário, o caminho natural é o **gatilho de comentário do Instagram** (veja [[automacoes/gatilhos]]),
que já entrega o comentário; este instrumento é para varrer os comentários de um post sob demanda.

## Relacionado
- [[instrumentos/instagram-responder-comentario]]
- [[instrumentos/instagram-ler-post]]
- [[automacoes/gatilhos]]
