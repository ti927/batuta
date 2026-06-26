# Instruções — Concluir o App Review do Instagram na Meta

> **Documento de apoio para o maestro.** Guarda tudo o que falta para terminar o envio do app à
> análise da Meta (App Review do Instagram).
>
> ⚠️ **Só execute os passos abaixo DEPOIS que a "Verificação da empresa" for APROVADA**
> (o status muda de **"Em análise"** para verificado, ~2 dias úteis). Antes disso, o botão
> **"Enviar para análise"** fica bloqueado.

---

## Onde estamos (contexto, atualizado em 26/06/2026)

- **App:** Batuta Team — App ID `1521228536398165` — status **Publicado/Live**.
- **Caso de uso:** "Gerenciar mensagens e conteúdo no Instagram", via **API com login do Instagram**
  (`graph.instagram.com`, conexão por **token colado** gerado no painel da Meta).
- **Empresa verificada / controladora oficial:** **JMF TREINAMENTOS E CONSULTORIA LTDA - ME**
  (CNPJ `56.923.834/0001-23`). As páginas legais já estão neste nome:
  - Política de Privacidade → https://batuta.team/privacidade
  - Termos de Uso → https://batuta.team/termos
  - Exclusão de Dados → https://batuta.team/exclusao-de-dados
- **Verificação da empresa:** ✅ **ENVIADA** sob a JMF — aguardando aprovar ("Em análise").
- **Permissões enviadas ao review (4):** `instagram_business_basic`,
  `instagram_business_content_publish`, `instagram_business_manage_comments`,
  `instagram_business_manage_insights`.
- **Removidas do envio (de propósito):** `instagram_business_manage_messages` + `Human Agent`
  (mensagens diretas/DM — o Batuta **não faz DM ainda**; sem como demonstrar em vídeo = reprovação
  certa). Adicionar no futuro, quando construirmos o DM.
- **"Configurações do app"** do review já ✅ (as URLs legais cobrem este item).

---

## Pré-requisito antes de gravar os vídeos

- Tenha uma **conta profissional (Business/Criador)** de Instagram de **TESTE**, adicionada como
  testadora do app e **conectada no Batuta**.
- Cada vídeo (1–3 min, **sem cortes que escondam passos**) deve mostrar:
  **(1)** o Batuta logado → **(2)** a conta do Instagram conectada → **(3)** a ação acontecendo →
  **(4)** o resultado (de preferência abrindo o Instagram e mostrando o efeito real).

---

## Passo a passo na tela "Enviar para a análise do app"

1. **Verificação** — aguardar aprovar (✅ já enviada).
2. **Configurações do app** — ✅ já feito.
3. **Uso permitido** — para CADA uma das 4 permissões, clicar **"Começar"** e:
   colar a **descrição** (abaixo) + subir o **vídeo** (roteiro abaixo) + marcar **conformidade**.
4. **Tratamento de dados** — concordar com os termos de tratamento de dados da Meta.
5. **Instruções para o analista** — fornecer **passo a passo + credenciais de teste** para o
   analista reproduzir as funções (ver modelo no fim deste doc).
6. **Enviar para análise**.

---

## Os 4 textos (colar) + roteiro de cada vídeo

### 1. `instagram_business_basic`

**Descrição (colar):**
> O Batuta é uma plataforma que permite a uma empresa montar times de agentes de IA para gerenciar a
> própria conta profissional do Instagram. O app usa a `instagram_business_basic` para identificar e
> ler os dados básicos da conta profissional que a empresa conectou — nome de usuário, tipo de conta e
> a lista de mídias publicadas — exibindo essas informações no painel e usando-as como base para as
> demais funções (publicar, ler métricas e gerenciar comentários). É a permissão fundamental: sem ela
> o app não identifica a conta nem associa as ações às mídias corretas. Os dados são usados apenas para
> operar as funcionalidades que a própria empresa aciona; não são vendidos nem usados para perfis de
> publicidade.

**Roteiro do vídeo:**
1. Batuta logado → tela onde a empresa conecta o Instagram (credencial "Instagram", onde cola o token
   gerado no painel da Meta).
2. Mostrar o app reconhecendo a conta (aparece o usuário / ID da conta).
3. Rodar o instrumento "Instagram — conteúdo e métricas" lendo a conta.
4. Mostrar na tela os dados retornados (usuário, tipo de conta, mídias).

### 2. `instagram_business_content_publish`

