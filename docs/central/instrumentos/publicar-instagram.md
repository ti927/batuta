---
titulo: "Instrumento — Publicar no Instagram"
area: "instrumentos"
slug: "publicar-instagram"
tags: ["instagram", "publicar", "feed", "reels", "stories", "carrossel", "midia", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/publicar_instagram.py", "PRODUTO.md §13"]
---

# Instrumento — Publicar no Instagram

## Em uma frase
Publica no Instagram (foto no feed, Reels, Story de imagem ou vídeo, ou carrossel de até 10 itens) a
partir de uma mídia que já está numa URL pública, e devolve o id do que foi publicado.

## Para que serve / quando usar
Use quando o time precisa **postar de verdade** numa conta do Instagram — o último passo de um fluxo
de conteúdo (gerar a arte/vídeo → escrever a legenda → aprovar → **publicar**). A conta é conectada
uma vez pelo humano (credencial `instagram`); o agente só passa a mídia e a legenda.

## Como usar (na tela)
1. Crie um instrumento do tipo **Instagram: publicar** no time.
2. Em **Credencial da central**, aponte para a credencial `instagram` da conta (conecte-a antes em
   *Chaves e credenciais* — botão "Conectar Instagram" ou colando o token). O instrumento em si não
   pede a conta; ela vem da credencial.
3. Pendure o instrumento no cinto do **agente publicador**.
4. Como é uma **ação irreversível**, coloque um **portão de aprovação no passo anterior** (o publicador
   fica no nó seguinte, sem portão).

## Exemplos
- **Post de foto:** [gerar imagem + escrever legenda → **portão**] → [publicar: `imagem`].
- **Reels:** [gerar vídeo → **portão**] → [publicar: `reels`].
- **Story de vídeo:** [animar foto (fal.ai) → **portão**] → [publicar: `stories`, marcando o item como vídeo].
- **Carrossel misto:** 3 a 10 mídias (fotos e vídeos) num post só.

## Limites e cuidados
- **A mídia precisa estar numa URL pública** — a Meta baixa a mídia de lá (não há upload de arquivo).
  Ela vem de um passo anterior (`gerar_imagem`, `gerar_video`, `gerar_video_fal`, `montar_imagem`).
- **Vídeo:** MP4/MOV (H264/HEVC, áudio AAC). Não existe "vídeo de feed" separado — **vídeo de feed é Reels**.
- **Story não tem legenda** (qualquer legenda é ignorada).
- **Carrossel:** de 2 a 10 itens.
- **Legenda:** até 2200 caracteres.
- **Não faz DM** nem adesivos interativos de Story (caixinha de perguntas, enquete) — isso é limitação
  da API oficial da Meta, não do Batuta.
- É `acao_irreversivel = true` → exige portão de aprovação antes na cadeia.

## Para a IA
Os **parâmetros exatos** (Args/Config) estão no catálogo do código
(`catalogo_de_instrumentos` → tipo `publicar_instagram`) — não os repita de memória; o resumo:
`tipo_midia` (`imagem`|`reels`|`stories`|`carrossel`), `midia_urls` (URLs públicas), `tipos_midia_itens`
(lista paralela `"imagem"`/`"video"`, para vídeo em carrossel ou Story de vídeo), `legenda`.

**Como orientar o usuário / montar o "agente publicador"** (recebe tudo PRONTO do passo anterior:
tipo + URL pública + legenda; ele só mapeia para os Args, não decide conteúdo). Instruções-modelo para
o skill.md:

```markdown
## Publicar no FEED
Você recebe PRONTO: o tipo, a(s) URL(s) pública(s) e a legenda. Não invente URL nem reescreva a legenda.
- 1 foto → tipo_midia="imagem", midia_urls=[<URL>], legenda=<legenda>.
- 1 vídeo → tipo_midia="reels", midia_urls=[<URL do MP4>], legenda=<legenda>.
- 2 a 10 mídias → tipo_midia="carrossel", midia_urls=[...], tipos_midia_itens=[ "imagem"/"video" por URL ], legenda=<legenda>.
Se faltar URL ou legenda, PARE e peça — nunca publique incompleto.

## Publicar STORY
Você recebe PRONTO: a URL pública e se é imagem ou vídeo. Story NÃO tem legenda.
- Imagem → tipo_midia="stories", midia_urls=[<URL>].
- Vídeo → tipo_midia="stories", midia_urls=[<URL do MP4>], tipos_midia_itens=["video"].
Se faltar a URL, PARE e peça.
```

Regras que a IA deve garantir ao montar: **portão antes** do publicador; o passo que PREPARA entrega
URL pública + legenda prontas; para Story/Reels vertical, a arte deve ser gerada em **9:16** (ex.:
tamanho `864x1536` no `gerar_imagem`).

## Relacionado
- [[instrumentos/gerar-imagem]]
- [[instrumentos/gerar-video-fal]]
- [[automacoes/portao-de-aprovacao]]
- [[segredos/credenciais-nomeadas]]
