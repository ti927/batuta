---
titulo: "Instrumento — WordPress: publicar"
area: "instrumentos"
slug: "publicar-wordpress"
tags: ["wordpress", "publicar", "blog", "artigo", "post", "imagem-destacada", "413", "upload", "instrumento"]
revisado_em: "2026-08-14"
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
3. Como é **ação irreversível**, dê ao agente que apresenta o instrumento **Pedir aprovação e aguardar**.

## Exemplos
- [idealizador → redator → revisor → **pede aprovação**] → [publicar no WordPress como `publish`].
- Publicar como rascunho para revisão humana no próprio WordPress.

## Limites e cuidados
- É `acao_irreversivel = true` → pede aprovação antes.
- A **senha de aplicativo** é a do WordPress (não a senha de login); o usuário precisa de permissão para
  publicar e enviar mídia (papel Autor ou superior).
- **Plugin Wordfence instalado?** Ele costuma **desligar as senhas de aplicativo** por padrão, e aí a
  autenticação falha (401/403) por mais correta que a senha esteja. Solução: no WordPress, vá em
  **Wordfence → Firewall → Todas as opções do Firewall → Proteção contra força bruta** e **desmarque**
  "Desativar senhas de aplicação do WordPress". Sem isso, o instrumento não consegue publicar.
- **Categorias inexistentes são ignoradas**; **tags** são criadas se ainda não existirem.
- A **imagem destacada** é subida antes e ligada ao post; se você pediu imagem e o upload falha, não
  publica sem ela (a falha sobe clara).
- **Imagem pesada → erro 413 "Payload Too Large".** O servidor tem um teto de tamanho de upload (padrão
  do nginx ~1 MB) e um **PNG** de 1024×1024 (~1,3 MB) o estoura → a publicação falha. Não é resolução nem
  servidor cheio, é **peso**. Solução simples: no instrumento [[instrumentos/gerar-imagem]], escolha
  **Formato = JPEG** (mesma resolução, ~150–300 KB). Alternativa: aumentar o limite de upload no servidor.

## Para a IA
Parâmetros no catálogo (`publicar_wordpress`): `titulo`, `conteudo` (texto/HTML), `tags`, `resumo`,
`imagem_url` (link da imagem gerada antes). A **categoria** e o **status** são da configuração do humano,
não seus. Monte com aprovação antes; o nó que publica recebe o artigo **pronto**.

Se a publicação falhar com **autenticação recusada (401/403)** e a senha estiver correta, oriente o
consultor a checar o **Wordfence**: em Firewall → Proteção contra força bruta, precisa **desmarcar**
"Desativar senhas de aplicação do WordPress" (o plugin costuma bloqueá-las).

## Relacionado
- [[instrumentos/gerar-imagem]]
- [[automacoes/pedir-aprovacao]]
- [[segredos/credenciais-nomeadas]]
