---
name: mexer-no-motor
description: Use SEMPRE antes de mexer no motor do Batuta — orquestração (cadeia, retomada, fila, dono, espera), aprovação/pedir_aprovacao, mensageria/Telegram, a tela de inspeção de execução, ou qualquer porta por onde uma pessoa ou um processo age sobre uma execução. Lista de verificação das falhas que já aconteceram e o teste que as pega.
---

# Mexer no motor

O motor quebra quase sempre do mesmo jeito: **duas coisas acontecendo juntas**, ou **uma
coisa chegando atrasada**. Testar um cenário de cada vez não pega isso — foi assim que,
em 05/10/2026, quatro mensagens no Telegram re-rodaram um agente que já tinha decidido
(execução f941b1b1), e que dois "aprovado" seguidos aprovavam um pedido que ninguém viu.

## Antes de escrever código

1. Leia `docs/FALHAS-DO-MOTOR.md` (o catálogo, seções E e F no mínimo). Se a mudança cria um
   modo de falha novo, ele entra lá.
2. Mexendo em checkpointer/memória/LangGraph: carregue `langgraph-persistence` e
   `langgraph-human-in-the-loop` antes. Não use a LangGraph de memória.
3. Liste as **portas** que tocam o que você vai mudar: clique na tela, mensagem no Telegram,
   botão antigo do Telegram, MCP, trabalhador da fila, vigias (sweeper, espera esquecida),
   agendador, chamada de outra automação.

## As quatro perguntas, para CADA porta

| Pergunta | O que tem que acontecer |
|---|---|
| **Chega duas vezes?** (duplo clique, 4 mensagens, retentativa) | a 2ª é no-op **com aviso honesto** ("já recebi") — nunca roda de novo |
| **Chega atrasada?** (o fluxo já parou noutra aprovação, concluiu, foi cancelado) | só vale para o que a pessoa **viu**: `passo_id` na tela; no canal, mensagem mais antiga que o passo em espera é recusada |
| **Outra porta age ao mesmo tempo?** | trava atômica: `dono.tomar(..., exigir_estado=...)` — o estado na MESMA condição do UPDATE. Nunca "confere e depois age" em dois comandos |
| **O processo morre no meio?** (deploy, queda) | nada fica "em andamento" sem vigia; o trabalho órfão é retomado ou avisado |

E sempre:
- **Sinal em menos de 1 s** para toda ação da pessoa. Clique sem resposta visível vira cinco
  cliques. Trabalho longo: segundo plano + sinal de vida + acompanhamento na tela.
- **Estado da execução mora na execução** (trava, relógio, endereço do pedido) — não só na borda.
- **"O último passo"** = `ordem desc, criado_em desc` em TODA busca (cérebro e tela iguais).
- **O texto do agente não é prova** de que a ação aconteceu: confira os instrumentos acionados.
- Texto que a pessoa lê: skill `escrever-para-quem-usa`.

## Antes de dar por pronto

1. **Porta ou evento novo?** Vira uma regra em `cerebro/testes/test_combinacoes_aprovacao.py`.
   **Garantia nova?** Vira um `@invariant` lá.
2. Rode a busca funda:
   `cd cerebro && BATUTA_COMBINACOES=1000 PYTHONIOENCODING=utf-8 uv run pytest testes/test_combinacoes_aprovacao.py`
3. Achou defeito → a sequência mínima que o Hypothesis imprimir vira **teste fixo** (`_replay`) no
   mesmo arquivo.
4. **Prove que o teste pega:** desligue a correção, veja falhar, religue, veja passar.
5. Suíte inteira verde (`uv run pytest -q`) e, se tocou a tela, `npx tsc --noEmit`.
6. Antes do push: nenhuma execução `em_andamento`/`aguardando` em produção (o deploy reinicia
   o servidor).
