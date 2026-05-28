# Batuta — Design System

Documento vivo da identidade visual da Batuta. Atualizar sempre que uma decisão de marca for tomada ou refinada. Este é o documento que **designers, devs e profissionais de marketing consultam** antes de produzir qualquer artefato visual ou textual da marca.

**Última atualização:** maio de 2026
**Versão:** 1.0 (inicial)

---

## 1. Marca

### Nome

**Batuta**

Pronúncia: ba-TU-ta (sílaba tônica no meio).

A batuta é a varinha que o maestro de orquestra usa pra coordenar músicos. Metáfora central do produto: **o usuário é o maestro, os agentes de IA são a orquestra, a Batuta é o instrumento que faz tudo se conectar**.

### Tagline principal

**"Você guia. A IA executa."**

Usa em: header da landing page, OG image, anúncios curtos, assinatura de email, app store description.

### Taglines secundárias (contextos diferentes)

- **"Seu time de IA, conduzido por você."** — quando precisar explicar um pouco mais (subhead da landing, descrição em diretórios)
- **"Orquestre agentes de IA. Sem complicação."** — quando o público é menos técnico e precisa entender o que é (anúncios pra leigo absoluto)
- **"Conecte agentes. Orquestre resultados."** — pra contexto mais business/produtividade

### Proposta de valor em uma frase

"A Batuta deixa qualquer pessoa criar e gerenciar um time de assistentes de IA que respondem clientes no WhatsApp, geram conteúdo e automatizam tarefas — sem precisar saber programar."

### Posicionamento

Pra quem é: pequeno empresário, freelancer, profissional liberal brasileiro que quer aproveitar IA mas não é técnico.

Contra quem competimos: planilha + WhatsApp do celular pessoal + ChatGPT free + funcionário/estagiário sobrecarregado.

Não competimos com: Paperclip (público dev), n8n (público técnico), CrewAI (público dev).

---

## 2. Personalidade da marca

### Atributos

A Batuta é:

- **Acolhedora** — não intimida, não joga jargão na cara, recebe leigo
- **Confiante** — não pede desculpas pelo que é, mostra capacidade
- **Brincalhona com moderação** — usa sparkle, emoji, ilustração quando cabe; nunca infantiliza
- **Brasileira** — fala português de gente real, não tradução literal do inglês
- **Discreta** — flat design, sem efeitos exagerados, sem ruído visual

A Batuta NÃO é:

- Corporativa fria
- Hype futurista ("revolucionária", "disruptiva", "next-gen")
- Sisuda
- Boba ou infantilizada
- Vendedora de feira ("clique agora!", "última chance!")

### Tom de voz

#### Princípios

1. **Direto mas acolhedor.** "Vamos criar seu primeiro time" ✅ — "Bora montar a rapaziada de IA" ❌
2. **Sem jargão técnico** em texto pro usuário final. Se aparecer "API", "endpoint", "webhook", "cron", "deploy", é falha de tradução.
3. **Primeira pessoa do plural** pra ação do sistema ("Estamos preparando seu time..."). **Segunda pessoa do singular** pra instrução ao usuário ("Configure seu WhatsApp aqui").
4. **Empatia em erros.** Nunca código de erro nu. Sempre explicação humana + próximo passo.
5. **Sentence case** em tudo. Nunca Title Case, nunca ALL CAPS. ALL CAPS só em badges minúsculas de status (ex: `NOVO`, `BETA`) e mesmo aí com moderação.

#### Exemplos lado a lado

| Contexto | Errado | Certo |
|---|---|---|
| Botão de salvar | OK | Salvar time |
| Erro 500 | Internal Server Error | Algo deu errado do nosso lado. Já estamos olhando — tenta de novo em alguns instantes. |
| Empty state | No teams found | Você ainda não tem times. Crie o primeiro pra começar. |
| Configurando | Loading... | Estamos preparando seu time... |
| Confirmação destrutiva | Are you sure? | Tem certeza? Essa ação não pode ser desfeita. |
| CTA principal | Click here | Criar meu primeiro time |
| Sucesso | Saved! | Time criado ✨ |
| Termo técnico | Configurar webhook | Conectar com seu WhatsApp |
| Sobre cota | Quota exceeded | Você atingiu o limite mensal. Faça upgrade ou aguarde a renovação. |

