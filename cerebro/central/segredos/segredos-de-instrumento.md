---
titulo: "Segredos de instrumento (no próprio instrumento ou chave de IA)"
area: "segredos"
slug: "segredos-de-instrumento"
tags: ["segredo", "instrumento", "cofre", "credencial", "pool", "chave-compartilhada", "token", "senha"]
revisado_em: "2026-10-02"
fontes: ["cerebro/instrumentos/base.py", "cerebro/segredos_instrumento.py", "reference_chaves-unificadas"]
---

# Segredos de instrumento (no próprio instrumento ou chave de IA)

## Em uma frase
Tudo o que um instrumento precisa para entrar num sistema de fora (token, senha, certificado, login)
**mora dentro do próprio instrumento**. A página **Chaves de IA** da organização guarda só as chaves das
IAs (Anthropic, OpenAI, Google).

## Para que serve / quando usar
Entender de onde vem o segredo evita o erro comum de "achar que está pronto" quando o token não foi ligado.
São dois caminhos:

- **No instrumento** — o segredo é preenchido na criação dele (no Construtor, no passo de
  identificação, ou no formulário do pronto); vai **cifrado** e nunca é reexibido. Vale para qualquer
  plataforma: API, servidor MCP, banco de dados, bot do Telegram, certificado digital, conta de serviço
  do Google.
- **Chave de IA da organização** — os prontos de uma IA (gerar imagem, vídeo, narrar, ler documento…)
  usam a chave daquela IA cadastrada em **Chaves de IA**, sem recadastrar. Veja [[segredos/chaves-de-ia]].

Desde 2026-10-02 **não existe mais** cadastro de credencial separado ("caixa-forte"/"credencial da
central") nem o botão "Conectar Google" na página de chaves. Quem precisa de Google usa a **conta de
serviço** no Construtor.

## Como usar (na tela)
1. No instrumento, os campos secretos aparecem com cadeado — preenchidos, vão cifrados e nunca voltam
   à tela (só os últimos dígitos). Ao editar, deixar em branco **mantém** o atual.
2. Nos prontos de IA, o campo de chave pode ficar **em branco** — o Batuta usa a chave de IA da organização.
3. Instrumento **da organização** (um instrumento usado por vários times) guarda o segredo uma vez só;
   para trocar, edita-se esse instrumento.

## Exemplos
- Conector de uma API com token → o token vai no passo de identificação do Construtor.
- Servidor MCP do WordPress → usuário + senha de aplicativo dentro do instrumento.
- `gerar_imagem` → chave da OpenAI da organização (campo em branco).

## Limites e cuidados
- Segredos **nunca** voltam à tela (só os últimos dígitos).
- **Duplicar** o time não copia segredos — a cópia nasce a reconectar.
- Um instrumento sem o segredo **falha com recado claro** ao rodar.

## Para a IA
Você nunca vê nem digita segredo. Ao montar um instrumento que precisa de um, deixe-o **pendente** e
avise o humano para preencher **no próprio instrumento**, na tela do time — não mande cadastrar
"credencial" em outra página (ela não existe mais). Não diga "pronto" enquanto faltar.

## Relacionado
- [[segredos/chaves-de-ia]]
- [[segredos/certificado-digital-mtls]]
- [[instrumentos/cinto]]
