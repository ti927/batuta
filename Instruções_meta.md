# Instruções — Concluir o App Review do Instagram na Meta

> **Documento de apoio para o maestro.** Guarda tudo o que falta para terminar o envio do app à
> análise da Meta (App Review do Instagram).
>
> ⚠️ **Só execute os passos abaixo DEPOIS que a "Verificação da empresa" for APROVADA**
> (o status muda de **"Em análise"** para verificado, ~2 dias úteis). Antes disso, o botão
> **"Enviar para análise"** fica bloqueado.

---

> **STATUS 2026-07-07 — quase enviando.** Empresa verificada (JMF). Ambiente de teste montado (org
> "Testes Meta", login do analista, @arrastafaca conectada, 3 automações Postar/Responder/Métricas).
> Na tela "Enviar para a análise": Verificação · Configurações · Tratamento de dados · Instruções ✅.
> **Uso permitido** com as 4 descrições + 4 vídeos subidos. Falta só a Meta registrar as **2 chamadas
> de API de teste** (insights + comentários) — feitas ao rodar as automações, mas leva **até 24h** para
> marcar `1/1`; aí o "Enviar para análise" acende. Comentários teve exigência extra (vídeo com usuário
> comentando + resposta; descrição com link do post + palavras-chave) — atendida.

## Onde estamos (contexto, atualizado em 26/06/2026)

- **App:** Batuta Team — App ID `1521228536398165` — status **Publicado/Live**.
- **Caso de uso:** "Gerenciar mensagens e conteúdo no Instagram", via **API com login do Instagram**
  (`graph.instagram.com`). Conexão da conta pelo botão **"Conectar Instagram"** (OAuth Business Login,
  já no ar); alternativamente, o token pode ser colado.
- **Empresa verificada / controladora oficial:** **JMF TREINAMENTOS E CONSULTORIA LTDA - ME**
  (CNPJ `56.923.834/0001-23`). As páginas legais já estão neste nome:
  - Política de Privacidade → https://batuta.team/privacidade
  - Termos de Uso → https://batuta.team/termos
  - Exclusão de Dados → https://batuta.team/exclusao-de-dados
- **Verificação da empresa:** ✅ **APROVADA** sob a JMF (o botão "Enviar para análise" está liberado).
- **Permissões enviadas ao review (4):** `instagram_business_basic`,
  `instagram_business_content_publish`, `instagram_business_manage_comments`,
  `instagram_business_manage_insights`.
- **Removidas do envio (de propósito):** `instagram_business_manage_messages` + `Human Agent`
  (mensagens diretas/DM — o Batuta **não faz DM ainda**; sem como demonstrar em vídeo = reprovação
  certa). Adicionar no futuro, quando construirmos o DM.
- **"Configurações do app"** do review já ✅ (as URLs legais cobrem este item).

---

## Como chegar até a tela de envio (caminho de clique)

> **Use este caminho sempre que se perder.** Painel da Meta = `developers.facebook.com`.
> (A Meta muda a interface de tempos em tempos; se um rótulo estiver diferente, procure o equivalente.)

