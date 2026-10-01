---
titulo: "Instrumento — Gerar vídeo a partir de foto (fal.ai)"
area: "instrumentos"
slug: "gerar-video-fal"
tags: ["gerar-video-fal", "video", "fal", "kling", "luma", "hailuo", "rosto", "animar-foto", "instrumento"]
revisado_em: "2026-10-01"
fontes: ["cerebro/instrumentos/gerar_video_fal.py", "project_fal-video-e-agendamento"]
---

# Instrumento — Gerar vídeo a partir de foto (fal.ai)

> **Não é mais um pronto do Batuta (desde 01/10/2026).** Integração com serviço de fora é
> instrumento **personalizado**: crie em **🌟 Criar instrumento → Uma API** (ou **Um servidor
> MCP**, se o serviço tiver um), com a chave do serviço no próprio instrumento (pela IA:
> `montar_conector` ou `configurar_instrumento` com `conectar_mcp`). Os que já existem seguem
> funcionando e editáveis até serem trocados — este capítulo vale só para eles.
> Ver [[instrumentos/construir-conector]] e [[instrumentos/mcp]].

## Em uma frase
Anima uma **foto** (URL pública) num clipe de vídeo pela fal.ai — e, ao contrário da Sora, **aceita
rosto de pessoa real**.

## Para que serve / quando usar
Ideal para o dono do negócio **animar a própria foto** em conteúdo de marketing. A entrada principal é a
imagem; o agente descreve o movimento/cena. O MP4 gerado serve direto ao [[instrumentos/publicar-instagram]].

## Como usar (na tela)
1. Crie o instrumento **Gerar vídeo a partir de foto**.
2. Escolha o **Modelo**: `kling` (melhor para rosto/pessoa — padrão), `luma` (cinematográfico) ou
   `hailuo` (econômico); e a **Duração** (as opções dependem do modelo).
3. Deixe **Travar composição** ligado (recomendado): o vídeo começa e termina na imagem original, o que
   evita zoom, corte e elementos "escapando" (vale no Luma e no Hailuo; no Kling o freio é o prompt
   negativo).
4. A **chave** reusa a chave `fal` da organização (deixe em branco para usar a do pool).

## Exemplos
- Animar a foto do dono para um Story vertical (9:16).
- Dar um leve movimento cinematográfico a uma arte de campanha.

## Limites e cuidados
- **Leva alguns minutos**; a conta paga entrega sem marca d'água.
- Os freios de movimento evitam que a IA "aluciná" e desmonte uma arte com texto — mantenha **Travar
  composição** ligado para arte que não pode deformar.
- **Proporção** só vale no Luma; Kling e Hailuo seguem a proporção da própria foto.
- Não é irreversível (só gera o arquivo) — quem publica é que pede aprovação.

## Para a IA
Parâmetros no catálogo (`gerar_video_fal`): `imagem_url` (a foto a animar) e `prompt` (o movimento/cena).
Os controles finos (travar composição, prompt negativo, cfg, proporção) são da **configuração** do humano,
não seus. Para rosto real, este instrumento; para texto→vídeo sem rosto real, o [[instrumentos/gerar-video]].

## Relacionado
- [[instrumentos/gerar-video]]
- [[instrumentos/montar-imagem]]
- [[instrumentos/publicar-instagram]]
