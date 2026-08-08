---
titulo: "Instrumento — Guardar imagem recebida (→ URL)"
area: "instrumentos"
slug: "arquivar-imagem"
tags: ["arquivar-imagem", "imagem", "foto", "comprovante", "storage", "url", "telegram", "atendimento", "instrumento"]
revisado_em: "2026-08-08"
fontes: ["cerebro/instrumentos/arquivar_imagem.py", "project_imagem-telegram-visao"]
---

# Instrumento — Guardar imagem recebida (→ URL)

## Em uma frase
Guarda a foto que o contato enviou na conversa e devolve uma **URL pública durável** — para preservar a
imagem e usá-la noutro sistema.

## Para que serve / quando usar
No atendimento por mensageria (hoje Telegram), o agente **já lê** automaticamente a imagem que o contato
manda — ela vira descrição no histórico, sem instrumento nenhum. Este instrumento é o outro passo: quando a
foto precisa ser **preservada** (não só lida), ele a salva no nosso storage e devolve a URL. O caso clássico:
um **comprovante** de despesa que o agente guarda e depois anexa a um sistema externo (ex.: um endpoint do
Bubble, via [[instrumentos/chamar-rest]]). Se a foto é descartável (só interessa o texto que veio junto), o
agente **não** chama — quem decide isso é o markdown do agente, caso a caso.

## Como usar (na tela)
1. Crie o instrumento **Guardar imagem recebida (→ URL)**. Não tem configuração nem segredo.
2. Pendure-o no cinto do **agente atendente** (o mesmo que recebe as mensagens do canal).
3. No markdown do agente (skill_md/soul_md), instrua **quando** guardar e **o que fazer com a URL** — por
   exemplo: "ao receber um comprovante, guarde a imagem e envie a URL no campo X do endpoint".

## Exemplos
- Reembolso: o consultor manda a foto do comprovante → o agente guarda → recebe a URL → faz um POST no
  sistema financeiro com a URL anexada.

## Limites e cuidados
- Grava só no **nosso** storage (bucket público) → **não** é ação irreversível, **sem portão**.
- Funciona mesmo **num turno posterior** ao envio da foto: se o agente decidir guardar depois, o Batuta
  rebusca a imagem mais recente da conversa pelo id salvo — o contato **não** precisa reenviar.
- Se não houver foto disponível (o contato nunca enviou, ou o canal não é de imagem), o instrumento avisa
  com clareza em vez de falhar em silêncio.
- **Ler ≠ guardar:** a leitura/descrição é automática; este instrumento é só para **guardar**.

## Para a IA
Sem parâmetros nem config (veja `arquivar_imagem` no catálogo): ele guarda a(s) imagem(ns) da conversa em
curso e devolve `urls`. Ponha-o no cinto do agente atendente e **descreva no markdown** a política: quando
guardar (ex.: comprovantes) e o destino da URL (ex.: repassar via [[instrumentos/chamar-rest]]). Não peça
portão — é gravação no nosso storage. A leitura da foto já é automática na borda; não crie instrumento para
"ver" a imagem recebida.

## Relacionado
- [[instrumentos/descrever-imagem]]
- [[instrumentos/chamar-rest]]
- [[mensageria/conversas]]
- [[mensageria/canal-telegram]]
