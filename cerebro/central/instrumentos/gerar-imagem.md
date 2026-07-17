---
titulo: "Instrumento — Gerar imagem"
area: "instrumentos"
slug: "gerar-imagem"
tags: ["gerar-imagem", "imagem", "arte", "openai", "gpt-image", "tamanho", "proporcao", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/gerar_imagem.py", "PRODUTO.md §13"]
---

# Instrumento — Gerar imagem

## Em uma frase
Cria uma imagem a partir de uma descrição (prompt) e devolve um link público para ela.

## Para que serve / quando usar
Ilustrar conteúdo, criar artes e mockups. A imagem gerada fica numa **URL pública**, pronta para o
próximo passo (ex.: publicar no Instagram, animar num vídeo).

## Como usar (na tela)
1. Crie o instrumento **Gerar imagem** (provedor OpenAI, família gpt-image).
2. Escolha o **Modelo**, o **Tamanho** e a **Qualidade** (as opções de tamanho dependem do modelo; ao
   lado do tamanho há uma **ilustração da proporção** para você bater o olho).
3. A **chave** de imagem reusa a chave OpenAI da organização (deixe em branco para usar a do pool).

## Exemplos
- Arte quadrada para feed: tamanho `1024x1024` (1:1).
- Arte de **Story/Reels** (vertical, tela cheia): tamanho **`864x1536`** (9:16).
- Feed em retrato: `1024x1280` (4:5).

## Limites e cuidados
- **Custo por imagem**, e maior na qualidade `high`.
- O instrumento é **texto→imagem** (cria do zero, não recebe foto de entrada). Para montar com uma foto
  existente, use [[instrumentos/montar-imagem]].
- A combinação modelo × tamanho × qualidade precisa ser válida (a tela já filtra).

## Para a IA
Parâmetros no catálogo (`gerar_imagem`). Para **Story/Reels**, oriente gerar em **9:16** (`864x1536`);
para feed vertical, 4:5 (`1024x1280`). A imagem sai numa URL pública — encadeie-a no passo que publica
ou anima. Não peça "chave própria" se a organização já tem chave OpenAI no pool.

## Relacionado
- [[instrumentos/montar-imagem]]
- [[instrumentos/gerar-video-fal]]
- [[instrumentos/publicar-instagram]]