**Descrição (colar):**
> O Batuta usa a `instagram_business_content_publish` para publicar conteúdo na conta profissional que
> a empresa conectou — fotos, Reels, Stories e carrosséis — a partir das automações que a empresa cria.
> Fluxo: a empresa (ou um agente de IA) prepara a imagem e a legenda; antes de qualquer publicação, o
> Batuta exige uma aprovação humana (portão de aprovação) por ser uma ação irreversível; uma vez
> aprovado, o app cria o contêiner de mídia e o publica pela API do Instagram. A permissão é central à
> proposta do produto: automatizar a publicação de conteúdo da própria empresa, sempre com revisão
> humana. Publica somente na conta que a empresa conectou e autorizou.

**Roteiro do vídeo:**
1. Mostrar uma automação que prepara um post (imagem + legenda).
2. Mostrar o **portão de aprovação** — o operador aprova.
3. Batuta publica.
4. Abrir o Instagram da conta de teste e mostrar **o post publicado** (ponta a ponta).

### 3. `instagram_business_manage_comments`

**Descrição (colar):**
> O Batuta usa a `instagram_business_manage_comments` para ler os comentários das publicações da conta
> profissional conectada e, quando a empresa decide, responder, ocultar, reexibir ou apagar comentários
> — ajudando a empresa a cuidar do relacionamento com o público. As respostas são sugeridas pelos
> agentes de IA e enviadas em nome da conta da empresa, sempre sob controle dela. O texto e o nome de
> usuário do autor do comentário são usados apenas para exibir e responder dentro do contexto da conta
> da empresa; não são vendidos nem usados para outras finalidades.

**Roteiro do vídeo:**
1. Batuta lendo os comentários de um post da conta de teste (instrumento "Ler comentários").
2. Agente/operador respondendo a um comentário (instrumento "Responder/moderar comentário").
3. Abrir o Instagram e mostrar **a resposta publicada** no comentário (ponta a ponta).

### 4. `instagram_business_manage_insights`

**Descrição (colar):**
> O Batuta usa a `instagram_business_manage_insights` para ler as métricas da conta profissional
> conectada e das suas publicações — alcance, curtidas, comentários e outras estatísticas —
> apresentando esses números no painel para que a empresa acompanhe o desempenho do conteúdo. Os
> agentes de IA também usam essas métricas para orientar as próximas ações de conteúdo. Os dados
> pertencem à própria conta da empresa e são usados apenas para relatórios e decisões dentro do app.

**Roteiro do vídeo:**
1. Batuta rodando o instrumento "Instagram — conteúdo e métricas" (insights).
2. Mostrar as métricas retornadas (alcance, curtidas, comentários por post + visão da conta).
3. Mostrar onde elas aparecem para a empresa.

---

## Modelo para "Instruções para o analista" (passo 5)

> Forneça uma **conta de teste do Batuta** (login + senha) e descreva como chegar a cada função.
> Modelo (ajustar os nomes reais das telas):

```
Acesso de teste:
- App: https://batuta.team  | Login: <email de teste>  | Senha: <senha de teste>
- A conta de Instagram de teste já está conectada nesta organização.

Como reproduzir cada permissão:
1. instagram_business_basic / manage_insights:
   Abra o time > aba Instrumentos > rode "Instagram — conteúdo e métricas".
   Mostra os dados da conta e as métricas dos posts.
2. instagram_business_content_publish:
   Abra a automação "<nome>" > Rodar. O agente prepara um post; aprove no portão.
   O post aparece na conta de Instagram de teste.
3. instagram_business_manage_comments:
   Rode "Ler comentários" no post X; depois "Responder/moderar comentário" para responder.
   A resposta aparece no Instagram.
```

---

## Avisos honestos

- **Conexão por token colado (não OAuth).** Se o analista perguntar como o acesso é concedido: o token
  é **gerado no painel da Meta da própria empresa e colado no Batuta** (mostre a tela da credencial no
  vídeo do item 1). Se a Meta **exigir** o fluxo de login na tela, aí entra a **fase futura "Conectar
  Instagram" (OAuth)** — ver `docs`/memória `project-instagram-oauth-app-review-fase-futura`.
- **Idioma:** os textos estão em PT-BR. Se algum analista internacional pedir, dá para traduzir para EN.
- **Não é aconselhamento jurídico:** as páginas legais são um modelo factual; recomenda-se revisão por
  advogado para uso definitivo.

## Motivos comuns de rejeição (e como já tratamos)

- **Descrição vaga** → usar as descrições específicas acima.
- **Vídeo que não mostra a função de ponta a ponta** → sempre mostrar o resultado real no Instagram.
- **Pedir permissão sem como demonstrar** → por isso removemos as de DM (`manage_messages` + Human Agent).
- **Empresa verificada ≠ controladora da política** → já resolvido (tudo no nome da **JMF**).
