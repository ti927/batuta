---
titulo: "Memória do agente"
area: "times-agentes"
slug: "memoria-do-agente"
tags: ["memoria", "aprender", "ficha", "recall", "assunto", "agente"]
revisado_em: "2026-07-17"
fontes: ["cerebro/memoria_agente.py", "cerebro/modelos.py (Agente.memoria_ativa)", "project_memoria-do-agente-fase-futura"]
---

# Memória do agente

## Em uma frase
Quando ligada, a memória deixa o agente **aprender com o próprio trabalho** — guardar e reusar fichas de
conhecimento, por assunto, entre execuções.

## Para que serve / quando usar
Para o agente não recomeçar do zero toda vez: lembrar preferências de um cliente, decisões já tomadas, um
padrão que funciona. É **por agente** e vem **desligada por padrão** (o comportamento sem memória é o
padrão). Ligue quando a repetição de contexto agrega — atendimento é o caso típico.

## Como usar (na tela)
1. No drawer do agente, ligue **Memória** e escolha o **recall**:
   - **sempre** — as fichas entram no prompt em toda execução (bom para atendimento).
   - **sob demanda** — o agente só busca a memória quando o markdown dele orienta a buscar.
2. As fichas ficam num **painel Memórias** no drawer do agente — você lê e edita ali.

## Exemplos
- Um atendente que guarda, por cliente, o que já foi combinado, e retoma sem pedir tudo de novo.

## Limites e cuidados
- A memória é organizada por **assunto** (uma ficha por assunto, atualizada — evita virar um monte de notas
  repetidas).
- **Desligada por padrão**: um agente novo não "lembra" nada até você ligar.
- Buscar uma memória que não existe **nunca trava** o agente.

## Para a IA
A IA criadora **lê** as memórias do agente e pode orientar você a editá-las na tela — ela não reescreve o
segredo do aprendizado sozinha. Ao montar um agente que se beneficia de lembrar (atendimento, follow-up),
sugira ligar a memória e escolher o recall adequado.

## Relacionado
- [[times-agentes/agente]]
- [[times-agentes/criar-com-a-ia]]
- [[mensageria/conversas]]
