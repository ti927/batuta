---
titulo: "Instrumento — Gerar imagem"
area: "instrumentos"
slug: "gerar-imagem"
tags: ["gerar-imagem", "imagem", "arte", "openai", "gpt-image", "tamanho", "proporcao", "formato", "png", "jpeg", "413", "instrumento"]
revisado_em: "2026-08-14"
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
3. Escolha o **Formato**: **PNG** (padrão, sem perdas, mais pesado) ou **JPEG** (mesma resolução, bem
   mais leve). Prefira **JPEG** quando a imagem for **subir para um site** (ex.: WordPress) — evita a
   recusa por tamanho (ver abaixo).
4. A **chave** de imagem reusa a chave OpenAI da organização (deixe em branco para usar a do pool).

## Exemplos
- Arte quadrada para feed: tamanho `1024x1024` (1:1).
- Arte de **Story/Reels** (vertical, tela cheia): tamanho **`864x1536`** (9:16).
- Feed em retrato: `1024x1280` (4:5).

## Limites e cuidados
- **Custo por imagem**, e maior na qualidade `high`.
- O instrumento é **texto→imagem** (cria do zero, não recebe foto de entrada). Para montar com uma foto
  existente, use [[instrumentos/montar-imagem]].
- A combinação modelo × tamanho × qualidade precisa ser válida (a tela já filtra).
- **Peso do arquivo × limite de upload.** Um **PNG** de 1024×1024 pesa ~1,3 MB e pode **estourar o limite
  de upload** de um site — o WordPress recusa com **HTTP 413 "Payload Too Large"** (o teto padrão do nginx
  é ~1 MB) e a publicação falha. O mesmo desenho em **JPEG** cai para ~150–300 KB e entra tranquilo. Não é
  resolução nem servidor cheio: é só **peso**. Solução: **Formato = JPEG** no instrumento.

## Para a IA
Parâmetros no catálogo (`gerar_imagem`), incluindo o campo **`formato`** (`png`/`jpeg`). Para
**Story/Reels**, oriente gerar em **9:16** (`864x1536`); para feed vertical, 4:5 (`1024x1280`). Se a
imagem vai ser **publicada num site** (WordPress etc.), oriente **Formato = JPEG** — o PNG costuma passar
do limite de upload (erro 413). A imagem sai numa URL pública — encadeie-a no passo que publica ou anima.
Não peça "chave própria" se a organização já tem chave OpenAI no pool.

## Relacionado
- [[instrumentos/montar-imagem]]
- [[instrumentos/gerar-video-fal]]
- [[instrumentos/publicar-instagram]]