#### Vocabulário oficial (sempre usar)

Quando traduzir de termos técnicos do Paperclip ou de IA em geral:

| Termo evitado | Termo Batuta |
|---|---|
| Agente | Assistente |
| Skill | Habilidade |
| Company / workspace | Time |
| Task | Tarefa |
| Trigger | Gatilho ou "Quando isso acontecer" |
| Heartbeat | Verificação automática |
| Budget | Limite de gastos |
| Pipeline | Sequência |
| Hire / fire | Adicionar / remover |
| Library | Biblioteca |
| Prompt | Instruções |
| LLM / model | Modelo de IA (ou só "IA" quando contexto permitir) |
| Token | Não mencionar pro usuário final |
| API key | Não mencionar pro usuário final |

---

## 3. Identidade visual

### Logo

#### Logo principal — com mascot

Maestro estilizado segurando batuta, conduzindo robozinhos amigáveis ao redor. Versão completa pra **marketing e contextos emocionais**.

**Uso:**
- Landing page (hero section)
- Redes sociais (perfil, posts)
- Email marketing
- Materiais impressos e cards
- Onboarding (tela de boas-vindas)

**Não usar em:**
- Header da aplicação
- Documentação técnica
- Contextos onde mascot seria distração

#### Logotipo — apenas tipografia

A palavra "Batuta" em Bricolage Grotesque Semibold (600), preta em fundo claro ou off-white em fundo escuro. Versão funcional pra **dentro do produto**.

**Uso:**
- Header da aplicação web
- Footer
- Documentação
- Contextos onde precisa apenas identificar a marca sem decoração

#### Símbolo — só o ícone

Batuta diagonal estilizada com um pequeno sparkle (ponto brilhante) na ponta. Cores: roxo `#6D4AFF` com acento amarelo `#F5C44A` no sparkle.

**Uso:**
- Favicon (16x16, 32x32)
- Ícone do app em celular (192x192, 512x512)
- Avatar em redes sociais quando precisa compactar
- Tela de loading do app
- Watermark sutil em screenshots de marketing

**Tamanhos obrigatórios pra entrega:**
- SVG (vetorial, base de tudo)
- PNG 32x32 (favicon padrão)
- PNG 192x192 (PWA Android)
- PNG 512x512 (PWA padrão)
- PNG 1024x1024 (App Store, alta resolução)
- ICO 16x16 + 32x32 (favicon legado)

### Área de respiro do logo

Mínimo de espaço livre ao redor do logo igual à altura da letra "B". Em headers e contextos compactos, nunca apertar.

### O que não fazer com o logo

- ❌ Esticar ou comprimir desproporcionalmente
- ❌ Trocar as cores do logo principal (mascot mantém paleta original)
- ❌ Adicionar contorno ou sombra
- ❌ Usar sobre fundos com pouca legibilidade
- ❌ Girar
- ❌ Recriar o mascot em outros estilos sem aprovação

---

## 4. Paleta de cores

### Cores primárias

**Roxo Batuta** — cor da marca
- Hex: `#6D4AFF`
- RGB: 109, 74, 255
- Uso: botões primários, links, header destacado, hover states, sparkles, gravata-borboleta do mascot
- Variações:
  - Hover: `#5A3FE0`
  - Light (backgrounds suaves): `#EFEAFF`
  - Subtle text (sobre fundo light primário): `#3D2A99`

**Off-white Maestro** — fundo claro padrão
- Hex: `#FAFAF7`
- RGB: 250, 250, 247
- Uso: fundo principal em light mode (não usar branco puro)

**Roxo Escuro** — fundo escuro padrão
- Hex: `#1A1730`
- RGB: 26, 23, 48
- Uso: fundo principal em dark mode, texto principal em light mode

### Cores secundárias

**Ciano Maestro** — acento amigável
- Hex: `#3DD8C3`
- Uso: badges informativos, ícones secundários, estados ativos sutis, robozinho azul no mascot

**Amarelo Aplauso** — destaque positivo
- Hex: `#F5C44A`
- Uso: badges "Novo!", sparkles, call-to-action secundário, robozinho amarelo do mascot

**Lilás Suave** — neutro com personalidade
- Hex: `#B19CD9`
- Uso: ilustrações secundárias, separadores temáticos

