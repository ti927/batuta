---
titulo: "Instrumento — WordPress: publicar"
area: "instrumentos"
slug: "publicar-wordpress"
tags: ["wordpress", "publicar", "blog", "artigo", "post", "imagem-destacada", "instrumento"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/wordpress.py"]
---

# Instrumento — WordPress: publicar

## Em uma frase
Publica um artigo no WordPress e devolve o link do post — com título, conteúdo e, se quiser, tags, resumo
e uma imagem destacada.

## Para que serve / quando usar
O último passo de um fluxo de blog: o agente entrega o artigo pronto e o instrumento publica (rascunho ou
no ar). A imagem destacada pode vir de um passo de [[instrumentos/gerar-imagem]].

## Como usar (na tela)
1. Crie o instrumento **WordPress: publicar** e configure o **site**, o **usuário** e a **senha de
   aplicativo** (segredo) — ou aponte para uma credencial WordPress.
2. Escolha o **status** (`draft` = rascunho; `publish` = no ar) e as **categorias** onde publicar.
3. Como é **ação irreversível**, coloque um **portão de aprovação no passo anterior**.

## Exemplos
- [idealizador → redator → revisor → **portão**] → [publicar no WordPress como `publish`].
- Publicar como rascunho para revisão humana no próprio WordPress.

## Limites e cuidados
- É `acao_irreversivel = true` → exige portão antes.
- A **senha de aplicativo** é a do WordPress (não a senha de login); o usuário precisa de permissão para
  publicar e enviar mídia (papel Autor ou superior).
- **Categorias inexistentes são ignoradas**; **tags** são criadas se ainda não existirem.
- A **imagem destacada** é subida antes e ligada ao post; se você pediu imagem e o upload falha, não
  publica sem ela (a falha sobe clara).

## Para a IA
Parâmetros no catálogo (`publicar_wordpress`): `titulo`, `conteudo` (texto/HTML), `tags`, `resumo`,
`imagem_url` (link da imagem gerada antes). A **categoria** e o **status** são da configuração do humano,
não seus. Monte com portão antes; o nó que publica recebe o artigo **pronto**.

## Relacionado
- [[instrumentos/gerar-imagem]]
- [[automacoes/portao-de-aprovacao]]
- [[segredos/credenciais-nomeadas]]
