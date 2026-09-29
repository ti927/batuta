---
titulo: "Duplicar time"
area: "admin"
slug: "duplicar-time"
tags: ["duplicar", "time", "copia", "remapeamento", "canal", "memoria", "inativa", "segredos", "senha", "reconectar"]
revisado_em: "2026-09-29"
fontes: ["cerebro/duplicacao_time.py", "project_navegacao-time-centrica"]
---

# Duplicar time

## Em uma frase
Duplicar recria um time inteiro — agentes, instrumentos, cinto, automações e a memória da IA companheira —
com **ids novos**, dentro da **mesma organização**.

## Para que serve / quando usar
Partir de um time que já funciona para montar outro parecido, sem refazer tudo. As referências internas
(quais agentes/instrumentos cada passo usa) são **remapeadas** para a cópia — ela não aponta para o
original.

## Como usar (na tela)
1. No time, use **Duplicar**. A cópia nasce na mesma organização.
2. **Preencha de novo os segredos** dos instrumentos que a tela listar ao copiar (senhas, tokens,
   chaves, certificados) e clique em **Conectar** nos que entram com a conta.
3. **Reconecte os canais** (Telegram/WhatsApp): eles nascem **desconectados** de propósito.
4. Revise e **ative** as automações — a cópia nasce **inativa**.

## Exemplos
- Duplicar o time de conteúdo de um cliente para criar o de outro, trocando só os detalhes.

## Limites e cuidados
- **Canais nascem desconectados** (sem token/webhook) — para dois times nunca brigarem pelo mesmo bot (um
  webhook por bot). Você pluga um bot novo na cópia.
- **Automações nascem inativas** — evita disparo em dobro de agendadas/webhook.
- **Segredos não são copiados** (desde 2026-09-29 isto é verdade no código também — antes eram): todo
  instrumento da cópia nasce com os segredos pendentes, e o login OAuth nunca vai junto. Credenciais da
  central apontadas pelo instrumento continuam valendo.
- **A memória da IA é herdada** (a cópia já "sabe" as decisões lembradas); dados de runtime (execuções,
  conversas, uso) **não** são copiados.
- Um alvo de **agendar automação** é remapeado — confira se aponta para a automação certa da cópia.

## Para a IA
Um time duplicado recomeça a conversa da criadora limpa, herdando a memória. Lembre o consultor de
**preencher os segredos** dos instrumentos listados (`duplicar_time` devolve a lista), **reconectar
canais** e **revisar antes de ativar** — a cópia não está no ar até ele ativar.

## Relacionado
- [[times-agentes/time]]
- [[mensageria/canal-telegram]]
- [[instrumentos/agendar-automacao]]
