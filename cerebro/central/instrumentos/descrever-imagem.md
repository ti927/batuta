---
titulo: "Instrumento — Descrever/ler imagem (visão)"
area: "instrumentos"
slug: "descrever-imagem"
tags: ["descrever-imagem", "visao", "imagem-para-texto", "multimodal", "ler-imagem", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/descrever_imagem.py", "project_descrever-imagem-visao-multiprovedor"]
---

# Instrumento — Descrever/ler imagem (visão)

## Em uma frase
Uma IA de visão **lê** uma ou mais imagens e devolve uma descrição em texto — o oposto de gerar imagem.

## Para que serve / quando usar
Para o agente **entender uma foto** e responder com contexto. O caso clássico: um comentário no Instagram
sobre o post — o agente lê o post ([[instrumentos/instagram-ler-post]]), pega a URL da imagem, "enxerga"
com este instrumento e então responde bem.

## Como usar (na tela)
1. Crie o instrumento **Descrever/ler imagem (visão)**.
2. Escolha o **Modelo de IA (visão)** — só aparecem os modelos de provedores com **chave cadastrada** na
   organização (a chave vem do pool; não há segredo próprio).
3. Pendure no cinto do agente que precisa "ver".

## Exemplos
- Ler a arte de um post para responder um comentário com contexto.
- Extrair o texto/elementos que aparecem numa imagem enviada por um contato.

## Limites e cuidados
- É **imagem→texto** (não gera imagem).
- De 1 a 8 imagens por leitura; para vídeo/Reels, passe a URL da **miniatura**, não a do vídeo.
- Precisa de chave do provedor do modelo escolhido; sem ela, falha com recado claro.
- Só leitura → ninguém precisa aprovar nada.

## Para a IA
Parâmetros no catálogo (`descrever_imagem`): `imagens_url` (URLs públicas) e `instrucao` (o que extrair).
É multimodal e agnóstico de provedor — serve a modelos OpenAI, Claude ou Gemini, conforme a chave da org.

## Relacionado
- [[instrumentos/instagram-ler-post]]
- [[instrumentos/instagram-responder-comentario]]
- [[segredos/chaves-de-ia]]
