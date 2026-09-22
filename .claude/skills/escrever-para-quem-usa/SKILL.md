---
name: escrever-para-quem-usa
description: Use SEMPRE que escrever qualquer texto que aparece numa tela do Batuta — rótulo, botão, aviso, erro, estado vazio, texto de ajuda, mensagem enviada a uma pessoa. Traduz o vocabulário de dentro do código para o de quem usa, e corta o que ninguém vai ler.
---

# Escrever para quem usa

O maestro não é desenvolvedor. **Nenhum ser humano sabe o que acontece por baixo dos panos de um software** — nem no Batuta. Quem lê a tela conhece o próprio trabalho dele (publicar um post, aprovar um orçamento), não o meu.

Esta skill existe porque a regra já estava escrita em dois lugares — `DESIGN-SYSTEM.md` §2 ("sem jargão técnico; se aparecer, **é falha de tradução**") e a skill `frontend-design` ("nomeie as coisas pelo que o usuário entende, não por como o sistema é construído") — e mesmo assim escrevi, numa tela, *"o Batuta segue pela resposta da pessoa e avisa no rastro"*. Ninguém sabe o que é "rastro". Saber a regra não bastou; ela precisa de um passo obrigatório.

## As duas perguntas, antes de escrever qualquer coisa

1. **Isto precisa existir?** Texto que explica *por que o sistema foi feito assim* não ajuda ninguém a fazer nada. É justificativa minha, não instrução dela. **Corte.**
2. **Quem lê sabe o que esta palavra significa?** Se a palavra só existe porque eu escrevi o código, traduza ou reescreva a frase sem ela.

A ordem importa: **apagar vem antes de reescrever.** Uma ressalva que ninguém lê não protege ninguém — só polui. Se a honestidade cabe no título, não escreva o parágrafo.

## Palavras que NUNCA vão para a tela

Palavras de dentro do Batuta, e o que dizer no lugar:

| Não escreva | Escreva |
|---|---|
| rastro, timeline, trilha | o que aconteceu / o passo a passo da execução |
| nó, cadeia, grafo | passo / o desenho |
| declarar o caminho, ramo, saída (a aresta) | dizer por onde seguir / o caminho |
| portão, gate | a aprovação / quando ele para e pergunta |
| ficha, payload, corpo da requisição | o que o passo recebe / os dados |
| cascata, herdar (no sentido técnico) | segue o valor da automação |
| instrumento de mensageria, canal | o bot / o WhatsApp / o Telegram |
| webhook, endpoint, API, token, cota | o endereço que outro sistema chama / (não mencionar) |
| fan-out, disjuntor, sweeper, vigia, heartbeat | (reescreva a frase: diga o EFEITO) |
| `campos_resposta`, `config`, qualquer nome de variável | o rótulo que aparece na tela |

Palavras que **são** do produto e podem aparecer: agente, instrumento, automação, time, gatilho, aprovação. Estão no `DESIGN-SYSTEM.md` e a pessoa as vê na navegação.

## Como escrever o que sobrou

- **Diga o que fazer, não como funciona.** "Ajuste só o que for diferente neste agente" ✅ — "estes valores sobrepõem a cascata do fluxo" ❌
- **Erro diz o que houve E o que fazer.** Nunca código nu, nunca "Falha ao…".
- **Uma frase faz um trabalho.** Se a segunda frase explica a primeira, a primeira está errada.
- **Nome honesto no título dispensa ressalva no corpo.** "O desenho não tem furos" já diz que é sobre o desenho.
- Voz e exemplos lado a lado: `DESIGN-SYSTEM.md` §2 ("Tom de voz"). Telas e layout: `docs/design/README.md`.

## A conferência final (obrigatória)

Antes de dar a tarefa por pronta, releia **só o texto que aparece na tela**, em voz alta, como se fosse o maestro:

- Alguma palavra existe só porque eu escrevi o código? → traduza.
- Algum parágrafo explica a minha decisão de arquitetura? → apague.
- Se eu apagasse este bloco, alguém perderia alguma coisa? → se não, apague.

**Sinal de alarme:** se o texto na tela parece com o comentário que escrevi no código acima dele, ele está errado. O comentário é para quem mantém; a tela é para quem usa.
