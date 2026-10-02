---
titulo: "O Agente e os 4 markdowns"
area: "times-agentes"
slug: "agente"
tags: ["agente", "markdown", "agent", "skill", "tools", "soul", "modelo", "modelo de ia", "qual modelo", "sonnet", "opus", "haiku", "preço do modelo", "personalidade"]
revisado_em: "2026-10-02"
fontes: ["PRODUTO.md §11", "cerebro/modelos.py (Agente)", "feedback_sem-prompt-base-agentes"]
---

# O Agente e os 4 markdowns

## Em uma frase
Um agente é uma peça que faz **uma** função bem-feita; **todo o comportamento dele vem de 4 textos**
(markdowns) que você escreve — não há preâmbulo escondido.

## Para que serve / quando usar
Cada agente é único e encadeável. Você define o que ele é e como age escrevendo os 4 markdowns:

- **`agent.md` (Quem é)** — a identidade e a missão do agente, em uma frase forte.
- **`skill.md` (Habilidades)** — o passo a passo do que ele faz; as regras do trabalho dele.
- **`tools.md` (Cinto de instrumentos)** — como e quando usar cada instrumento do cinto.
- **`soul.md` (Personalidade)** — o tom, o jeito de falar, os cuidados.

Além dos markdowns, o agente tem um **modelo de IA** (qual "cérebro" usa) e, opcionalmente, **memória**.

## Como usar (na tela)
1. No time, abra o agente (drawer/popup) e edite os 4 markdowns.
2. Escolha o **modelo de IA** (a escolha do provedor é feita aqui).
3. Pendure os **instrumentos** no cinto dele e explique no `tools.md` quando usá-los.
4. Salve — o popup mantém o que você digitou; marcadores mostram o que ainda não foi salvo.

## Qual modelo de IA escolher
O modelo é o "cérebro" que o agente usa para pensar e escrever. O custo da IA do agente depende dele (o
custo dos instrumentos é à parte — veja [[operacao/uso-e-custos]]). Preços por milhão de tokens, entrada /
saída:

| Modelo | Para quê | Preço |
|---|---|---|
| `claude-haiku-4-5` | passos mecânicos: publicar, rotear, formatar (é o padrão de quem não escolhe) | US$ 1 / 5 |
| `claude-sonnet-5` | o padrão para escrever, julgar e curar | US$ 2 / 10 |
| `claude-sonnet-5-5` | sucessor do Sonnet 5, mesmo preço (set/2026 — em validação no Batuta) | US$ 2 / 10 |
| `claude-opus-5-5` | raciocínio mais exigente; mais barato que os outros Opus (set/2026 — em validação) | US$ 4 / 20 |
| `claude-opus-5`, `claude-opus-4-8` | raciocínio mais exigente | US$ 5 / 25 |
| `claude-sonnet-4-6` | geração anterior do Sonnet | US$ 3 / 15 |

Há também modelos da OpenAI (GPT-5.6 Luna/Terra/Sol e GPT-4) e do Google (Gemini 3.8 Flash, 3.6 Flash,
3.5 Flash-Lite e 3.1 Pro) — só aparecem na tela quando a organização tem a chave daquele provedor.

**Modelo que vai sair do ar:** as empresas de IA desligam modelos com data marcada. No seletor, o modelo
que vai sair aparece com **"— sai em dd/mm/aaaa"** e um aviso embaixo; o já desligado some da escolha, e o
agente que ainda o usa ganha o selo **precisa de atenção** no cartão. Troque o modelo antes da data —
o aviso traz a sugestão de substituto.

Nos modelos mais novos da Anthropic (do Opus 4.7 em diante: Opus 4.8, Opus 5/5.5, Sonnet 5/5.5) o Batuta
não envia "temperatura" (eles recusam) e deixa o raciocínio do modelo ligado. No Sonnet 5.5 e no Opus 5.5,
quando uma conversa longa é resumida, o raciocínio dos turnos antigos é descartado em vez de dar erro — o
agente segue normalmente.

## Exemplos
- Um "Redator": `agent.md` diz que escreve artigos SEO; `skill.md` traz o processo; `tools.md` explica
  usar a busca web; `soul.md` fixa o tom da marca.

## Limites e cuidados
- **O comportamento vem 100% dos markdowns.** Se o agente está "tagarela" ou vago, o texto está vago —
  não há prompt-base para culpar. Seja específico.
- Um agente que **precisa de um dado** (ex.: qual cliente) deve **pedir** — instrua isso no markdown.
- **Os 4 markdowns são lidos juntos: instrução contraditória em um deles vence a regra nova do outro.**
  Ao mudar o jeito de fazer alguma coisa, **apague a instrução velha** — não basta escrever a nova em
  outro campo. Caso real (2026-09-02): a regra "chame Pedir aprovação e aguardar" entrou no `skill.md`,
  mas o `tools.md` continuou mandando pedir aprovação pelo Telegram e esperar "#aprovado#". O agente
  obedeceu a velha, o fluxo não parou e a execução terminou sem que ninguém aprovasse.

## Para a IA
Ao EDITAR um agente que já existe, leia os 4 markdowns ANTES de escrever: se a mudança troca o **jeito**
de fazer algo (outro instrumento, outro caminho), remova a instrução antiga no mesmo movimento. Regra
nova num campo + regra velha em outro = o agente segue a velha, calado.

Ao montar um agente, escreva os 4 markdowns com precisão; não confie num comportamento "padrão". Ensine
no markdown COMO usar cada instrumento do cinto (o instrumento é genérico; quem dá contexto é o texto do
agente). Um agente = uma função; se a tarefa tem várias etapas distintas, prefira **vários agentes**
encadeados a um agente que faz tudo.

## Relacionado
- [[instrumentos/cinto]]
- [[times-agentes/memoria-do-agente]]
- [[automacoes/cadeia-e-grafo]]
