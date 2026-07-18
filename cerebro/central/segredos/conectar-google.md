---
titulo: "Conectar Google (OAuth)"
area: "segredos"
slug: "conectar-google"
tags: ["google", "oauth", "conectar", "gmail", "agenda", "drive", "search-console", "credencial", "conta"]
revisado_em: "2026-07-18"
fontes: ["cerebro/google_oauth.py", "cerebro/rotas/google.py", "cerebro/tipos_credencial.py (google)"]
---

# Conectar Google (OAuth)

## Em uma frase
Você conecta uma conta Google **uma vez** (login na tela do próprio Google) e o Batuta guarda o acesso —
renovando sozinho — para os instrumentos de Search Console, Gmail, Agenda e Drive.

## Para que serve / quando usar
Sempre que um time precisa acessar os dados Google do dono do negócio (o desempenho do blog no Search
Console, e-mails, agenda, arquivos do Drive). A credencial `google` é o "saco" seguro desse acesso; os
instrumentos Google **apontam** para ela.

## Como usar (na tela)
1. Em **Chaves e credenciais** da organização, crie uma credencial do tipo **Google** e clique em
   **"Conectar Google"**.
2. Você é levado à tela do Google, faz login na conta certa e **autoriza** os serviços.
3. No retorno, a credencial já aparece preenchida (com o e-mail da conta) — **sem colar token**.
4. Nos instrumentos Google, em **Credencial da central**, aponte para essa credencial.

## Exemplos
- Conectar a conta Google do dono → um agente "Analista de SEO" lê o Search Console do blog.

## Limites e cuidados
- **Não se cola token.** O acesso do Google vence rápido (~1h) e depende de um "token de renovação" que só
  o fluxo de conexão entrega — por isso é só pelo botão.
- **Uma conexão cobre os serviços habilitados.** Para incluir um serviço novo depois, **reconecte** (o
  Google pede o consentimento de novo, somando a permissão).
- **Fase de testes do Google:** enquanto o app do Batuta não passa pela verificação do Google, só as
  contas adicionadas como **testadoras** (até 100) conseguem conectar — como os testadores do Instagram.
- O segredo **nunca** volta à tela (só o e-mail e as permissões aparecem). A IA nunca toca o token.

## Para a IA
Ao montar um agente que usa um serviço Google, aponte o instrumento para a credencial `google` e avise que
falta o humano **conectar a conta** (botão "Conectar Google"), se ainda não conectou — não diga que está
"pronto" sem isso. Se um instrumento reclamar de permissão, oriente **reconectar incluindo aquele serviço**.

## Relacionado
- [[instrumentos/search-console]]
- [[segredos/credenciais-nomeadas]]
- [[segredos/segredos-de-instrumento]]
