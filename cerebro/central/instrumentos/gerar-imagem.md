---
titulo: "Instrumento — Gerar imagem"
area: "instrumentos"
slug: "gerar-imagem"
tags: ["gerar-imagem", "imagem", "arte", "openai", "gpt-image", "google", "gemini", "tamanho", "proporcao", "formato", "png", "jpeg", "413", "instrumento"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/gerar_imagem.py", "PRODUTO.md §13"]
---

# Instrumento — Gerar imagem

## Em uma frase
Cria uma imagem a partir de uma descrição (prompt) e devolve um link público para ela.

## Para que serve / quando usar
Ilustrar conteúdo, criar artes e mockups. A imagem gerada fica numa **URL pública**, pronta para o
próximo passo (ex.: publicar no Instagram, animar num vídeo).

## Como usar (na tela)
1. Crie o instrumento **Gerar imagem** (aparece quando a organização tem a chave da OpenAI ou a do
   Google).
2. Escolha o **Modelo** — da OpenAI: **GPT Image 2**, o padrão; **2.5 Flare**, rápido para o dia a dia;
   **2.5 Sunburst**, a edição mais precisa; do Google: **Gemini 3.1 Flash Image**, **Flash-Lite Image**
   (o mais barato) e **3 Pro Image** (acabamento superior). Só funciona o modelo da IA que tem chave.
   Depois, o **Tamanho** e a **Qualidade** (as opções dependem do modelo; ao lado do tamanho há uma
   **ilustração da proporção**). Nos modelos do Google, o tamanho é a **proporção** (1:1, 4:5, 9:16…) e a
   qualidade é a **resolução** (1K, 2K, 4K).
3. Escolha o **Formato**: **PNG** (padrão, sem perdas, mais pesado) ou **JPEG** (mesma resolução, bem
   mais leve). Prefira **JPEG** quando a imagem for **subir para um site** (ex.: WordPress) — evita a
   recusa por tamanho (ver abaixo).
4. A **chave** de imagem reusa a chave da organização (deixe em branco para usar a do pool).

## Exemplos
- Arte quadrada para feed: tamanho `1024x1024` (1:1).
- Arte de **Story/Reels** (vertical, tela cheia): tamanho **`864x1536`** (9:16).
- Feed em retrato: `1024x1280` (4:5).
- No Google: Story em `9:16` e `1K`; feed em `4:5`.

## Limites e cuidados
- **Modelos antigos saíram** (gpt-image-1 em 23/10/2026; 1-mini e 1.5 em 01/12/2026, pela OpenAI). Um
  instrumento antigo configurado com eles passa a usar o GPT Image 2 sozinho, sem precisar editar.
- **Custo por imagem**, e maior na qualidade `high`. No Google, por resolução: Flash Image US$ 0,067
  (1K), 0,101 (2K) e 0,151 (4K); Flash-Lite US$ 0,034; Pro US$ 0,134 (até 2K) e 0,24 (4K).
- Toda imagem do Google sai com uma marca invisível (SynthID) que a identifica como feita por IA.
- A resposta traz o `custo_estimado_usd` da imagem (o painel de uso conta o mesmo valor). O Google
  devolve JPEG; se o formato pedido for PNG, o Batuta converte.
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
Não peça "chave própria" se a organização já tem a chave no pool. Com só a chave do Google, escolha
um modelo `gemini-…-image` (tamanho = proporção, qualidade = `1K`/`2K`/`4K`).

## Relacionado
- [[instrumentos/montar-imagem]]
- [[instrumentos/gerar-video]]