1. **`developers.facebook.com`** → topo **"Meus apps"** → abra **"Batuta Team"**.
2. Menu da **esquerda** → **"Casos de uso"**.
3. No card **"Gerenciar mensagens e conteúdo no Instagram"** → clique para abrir/**"Personalizar"**.
4. No sub-menu da esquerda → **"Configuração da API com login do Instagram"** (a tela com os
   **passos numerados de 1 a 5**).
5. Role até o **passo 5, "Concluir a análise do app"** → botão **"Ir para Análise do app"**.
6. Se aparecer o aviso "A análise do app mudou" → **"Continuar para a análise do app"**.
7. Se cair na lista de permissões ("Envios de análise do app" → "Novas solicitações"): confira que são
   as **4** (sem as de DM) e clique **"Avançar"**.
8. Você chega na tela **"Enviar para a análise do app"** — a dos **5 itens** no topo:
   **Verificação · Configurações do app · Uso permitido · Tratamento de dados · Instruções para o
   analista**. **Esta é a tela-base de tudo.**

> Nessa tela-base: cada item tem um botão **"Ir para..."**. O botão **"Enviar para análise"**
> (canto inferior direito) só fica clicável quando **todos** os itens estiverem ✅.
>
> **Conferir se a verificação já aprovou:** o item **"Verificação"** no topo deixa de estar pendente
> e vira ✅. (Alternativa: `business.facebook.com` → engrenagem **Configurações** → **Central de
> Segurança** → card **"Verificação da empresa"** — sai de "Em análise".)

---

## Pré-requisito antes de gravar os vídeos

- Tenha uma **conta profissional (Business/Criador)** de Instagram de **TESTE**, adicionada como
  testadora do app e **conectada no Batuta**.
- Cada vídeo (1–3 min, **sem cortes que escondam passos**) deve mostrar:
  **(1)** o Batuta logado → **(2)** a conta do Instagram conectada → **(3)** a ação acontecendo →
  **(4)** o resultado (de preferência abrindo o Instagram e mostrando o efeito real).

---

## Passo a passo na tela "Enviar para a análise do app"

> A partir da **tela-base dos 5 itens** (caminho na seção acima). Faça na ordem; cada item tem o seu
> botão **"Ir para..."**.

1. **Verificação** — aguardar aprovar (✅ já enviada). Quando o item virar ✅, siga.
2. **Configurações do app** — ✅ já feito; **não precisa mexer**.
3. **Uso permitido** — clique **"Ir para o uso permitido"**. Para CADA uma das **4 permissões**
   (cada card tem o nome da permissão), clique **"Começar"** → **cole a descrição** (abaixo) →
   **suba o vídeo** (roteiro abaixo) → **marque a conformidade** → salve/volte. **Repita nas 4.**
   Ao terminar, **"Avançar"**.
4. **Tratamento de dados** — clique **"Ir para o tratamento de dados"** → leia e **concorde** com os
   termos. Se pedir uma **URL de exclusão de dados**, informe `https://batuta.team/exclusao-de-dados`
   (e a política de privacidade `https://batuta.team/privacidade`) → **"Avançar"**.
5. **Instruções para o analista** — clique **"Ir para as instruções da análise"** → preencha o
   **acesso de teste + passo a passo** (modelo no fim deste doc) → salve.
6. Com os **5 itens ✅** → clique **"Enviar para análise"** (canto inferior direito).

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
1. Batuta logado → tela de credenciais da organização → clicar em **"Conectar Instagram"**.
2. Mostrar a tela de autorização do Instagram (login + consentimento) → autorizar.
3. Voltar ao Batuta com a conta conectada (banner verde, aparece o usuário da conta).
4. Rodar o instrumento "Instagram — conteúdo e métricas" e mostrar os dados retornados
   (usuário, tipo de conta, mídias).

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
- App: https://batuta.team/login  | Login: <EMAIL DE TESTE>  | Senha: <SENHA DE TESTE>
- Organização de teste "Testes Meta", com a conta de Instagram de teste (@arrastafaca) já conectada.

Como reproduzir cada permissão:
1. instagram_business_basic:
   Tela de credenciais > "Conectar Instagram" (o app reconhece e exibe a conta).
2. instagram_business_content_publish:
   Abra a automação "Instagram - Postar" > Rodar. O agente gera imagem + legenda; aprove no portão;
   o post aparece na conta de teste.
3. instagram_business_manage_comments:
   Abra a automação "Instagram - Responder" > Rodar: lê os comentários de um post e responde
   (a resposta passa pelo portão de aprovação antes de ir ao ar).
4. instagram_business_manage_insights:
   Abra a automação "Instagram - Métricas" > Rodar: alcance, curtidas e comentários da conta e posts.
```

---

## Avisos honestos

- **Conexão via "Conectar Instagram" (OAuth Business Login).** Já está no ar: o analista conecta a
  conta pelo botão **"Conectar Instagram"** (é o que a Meta pediu para a `basic`). Mostre esse fluxo no
  vídeo do item 1. O token colado continua funcionando como alternativa.
- **Idioma:** os textos estão em PT-BR. Se algum analista internacional pedir, dá para traduzir para EN.
- **Não é aconselhamento jurídico:** as páginas legais são um modelo factual; recomenda-se revisão por
  advogado para uso definitivo.

## Motivos comuns de rejeição (e como já tratamos)

- **Descrição vaga** → usar as descrições específicas acima.
- **Vídeo que não mostra a função de ponta a ponta** → sempre mostrar o resultado real no Instagram.
- **Pedir permissão sem como demonstrar** → por isso removemos as de DM (`manage_messages` + Human Agent).
- **Empresa verificada ≠ controladora da política** → já resolvido (tudo no nome da **JMF**).