### Cores de estado

**Sucesso — Verde Sereno**
- Hex: `#3DAA5C`
- Light: `#E6F4EA`
- Uso: confirmações, status "ativo", checkmarks

**Atenção — Laranja Suave**
- Hex: `#E89638`
- Light: `#FDF1E3`
- Uso: avisos, "quase no limite", próximo de expirar

**Erro — Vermelho Coral**
- Hex: `#E5484D`
- Light: `#FDECEC`
- Uso: erros, ações destrutivas, falhas. **Não usar vermelho mais agressivo** — fica hostil pro público leigo.

### Neutros

**Light mode:**
- Fundo principal: `#FAFAF7` (off-white)
- Fundo elevado (cards): `#FFFFFF`
- Texto principal: `#1A1730`
- Texto secundário: `#6B6880`
- Texto desabilitado: `#A09DB8`
- Bordas: `#E8E6F0`
- Bordas com ênfase: `#D6D3E8`

**Dark mode:**
- Fundo principal: `#1A1730`
- Fundo elevado (cards): `#252140`
- Texto principal: `#FAFAF7`
- Texto secundário: `#9D9AB5`
- Texto desabilitado: `#5D5A75`
- Bordas: `#2D2A45`
- Bordas com ênfase: `#3D3A55`

### Regras de uso de cor

- **Roxo Batuta é precioso.** Usa em CTAs primários, links importantes, momentos de marca. Não inundar a tela com ele.
- **Contraste mínimo 4.5:1** entre texto e fundo, sempre. Testar com ferramenta como webaim.org/resources/contrastchecker.
- **Acessibilidade**: nunca depender só de cor pra comunicar (ex: status com ícone + cor, não só cor).
- **Estado de erro nunca isolado**: sempre acompanhado de texto explicativo.

---

## 5. Tipografia

### Famílias

**Inter** — fonte de interface (UI)
- Google Fonts: https://fonts.google.com/specimen/Inter
- Uso: todo o app, formulários, dashboards, botões, labels, body text
- Pesos a carregar: 400 (Regular), 500 (Medium)
- Por que: excelente legibilidade em telas pequenas, alto reconhecimento, padrão da indústria pra interfaces modernas

**Bricolage Grotesque** — fonte de marca (headlines)
- Google Fonts: https://fonts.google.com/specimen/Bricolage+Grotesque
- Uso: logotipo, títulos grandes de landing page, hero sections, capas de email
- Pesos a carregar: 500 (Medium), 600 (Semibold)
- Por que: tem personalidade sem ser barulhenta, casa com o tom moderno-mas-acessível da Batuta

### Hierarquia tipográfica

#### Em landing page e marketing

| Estilo | Fonte | Peso | Tamanho | Line height |
|---|---|---|---|---|
| Hero title | Bricolage Grotesque | 600 | 56px (mobile 36px) | 1.1 |
| Section title | Bricolage Grotesque | 600 | 40px (mobile 28px) | 1.15 |
| Subtitle | Bricolage Grotesque | 500 | 24px | 1.3 |
| Body large | Inter | 400 | 18px | 1.6 |
| Body | Inter | 400 | 16px | 1.6 |
| Caption | Inter | 400 | 14px | 1.5 |

#### Dentro do app

| Estilo | Fonte | Peso | Tamanho | Line height |
|---|---|---|---|---|
| Page title (h1) | Inter | 500 | 24px | 1.3 |
| Section title (h2) | Inter | 500 | 18px | 1.4 |
| Subsection (h3) | Inter | 500 | 16px | 1.5 |
| Body | Inter | 400 | 14-16px | 1.5 |
| Label de formulário | Inter | 500 | 14px | 1.4 |
| Caption / helper | Inter | 400 | 12px | 1.4 |
| Botão | Inter | 500 | 14px | 1.0 |

### Regras de tipografia

- **Sentence case sempre.** Nunca Title Case ("Criar Novo Time" ❌ → "Criar novo time" ✅), nunca ALL CAPS (exceto badges minúsculas estilo `NOVO`).
- **Só dois pesos: 400 e 500.** Bold (700+) é proibido na UI do app — fica pesado demais e quebra a leveza da marca. Em landing page e capas de email, Semibold (600) é OK pra headlines.
- **Itálico é raro.** Usa só pra citação literal ou termo estrangeiro.
- **Sublinhado só em links.** Nunca pra dar ênfase.
- **Tipografia respira.** Line height generoso (1.5-1.6 em body), letter spacing default da fonte.

