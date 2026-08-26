---
titulo: "Sinais e diagnóstico (quando algo trava ou degrada)"
area: "operacao"
slug: "sinais-e-diagnostico"
tags: ["diagnostico", "log", "evento", "travou", "preso", "degradado", "silencio", "observabilidade", "turno"]
revisado_em: "2026-08-26"
fontes: ["cerebro/observabilidade/escritor.py", "cerebro/mensageria/sweeper.py", "cerebro/orquestracao/memoria_conversa.py", "cerebro/diagnostico_execucao.py", "CLAUDE.md §12-A"]
---

# Sinais e diagnóstico (quando algo trava ou degrada)

## Em uma frase
Nada no Batuta pode falhar em silêncio: toda queda deixa **evento no registro do sistema**, todo trabalho
preso é **destravado por um vigia**, e quem esperava resposta **é avisado** com um recado honesto.

## Para que serve / quando usar
Quando alguém diz *"não aconteceu nada"*, *"o agente ignorou minha mensagem"* ou *"parece travado"*. Antes
de culpar o modelo ou o prompt, olhe os sinais — quase sempre eles dizem exatamente o que houve.

Um princípio orienta o sistema todo: **proteger o atendimento não pode virar esconder o problema.** Quando
uma peça falha, o Batuta continua funcionando em modo reduzido — mas registra a queda e avisa. Um modo
degradado silencioso é considerado defeito, não proteção.

## Como usar (na tela)
1. **Na execução:** a inspeção mostra o motivo em português, o instrumento envolvido e avisos com ação
   sugerida. Numa conversa, cada turno registra se rodou com **memória durável** ou em **modo legado**.
2. **Nos registros do sistema:** a consulta de logs mostra os eventos, com data, servidor e detalhe.
3. **Na conversa:** se um turno não voltou, o próprio contato recebe o aviso e a conversa é destravada.

## Exemplos
- Uma aprovação respondida no Telegram que "não fez nada": o turno começou e não voltou. Passados ~30
  minutos, o contato é avisado, a conversa é destravada e a aprovação continua pendente — nada se perde.
- Um agente que "esqueceu" o que já tinha buscado: os turnos aparecem carimbados como **legado**, sinal de
  que a memória entre turnos estava indisponível.

## Limites e cuidados
- Os eventos que mais importam, e o que cada um significa:
  - **turno começou e não terminou** — a tarefa de fundo morreu ou pendurou; o vigia destrava em ~30 min.
  - **turno preso** — o vigia agiu: avisou o contato e devolveu a conversa ao relógio normal. Ele **não**
    reprocessa sozinho, de propósito: o turno pendurado pode estar no meio de uma ação externa (publicar,
    enviar), e repetir arriscaria fazer duas vezes. Quem reenvia é a pessoa.
  - **memória de conversa indisponível** — o sistema caiu para o modo legado: cada turno recomeça do texto
    e a trava de ação irreversível fica inativa. É degradação, não normalidade — peça verificação.
  - **falha de ferramenta pelo MCP** — vem com um **código** que aparece também na resposta ao Claude; cite
    esse código ao pedir ajuda.
- **Falha que a ferramenta devolve como resposta também entra no rastro.** Quando um sistema externo
  responde "não deu" (por exemplo, arquivo grande demais), o agente recebe isso como dado e decide como
  seguir — e é comum ele narrar sucesso mesmo assim. O registro guarda a falha crua, então **o que o agente
  escreveu não é prova de que a ação aconteceu**: confira o rastro.
- O tempo de espera do vigia é generoso (~30 min) porque uma chamada de IA lenta com retentativas pode
  demorar de verdade. Ele destrava o que está preso, não interrompe o que ainda está trabalhando.

## Para a IA
Diante de *"não funcionou"*, siga esta ordem, sem adivinhar:
1. **Leia o rastro** (execução e seus passos) antes de opinar. Ferramenta que não aparece nos instrumentos
   acionados **não foi chamada** pelo modelo — isso é adesão do modelo ao prompt, não defeito do motor.
2. **Procure falha devolvida como resposta** nos erros de instrumento do passo: é o caso em que o agente diz
   ter feito e não fez.
3. **Verifique degradação**: turno carimbado como legado, conversa presa, evento de indisponibilidade.
4. Só então discuta prompt ou modelo.
Ao explicar ao consultor, diga **o que aconteceu e o que fazer** — nunca "ocorreu um erro". Se houver código
de erro, repasse-o.

## Relacionado
- [[automacoes/execucoes-e-inspecao]]
- [[operacao/falhas-e-retentativa]]
- [[mensageria/conversas]]
