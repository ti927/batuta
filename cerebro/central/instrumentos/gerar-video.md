---
titulo: "Instrumento — Gerar vídeo"
area: "instrumentos"
slug: "gerar-video"
tags: ["gerar-video", "video", "veo", "google", "gemini", "sora", "reels", "stories", "texto-para-video", "audio", "instrumento"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/gerar_video.py", "cerebro/precos.py"]
---

# Instrumento — Gerar vídeo

## Em uma frase
Gera um vídeo curto, **com áudio**, a partir de uma descrição (e, se quiser, de uma imagem inicial),
com a IA de vídeo do Google (Veo 3.1), e devolve um link público para o MP4.

## Para que serve / quando usar
Produzir um Reels, um Story de vídeo ou um item de vídeo de um carrossel. Faz **texto→vídeo** e também
**imagem→vídeo** (anima a partir de um quadro inicial — ex.: uma arte gerada no passo anterior). O link
serve direto ao instrumento personalizado que publica (ex.: o conector da rede social).

## Como usar (na tela)
1. Crie o instrumento **Gerar vídeo** (aparece quando a organização tem a chave do Google).
2. Escolha o **Modelo** — **Veo 3.1 Lite** (o padrão, o mais barato), **Fast** (rápido, até 4K) ou o
   **completo** (melhor qualidade) —, a **Proporção** (9:16 vertical, para Reels/Stories, ou 16:9
   horizontal), a **Resolução** e a **Duração** (4, 6 ou 8 segundos).
3. Pendure no cinto do agente e diga no markdown dele o que o vídeo deve mostrar e para onde vai o link.

## Exemplos
- Um Reels vertical de 8 s a partir de um roteiro, com a fala do apresentador e o som ambiente.
- Animar uma arte gerada antes: passe a URL da imagem como quadro inicial.

## Limites e cuidados
- **Leva de segundos a alguns minutos** (o Google diz de 11 s a 6 min). A tela mostra "Gerando o
  vídeo… (2 min)" enquanto espera.
- **Cobrado por segundo, já com o áudio:** Lite US$ 0,05 (720p) a 0,08 (1080p); Fast US$ 0,10 a 0,30
  (4K); completo US$ 0,40 a 0,60. Um Reels de 8 s no padrão custa cerca de **US$ 0,40**.
- **1080p e 4K só saem com 8 segundos.** O Lite não faz 4K.
- O Google recusa conteúdo pela política dele (ex.: pessoa pública reconhecível); o instrumento diz o
  motivo, e o agente deve ajustar o roteiro em vez de insistir.
- Todo vídeo do Google sai com uma marca invisível (SynthID) que o identifica como feito por IA.
- O vídeo fica só 2 dias no Google; o Batuta baixa e guarda no armazenamento dele na hora.
- **Imagem de partida em outra proporção** (ex.: uma arte quadrada num vídeo 9:16): o Batuta recorta
  no centro para a proporção do vídeo, em vez de sair com faixas pretas, e o resultado avisa.
- A resposta traz o `custo_estimado_usd` do vídeo (o painel de uso conta o mesmo valor).
- Não é irreversível (só gera o arquivo) — quem PUBLICA é que pede aprovação, num passo seguinte.
- **História:** até 24/09/2026 este instrumento usava a Sora, da OpenAI, que a OpenAI desligou. Uma
  configuração antiga de Sora passa a usar o Veo sozinha, com a mesma orientação.

## Para a IA
Parâmetros no catálogo (`gerar_video`): `prompt` (roteiro — cena, movimento de câmera, clima, falas e
sons) e `imagem_referencia_url` (opcional, quadro inicial). Na configuração: `modelo`, `tamanho` (a
proporção, `9:16` ou `16:9`), `resolucao` (`720p`, `1080p`, `4k`) e `duracao_s` (`4`, `6`, `8`).
Deixe o padrão (Lite, 9:16, 720p, 8 s) salvo pedido. Devolve `url` (MP4), `modelo`, `duracao_s` e
`resolucao`. Encadeie a URL no passo que publica. Sem a chave do Google, a criação é recusada.

## Relacionado
- [[instrumentos/gerar-imagem]]
- [[instrumentos/montar-imagem]]
- [[instrumentos/narrar-texto]]
