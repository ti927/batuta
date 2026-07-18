---
titulo: "Instrumento — Montar imagem (a partir de fotos)"
area: "instrumentos"
slug: "montar-imagem"
tags: ["montar-imagem", "imagem", "foto", "rosto", "composicao", "arte", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/montar_imagem.py"]
---

# Instrumento — Montar imagem (a partir de fotos)

## Em uma frase
Cria uma imagem NOVA combinando uma ou mais **fotos-base** (a pessoa, um produto, uma logo) com um tema
descrito em texto, preservando o rosto/produto das fotos.

## Para que serve / quando usar
Quando você quer a pessoa (ou o produto) **dentro** da cena — a arte de um post com o dono do negócio,
por exemplo. É diferente do [[instrumentos/gerar-imagem]], que cria do zero só a partir de texto: aqui o
agente também passa a **URL da(s) foto(s)-base**.

## Como usar (na tela)
1. Crie o instrumento **Montar imagem (a partir de fotos)**.
2. Escolha o **Modelo**, o **Tamanho** e a **Qualidade** (as opções de tamanho/qualidade dependem do
   modelo; ao lado, a ilustração da proporção). O padrão já vem bom para rosto: retrato, qualidade alta.
3. A **chave** reusa a chave OpenAI da organização (deixe em branco para usar a do pool).
4. Pendure no cinto do agente que monta a arte; explique no `tools.md` qual foto vem primeiro.

## Exemplos
- A foto da pessoa (fundo transparente) + "coloque-a num escritório moderno, com o texto X em destaque".
- Um produto + uma referência de estilo → arte de campanha com o produto preservado.

## Limites e cuidados
- **A 1ª foto é a mais preservada** (rosto/textura). Passe a foto principal primeiro.
- As fotos-base precisam estar em **URLs públicas** (o cérebro as baixa). De 1 a 16 fotos.
- Montagem em qualidade alta é **pesada** — leva minutos e tem um custo por imagem maior.
- Só a família **gpt-image-1 / gpt-image-1.5** reforça a fidelidade ao rosto da entrada.
- Não é ação irreversível (só gera um arquivo) — não exige portão.

## Para a IA
Parâmetros no catálogo (`montar_imagem`): `prompt` (descreva o PAPEL de cada imagem — qual PRESERVAR e
quais são só referência de estilo — e o tema) e `imagens_url` (a 1ª = a preservada). A imagem sai numa
URL pública — encadeie no passo que publica. Quando a Biblioteca chegar, a URL da foto-base virá de lá;
o contrato (receber URL) não muda.

## Relacionado
- [[instrumentos/gerar-imagem]]
- [[instrumentos/gerar-video-fal]]
- [[instrumentos/publicar-instagram]]
