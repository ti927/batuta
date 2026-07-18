---
titulo: "Parede de ativação"
area: "operacao"
slug: "parede-de-ativacao"
tags: ["parede", "ativacao", "ativar", "acao-irreversivel", "portao", "trava", "seguranca"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/base.py (exige_portao)", "cerebro/rotas/automacoes.py", "project_ia-unica-conversa-eterna"]
---

# Parede de ativação

## Em uma frase
Ao **ativar** uma automação, o Batuta confere se há uma **ação irreversível sem portão antes** — e, se
houver, **recusa a ativação** com explicação.

## Para que serve / quando usar
É a trava de segurança que impede um fluxo de sair publicando/enviando/gravando **sem** um humano ter
aprovado. Você encontra a parede no momento de ativar (ou quando a IA companheira tenta ativar por você).

## Como usar (na tela)
1. Monte a cadeia com o **portão no passo anterior** a cada ação irreversível.
2. Clique em **Ativar**. Se estiver tudo certo, a automação entra no ar.
3. Se faltar um portão, a ativação é **recusada** e o Batuta diz **onde** falta — corrija e ative de novo.

## Exemplos
- Uma automação que publica no Instagram **sem** portão antes → a ativação é barrada até você inserir o
  portão.

## Limites e cuidados
- A necessidade de portão é **derivada** de cada instrumento (`acao_irreversivel`), não de uma lista fixa —
  um GET não pede portão; um POST/publicação sim.
- Instrumentos com interruptor por instância (ex.: REST/SQL em leitura, webhook) ajustam essa derivação.
- **Nada roda enquanto inativa.** A parede só entra em cena na ativação.

## Para a IA
Você não ativa por conta própria uma automação com ação irreversível sem portão — é justamente o que a
parede protege. Monte a estrutura certa (preparar+gate → executar) e sinalize ao consultor quando estiver
pronta para ele ativar.

## Relacionado
- [[automacoes/portao-de-aprovacao]]
- [[automacoes/automacao]]
- [[instrumentos/cinto]]
