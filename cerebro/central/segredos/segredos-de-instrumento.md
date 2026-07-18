---
titulo: "Segredos de instrumento (inline, credencial ou pool)"
area: "segredos"
slug: "segredos-de-instrumento"
tags: ["segredo", "instrumento", "cofre", "credencial", "pool", "chave-compartilhada", "token"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/base.py", "reference_chaves-unificadas"]
---

# Segredos de instrumento (inline, credencial ou pool)

## Em uma frase
Um instrumento que precisa de segredo (token, senha, chave) o recebe por **um de três caminhos**: digitado
no próprio instrumento, apontado para uma credencial, ou reusado de um pool compartilhado.

## Para que serve / quando usar
Entender de onde vem o segredo evita o erro comum de "achar que está pronto" quando o token não foi ligado.
Os três caminhos:

- **Inline (no instrumento)** — você digita o segredo no campo do instrumento; ele vai **cifrado** (cofre).
  Simples, mas não é reusável.
- **Credencial nomeada** — o instrumento aponta para uma [[segredos/credenciais-nomeadas]] tipada (ex.:
  `instagram`, WordPress). Reusável e trocável num lugar só.
- **Pool compartilhado** — chaves de serviço que os instrumentos reusam sem você recadastrar (ex.: imagem e
  busca reusam a chave OpenAI/Tavily da organização). Veja [[segredos/chaves-de-ia]].

## Como usar (na tela)
1. No formulário do instrumento, os campos secretos aparecem como **segredo** (nunca são reexibidos).
2. Para reusar, use **Credencial da central** — os campos vindos da credencial ficam **ocultos** no
   formulário.
3. Para os que reusam o **pool** (imagem, busca), deixe a chave **em branco** — o Batuta injeta a do pool.

## Exemplos
- `publicar_instagram` → credencial `instagram`.
- `gerar_imagem` → pool OpenAI (chave em branco).
- `chamar_api_rest` → token bearer inline (ou credencial do tipo bearer).

## Limites e cuidados
- Segredos **nunca** voltam à tela (só os últimos dígitos).
- **Duplicar** o time não copia segredos — a cópia nasce a reconectar.
- Um instrumento sem o segredo do caminho certo **falha com recado claro** ao rodar.

## Para a IA
Você nunca vê nem digita segredo. Ao montar um instrumento com segredo, escolha o caminho: pool (se a org
já tem a chave do serviço), credencial (reuso) ou inline. Se falta ligar, **avise o humano** e não diga
"pronto".

## Relacionado
- [[segredos/chaves-de-ia]]
- [[segredos/credenciais-nomeadas]]
- [[instrumentos/cinto]]