---

## 6. Espaçamento e layout

### Escala de espaçamento

Baseada em múltiplos de 4px, seguindo a escala do Tailwind:

| Token | Pixels | Uso típico |
|---|---|---|
| `space-1` | 4px | Espaçamento interno mínimo |
| `space-2` | 8px | Entre ícone e texto, padding de badge |
| `space-3` | 12px | Padding pequeno em botão, gap entre itens próximos |
| `space-4` | 16px | Padding padrão de input, gap entre cards relacionados |
| `space-6` | 24px | Padding de card, gap entre seções |
| `space-8` | 32px | Margin entre blocos maiores |
| `space-12` | 48px | Separação entre seções em landing page |
| `space-16` | 64px | Hero section, espaços generosos |

### Container max-widths

- Landing page: `max-w-7xl` (1280px), centralizado
- App content: `max-w-6xl` (1152px), centralizado
- Modal: `max-w-md` (448px) pra simples, `max-w-2xl` (672px) pra complexo
- Formulário simples: `max-w-md` (448px)

### Princípios de layout

- **Mobile-first sempre.** TODA tela testada em 375px antes de ajustar pra desktop.
- **Respiro generoso.** O produto é pra leigo — aperto visual transmite "complicado". Padding mínimo de 16px em cards, 24-32px em containers.
- **Hierarquia visual clara.** Uma ação primária por tela (botão roxo). Outras ações ficam secundárias (outline, ghost).
- **Densidade controlada.** Não enche tela de informação. Se precisar muito conteúdo, divide em abas ou steps.

---

## 7. Bordas, sombras e cantos

### Border radius

| Token | Valor | Uso |
|---|---|---|
| `rounded-sm` | 4px | Badges, chips pequenos |
| `rounded-md` | 6px | Botões, inputs, selects |
| `rounded-lg` | 8px | Cards, modais |
| `rounded-xl` | 12px | Containers destacados (raro) |
| `rounded-full` | 999px | Avatares, pills, badges arredondados |

### Bordas

- Padrão: `1px solid var(--border)`
- Cor da borda: `#E8E6F0` (light), `#2D2A45` (dark)
- Borda em hover: `#D6D3E8` (light), `#3D3A55` (dark)
- Nunca borda de 2px+ em UI de produção — fica pesado.

### Sombras

**Filosofia: quase nenhuma sombra.** Flat design é o padrão da Batuta.

| Token | Valor | Uso |
|---|---|---|
| `shadow-none` | nenhuma | Cards padrão (regra) |
| `shadow-sm` | sutil | Modais, dropdowns, popovers |
| `shadow-md` | leve | Tooltips, popovers elevados |

**Nunca usar `shadow-lg` ou maior.** Sombras pesadas brigam com a estética leve.

---

## 8. Iconografia

### Biblioteca oficial

