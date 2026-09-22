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

## A alternativa que não expira: CONTA DE SERVIÇO
O OAuth acima é o acesso de uma **pessoa**, e ele tem um custo escondido: enquanto o app do Batuta não
passa pela verificação do Google (os escopos de Gmail e Drive são *restritos*, com auditoria anual), o
token de renovação **morre a cada 7 dias**. Em 2026-07 uma conta parou de renovar e o Search Console do
blog ficou **dois meses** em HTTP 401 — a falha era muda, e só apareceu porque um agente escreveu "401"
no meio de uma entrega.

A **conta de serviço** é uma identidade de **máquina**: sem tela de consentimento, sem app verificado,
sem expirar. Ela não se conecta por aqui — é uma opção de autenticação do **Construtor de Instrumentos**
(`auth_tipo: "google_conta_servico"`), com o JSON da chave no cofre. Ver
[[instrumentos/construir-conector]].

**Quando usar cada um:**
- **OAuth (esta tela)** — o agente age *como aquela pessoa* (ler o Gmail dela, a agenda dela).
- **Conta de serviço** — o agente age *como o sistema*, num recurso que se compartilha com ele
  (Search Console, uma planilha, uma pasta do Drive). Para automação que roda sozinha, é a melhor.

O passo que todo mundo esquece na conta de serviço: **dar acesso ao e-mail dela** no serviço de destino
(no Search Console, como usuário da propriedade). Sem isso vem 403 e o erro parece ser da chave.

## Para a IA
Ao montar um agente que usa um serviço Google, aponte o instrumento para a credencial `google` e avise que
falta o humano **conectar a conta** (botão "Conectar Google"), se ainda não conectou — não diga que está
"pronto" sem isso. Se um instrumento reclamar de permissão, oriente **reconectar incluindo aquele serviço**.
**Para automação que roda sozinha, prefira a conta de serviço** (não expira e não depende de ninguém
reconectar): monte um conector com `auth_tipo: "google_conta_servico"` em vez de usar o OAuth.

## Relacionado
- [[instrumentos/search-console]]
- [[instrumentos/construir-conector]]
- [[segredos/credenciais-nomeadas]]
- [[segredos/segredos-de-instrumento]]
