---
titulo: "Instrumento — Agendar automação"
area: "instrumentos"
slug: "agendar-automacao"
tags: ["agendar", "agendamento", "disparo-futuro", "automacao", "alvo", "manual", "entrada", "instrumento", "editar", "reagendar", "recuperar", "nao-disparou"]
revisado_em: "2026-09-08"
fontes: ["cerebro/instrumentos/agendar_automacao.py", "cerebro/agendador.py", "cerebro/rotas/automacoes.py"]
---

# Instrumento — Agendar automação

## Em uma frase
Permite que um **agente** reprograme um **disparo futuro** de uma automação — a própria ou a de outro
time da mesma organização.

## Para que serve / quando usar
Ao fim de um fluxo, conforme o resultado, um agente pode marcar "rode de novo daqui a 10 dias" ou "dispare
a automação do outro time em tal data". O **alvo** (qual automação) é fixado por **você** na configuração;
o agente decide só **se** e **quando**.

## Como usar (na tela)
1. Crie o instrumento **Agendar automação** e, na configuração, escolha a **automação-alvo** (seletor com
   as automações da organização).
2. Pendure no cinto do agente que decide o agendamento.
3. **A automação-alvo precisa estar ATIVA** — e o ideal é que o gatilho dela seja **manual** (senão ela
   também roda sozinha pelo cron do próprio agendamento → disparo em dobro).
4. O agente pode passar uma **entrada** (texto) que chega ao primeiro agente da automação-alvo.

## Exemplos
- Um fluxo de follow-up que se reprograma para "+7 dias" até o cliente responder.
- O time financeiro dispara o time fiscal numa data de fechamento.

## Corrigir um agendamento que ainda vai disparar
Quem monta o texto de entrada é o **agente**, e agente erra. Por isso o agendamento pendente é
**editável**: na aba **Agendadas** das Execuções (e na seção "Próximas execuções agendadas" da
automação), cada linha mostra **entre aspas o texto que o agente escreveu** e traz **Editar** —
que corrige o texto, o horário, ou os dois.

Ver esse texto é o que permite consertar **antes** de rodar; e um texto inicial errado é sinal de
que o markdown do agente que agenda precisa de ajuste — a correção na linha resolve **este**
disparo, não o próximo.

Só se edita o que está **pendente**: o que já virou execução não volta atrás, e o que foi
cancelado se resolve pelo caminho abaixo.

## Quando o agendamento NÃO disparou
Se, na hora marcada, a automação-alvo estiver **desativada** (ou tiver sido removida), o
agendamento é **cancelado** — ele não fica esperando. Isso aparece de duas formas:

- Na aba **Agendadas**, em "Não dispararam (últimos 7 dias)", com o **motivo** em texto claro.
- Como evento **`agendamento.nao_disparou`** (nível `error`) no banco de logs, com a causa
  (`alvo_desativado` ou `alvo_removido`) — para a falha ter endereço mesmo que ninguém abra a tela.

**Isso se recupera.** A linha cancelada oferece dois botões:
- **Disparar agora** — cria a execução na hora, com o texto guardado (corrigível antes de confirmar).
  Funciona mesmo com a automação desativada, com aviso: disparo manual roda; os **próximos**
  agendamentos dela continuarão não disparando enquanto ela não for reativada.
- **Reagendar** — marca um novo disparo para a data/hora que você escolher. Se a automação seguir
  desativada até lá, ele morre pelo mesmo motivo — a tela avisa antes.

Cada agendamento é recuperado **uma vez** (a linha passa a mostrar "recuperado em…" e o elo para a
execução): um fluxo importante disparado duas vezes por engano é trabalho em dobro de verdade.

## Limites e cuidados
- **Alvo inativo/ausente** → o agendamento é **cancelado** (visível, nunca em silêncio) — e
  **recuperável** pela tela; ele não fica pendurado esperando a automação voltar.
- Piso de ~1 minuto no futuro; teto de agendamentos pendentes por automação.
- Ao **duplicar** o time, o alvo é remapeado; confira se aponta para a automação certa.

## Para a IA
O alvo é do humano (config), não do agente — nunca proponha o agente "escolher" a automação. Requisito
real do disparo: alvo **ativo**; recomende alvo com gatilho **manual** para não haver cron recorrente
junto. A "entrada" é um texto que vira a entrada do 1º agente do alvo.

Se o consultor disser que **um agendamento não rodou**, não conclua que o motor travou nem mande
recriar a automação: procure a linha cancelada na aba **Agendadas** (o motivo está escrito nela) ou
o evento `agendamento.nao_disparou`. O conserto é **reativar a automação** e usar **Disparar agora**
ou **Reagendar** — o trabalho não se perdeu. E se o problema for o **texto** que o agente montou, ele
é editável ali mesmo; a causa de raiz, nesse caso, está no markdown do agente que agenda.

## Relacionado
- [[automacoes/chamar-automacao]] — quando você precisa do **resultado** da outra
  automação, é aquele passo, não este instrumento: este dispara e não fica sabendo o que
  aconteceu.
- [[automacoes/esperar]] — para adiar um passo **do mesmo fluxo**, sem perder a ficha.
- [[automacoes/gatilhos]]
- [[automacoes/automacao]]