**lucide-react** (https://lucide.dev) — única biblioteca de ícones permitida no produto.

Por que: já vem incluída no shadcn/ui (e portanto no Paperclip), consistente, gratuita, muito completa, peso de linha uniforme.

### Tamanhos padrão

- Pequeno (em chip, badge, inline): 14px
- Padrão (em botão, label): 18px
- Médio (header, destaque): 20px
- Grande (empty state, ilustrativo): 32-48px

### Peso de linha

Sempre 1.5px (default do lucide). Nunca misturar com ícones de outro pacote (Font Awesome, Heroicons, etc.) — quebra a consistência.

### Ícones favoritos (referência)

Ícones que aparecem com frequência no produto e devem ser usados consistentemente:

| Conceito | Ícone Lucide |
|---|---|
| Time / grupo | `users` |
| Assistente / agente | `bot` |
| Habilidade / skill | `sparkles` (com cor roxa) |
| Biblioteca | `library` ou `folder` |
| Gatilho / trigger | `zap` |
| WhatsApp | `message-circle` ou logo oficial do WhatsApp |
| Imagem gerada | `image` |
| Tarefa em execução | `loader` (animado) |
| Sucesso | `check-circle-2` |
| Erro | `x-circle` |
| Aviso | `alert-circle` |
| Configurações | `settings` |
| Adicionar | `plus` |
| Editar | `pencil` |
| Deletar | `trash-2` |

### Uso de sparkles ✨

Importado direto do mascot pra UI, **com moderação**. Usar ao lado de:

- Coisas geradas por IA: "Resposta gerada ✨", "Imagem criada ✨"
- Momentos de "magia" do produto: setup completo, primeiro time funcionando

**Não usar em:** ações técnicas, erros, processos lentos, lugares onde já tem muito visual.

---

## 9. Componentes-chave

### Botões

#### Primário (roxo)
- Fundo: `#6D4AFF`, texto branco
- Hover: `#5A3FE0`
- Tamanho padrão: `h-10` (40px altura), padding `px-4`
- Border radius: `rounded-md`
- Peso de fonte: 500
- **Uso:** uma vez por tela, na ação principal. Nunca dois primários competindo.

#### Secundário (outline)
- Fundo transparente, borda `1px solid #E8E6F0`, texto `#1A1730`
- Hover: fundo `#FAFAF7`
- **Uso:** ações secundárias, "Cancelar", alternativas

#### Ghost (sem borda)
- Fundo transparente, texto `#1A1730`
- Hover: fundo `#F0EDF7` muito sutil
- **Uso:** ações terciárias, navegação, itens de menu

#### Destrutivo
- Fundo `#E5484D` (Vermelho Coral), texto branco
- Hover: tom mais escuro do vermelho
- **Uso:** apenas deleção, sempre dentro de AlertDialog de confirmação

### Inputs

- Altura padrão: `h-10`
- Border radius: `rounded-md`
- Border: `1px solid #E8E6F0`
- Focus: borda roxa `#6D4AFF`, anel suave `ring-2 ring-purple-100`
- Placeholder: `#A09DB8`
- Label sempre acima, em peso 500, 14px

### Cards

- Background: `#FFFFFF` (light) ou `#252140` (dark)
- Border: `1px solid #E8E6F0` (light) ou `#2D2A45` (dark)
- Border radius: `rounded-lg`
- Padding interno: `p-6` (24px) por padrão, `p-4` em cards compactos
- Sem sombra

### Badges

- Padding: `px-2 py-0.5`
- Border radius: `rounded-full`
- Tamanho de fonte: 12px, peso 500
- Variações por contexto:
  - Informativo: fundo `#EFEAFF`, texto `#3D2A99` (light purple)
  - Sucesso: fundo `#E6F4EA`, texto `#3DAA5C` (light green)
  - Atenção: fundo `#FDF1E3`, texto `#E89638` (light orange)
  - Erro: fundo `#FDECEC`, texto `#E5484D` (light red)

### Toasts (notificações)

Biblioteca: `sonner` (já vem no shadcn/ui).

- Posição padrão: bottom-right (desktop), bottom-center (mobile)
- Duração padrão: 4 segundos
- Sucesso: ícone `check-circle-2` verde, mensagem curta
- Erro: ícone `x-circle` vermelho, mensagem + sugestão de ação
- Info: ícone `info` roxo

---

## 10. Ilustração e imagens

### Estilo do mascot

O mascot oficial segue o estilo do logo "número 2" do briefing:

- Personagem humano feliz (maestro), traços simples e amigáveis
- Robozinhos coloridos arredondados, com expressão de felicidade/curiosidade
- Paleta consistente com a paleta da marca (roxo, ciano, amarelo, lilás)
- Fundo claro off-white ou cenas com gradiente sutil
- Sparkles e elementos mágicos com moderação

**Quando expandir o universo do mascot** (mais ilustrações tipo onboarding, ilustrações de empty state, etc.), manter o mesmo ilustrador ou o mesmo estilo. Não misturar com outros estilos (foto realista, 3D, isométrico) na mesma marca.

### Imagens em landing page

- Screenshots reais do produto sempre que possível
- Evitar stock photos genéricas de "pessoas de negócio sorrindo segurando notebook"
- Quando precisar de imagem ambiental, foto autêntica de brasileiro real ou ilustração no estilo do mascot
- Sempre comprimir e servir em WebP

### Empty states

Sempre que uma lista estiver vazia, mostrar:

1. Ilustração simples ou ícone grande (32-48px)
2. Texto explicativo curto: "Você ainda não tem nada aqui."
3. Sugestão clara do que fazer: "Crie seu primeiro [coisa] pra começar."
4. Botão primário levando à ação

---

## 11. Acessibilidade

A Batuta atende ao público leigo brasileiro — muitos com idade mais avançada, deficiências visuais ou pouca familiaridade com tecnologia. Acessibilidade é prioridade, não item de checklist no fim.

### Mínimos obrigatórios

- **Contraste de texto:** mínimo 4.5:1 entre texto e fundo. 7:1 quando possível.
- **Áreas de toque:** mínimo 44x44px pra elementos interativos em mobile.
- **Foco visível:** anel de foco visível em todos os elementos interativos (Tab navigation). Nunca usar `outline: none` sem fornecer alternativa.
- **Alt text em imagens:** sempre. Decorativa pode ser `alt=""`.
- **Aria-label em ícones-só:** botão de fechar com ícone X precisa `aria-label="Fechar"`.
- **Hierarquia de heading correta:** h1 → h2 → h3, sem pular níveis.
- **Estado nunca só por cor:** sucesso/erro/aviso sempre com cor + ícone + texto.

### Suporte a leitor de tela

Componentes shadcn já vêm acessíveis. Não desabilitar essa funcionalidade ao customizar.

---

## 12. Voice & messaging — exemplos canônicos

Frases que devem ser usadas como referência consistente em todo o produto, marketing e comunicação:

### Login e onboarding

- "Bem-vindo de volta à Batuta."
- "Vamos criar sua conta em menos de 1 minuto."
- "Pronto pra orquestrar seu primeiro time?"

### Ações principais

- "Criar meu primeiro time" (CTA principal pós-cadastro)
- "Adicionar assistente"
- "Adicionar habilidade"
- "Conectar WhatsApp"
- "Configurar gatilho"

### Estados de sucesso

- "Time criado ✨"
- "Assistente atualizado"
- "WhatsApp conectado com sucesso"

### Estados de erro

- "Não conseguimos conectar agora. Tenta de novo em alguns instantes." (genérico)
- "Esse email já tem cadastro. Quer fazer login?" (signup duplicado)
- "Senha precisa de no mínimo 8 caracteres." (validação)

### Confirmação destrutiva

- "Tem certeza que quer remover esse assistente? Isso não pode ser desfeito."
- "Remover esse time apaga todos os assistentes, habilidades e histórico junto. Tem certeza?"

### Cobrança

- "Você atingiu o limite do seu plano. Faça upgrade pra continuar ou aguarde a renovação."
- "Sua assinatura está ativa até [data]."
- "Pagamento recusado. Atualize seus dados pra continuar."

---

## 13. Próximas decisões (TODO)

Coisas que ainda precisamos definir e fechar:

- [ ] Kit de logo completo (SVG do mascot, SVG do logotipo, ícone em todos os tamanhos)
- [ ] Versões finais do mascot pra ilustrações de empty state (3-5 cenas)
- [ ] Voz e tom no canal WhatsApp (a Batuta tem um "tom oficial" quando assistentes respondem? Ou herda do template?)
- [ ] Sistema de animações (entrada de elementos, micro-interações) — provavelmente Framer Motion
- [ ] Domínio definitivo: batuta.com.br? batuta.ai? batuta.io?
- [ ] Identidade sonora pra eventual vídeo/podcast (jingle curto, opcional)

---

## 14. Como contribuir com este documento

Este é um documento vivo. Sempre que tomarmos decisão de marca ou ajustarmos algo, atualizamos aqui.

**Quem pode mudar:** dev principal (você), designer (quando contratar), responsável por marketing/conteúdo.

**Como mudar:**

1. Editar este arquivo
2. Atualizar "Última atualização" e "Versão" no topo
3. Commitar no Git com mensagem clara: `docs(design-system): atualiza paleta de erro pra novo tom de vermelho`
4. Se a mudança for grande, avisar quem mais usa o documento

**Versões:**
- 1.0 → versão inicial (este documento)
- 1.x → ajustes pequenos
- 2.0 → reformulação significativa (ex: troca de paleta, troca de fonte)
