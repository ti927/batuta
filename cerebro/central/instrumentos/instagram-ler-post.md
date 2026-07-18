---
titulo: "Instrumento — Instagram: ler post"
area: "instrumentos"
slug: "instagram-ler-post"
tags: ["instagram", "ler-post", "legenda", "midia", "comentario", "leitura", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/instagram_ler_post.py"]
---

# Instrumento — Instagram: ler post

## Em uma frase
Lê o conteúdo de um post do Instagram (legenda, tipo, URL da imagem, link, curtidas e nº de comentários)
a partir do id do post.

## Para que serve / quando usar
Para o agente responder um comentário **com o contexto do post**, e não só com o texto isolado do
comentário. O id do post é o `media_id` que o gatilho de comentário entrega, ou o id devolvido ao publicar.

## Como usar (na tela)
1. Crie o instrumento **Instagram: ler post**.
2. Em **Credencial da central**, aponte para a credencial `instagram` da conta (a mesma que publica).
3. Pendure no cinto do agente que trata comentários.

## Exemplos
- Corrente de resposta a comentário: ler post → [[instrumentos/descrever-imagem]] (enxergar a arte) →
  [[instrumentos/instagram-responder-comentario]].

## Limites e cuidados
- Precisa da credencial `instagram` conectada (token + conta).
- Para FOTO, a URL da mídia é a própria imagem; para VÍDEO/Reels, é o vídeo — use a **miniatura** como
  imagem quando quiser "ver".
- Só leitura → não exige portão.

## Para a IA
Parâmetro no catálogo (`instagram_ler_post`): `media_id`. A `imagem` devolvida pode ir direto ao
`descrever_imagem` para o agente entender a foto antes de responder.

## Relacionado
- [[instrumentos/instagram-ler-comentarios]]
- [[instrumentos/instagram-responder-comentario]]
- [[instrumentos/descrever-imagem]]
