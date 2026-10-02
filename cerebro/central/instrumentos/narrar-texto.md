---
titulo: "Instrumento — Narrar texto (voz)"
area: "instrumentos"
slug: "narrar-texto"
tags: ["narrar-texto", "voz", "audio", "locucao", "tts", "google", "gemini", "podcast", "instrumento"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/narrar_texto.py"]
---

# Instrumento — Narrar texto (voz)

## Em uma frase
Transforma um texto em **áudio falado**, em português, com uma voz do Google, e devolve o link do
arquivo.

## Para que serve / quando usar
A versão em áudio de um post ou artigo, uma mensagem de voz para o cliente, a locução de um vídeo.

## Como usar (na tela)
1. Crie o instrumento **Narrar texto (voz)** (aparece quando a organização tem a chave do Google).
2. Escolha a **Voz** (são 30; algumas: Kore, firme; Puck, animada; Charon, informativa; Achird,
   amigável; Sulafat, calorosa; Gacrux, madura) e, se quiser, o **Jeito de falar** (ex.: "animado e
   próximo, como num podcast").
3. O **Modelo** vem no Flash-Lite (o mais barato); o Flash é mais expressivo.

## Exemplos
- O agente escreve o resumo semanal e gera a versão em áudio para mandar no grupo.
- A locução de um Reels feito com o [[instrumentos/gerar-video]].

## Limites e cuidados
- Até 5 mil caracteres por narração.
- O arquivo sai em **WAV** (24 kHz, mono): cerca de 2,9 MB por minuto. Serve para baixar, anexar ou
  subir num site; no Telegram vai como arquivo de áudio, não como "mensagem de voz".
- **Custo real por uso**, pelo que o Google informa: cerca de US$ 0,002 a cada 10 s no Flash e menos no
  Flash-Lite (os preços do Google sobem em 01/01/2027).
- Pausas e respirações podem ir no próprio texto, entre sinais: `<short pause>`, `<sigh>`.
- Só gera um arquivo → ninguém precisa aprovar (quem ENVIA é que pode precisar).
- A OpenAI não entra aqui: ela anunciou o desligamento dos modelos de voz dela em 06/01/2027.

## Para a IA
Argumento (`narrar_texto`): `texto` (exatamente como deve soar). Na configuração: `modelo`, `voz` e `tom`
(opcional). Devolve `url` (WAV) e `segundos`. Encadeie a URL no passo que envia ou publica. Sem a chave
do Google, a criação é recusada.

## Relacionado
- [[instrumentos/gerar-video]]
- [[segredos/chaves-de-ia]]
