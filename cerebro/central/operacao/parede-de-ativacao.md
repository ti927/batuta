---
titulo: "Parede de ativação"
area: "operacao"
slug: "parede-de-ativacao"
tags: ["parede", "ativacao", "ativar", "acao-irreversivel", "portao", "trava", "seguranca"]
revisado_em: "2026-08-09"
fontes: ["cerebro/instrumentos/base.py (exige_portao)", "cerebro/rotas/automacoes.py", "cerebro/mensageria/config.py (parede governa a trava da conversa)", "cerebro/orquestracao/agente.py (portão nativo)", "project_ia-unica-conversa-eterna"]
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
- **Nada roda enquanto inativa.** A parede só entra em cena na ativação — no caso das **automações**.
- **No atendimento por conversa, a mesma parede age AO VIVO.** Quando o agente atendente vai executar uma
  ação irreversível, o sistema **segura e pede a confirmação do contato na hora**, dentro do próprio turno
  (não há o modelo de dois nós da esteira). É a mesma trava, governada pela mesma parede da organização:
  ligada, protege; desligada, a ação segue direto. Veja [[mensageria/conversas]]. Por isso o agente **não**
  deve ter um "Confirma?" manual no roteiro — seria confirmação em dobro.

## Para a IA
Você não ativa por conta própria uma automação com ação irreversível sem portão — é justamente o que a
parede protege. Monte a estrutura certa (preparar+gate → executar) e sinalize ao consultor quando estiver
pronta para ele ativar.

## Relacionado
- [[automacoes/portao-de-aprovacao]]
- [[automacoes/automacao]]
- [[instrumentos/cinto]]
