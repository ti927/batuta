---
titulo: "Instrumento — Gerar vídeo (Sora)"
area: "instrumentos"
slug: "gerar-video"
tags: ["gerar-video", "video", "sora", "openai", "reels", "texto-para-video", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/gerar_video.py"]
---

# Instrumento — Gerar vídeo (Sora)

## Em uma frase
Gera um vídeo curto a partir de uma descrição (e, opcionalmente, de uma imagem inicial), com a IA de
vídeo da OpenAI (Sora), e devolve um link público para o MP4.

## Para que serve / quando usar
Produzir um Reels, um Story de vídeo ou um item de vídeo de um carrossel. Faz **texto→vídeo** e também
**imagem→vídeo** (anima a partir de um quadro inicial — ex.: uma arte gerada no passo anterior). O link
serve direto ao [[instrumentos/publicar-instagram]].

## Como usar (na tela)
1. Crie o instrumento **Gerar vídeo** (provedor OpenAI/Sora).
2. Escolha o **Modelo** (`sora-2`, mais barato e 720p; `sora-2-pro`, até 1080p), o **Tamanho** e a
   **Duração** (as opções dependem do modelo). O padrão é vertical (720x1280), bom para Reels/Stories.
3. A **chave** reusa a chave OpenAI da organização (deixe em branco para usar a do pool).

## Exemplos
- Um Reels vertical de 8s a partir de um roteiro.
- Animar uma arte gerada antes: passe a URL da imagem como quadro inicial (mesma resolução do vídeo).

## Limites e cuidados
- **Leva alguns minutos** para ficar pronto — o passo aguarda dentro do próprio fluxo.
- **Cobrado por segundo:** um clipe mais longo custa proporcionalmente mais. Prefira clipes curtos.
- A OpenAI embute uma **marca d'água "Sora"** visível — não há como removê-la pela API.
- **Sem pessoas reais / figuras públicas** (no roteiro e na imagem de referência) — a Sora recusa. Para
  animar o rosto de uma pessoa real, use [[instrumentos/gerar-video-fal]].
- Se usar imagem de referência, ela precisa ter **exatamente o tamanho** do vídeo.
- Não é irreversível (só gera o arquivo) — quem PUBLICA é que pede aprovação, num passo seguinte.

## Para a IA
Parâmetros no catálogo (`gerar_video`): `prompt` (roteiro) e `imagem_referencia_url` (opcional, quadro
inicial). Para Reels/Stories, gere em vertical. Encadeie a URL do MP4 no passo que publica. Se o conteúdo
tem rosto real, prefira o `gerar_video_fal` (a Sora bloqueia).

## Relacionado
- [[instrumentos/gerar-video-fal]]
- [[instrumentos/gerar-imagem]]
- [[instrumentos/publicar-instagram]]
