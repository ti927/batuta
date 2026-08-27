---
titulo: "Sinais e diagnóstico (quando algo trava ou degrada)"
area: "operacao"
slug: "sinais-e-diagnostico"
tags: ["diagnostico", "log", "evento", "travou", "preso", "degradado", "silencio", "observabilidade", "turno", "status", "elo", "rede", "congelou", "reconectar"]
revisado_em: "2026-08-27"
fontes: ["cerebro/observabilidade/escritor.py", "cerebro/mensageria/sweeper.py", "cerebro/orquestracao/memoria_conversa.py", "cerebro/diagnostico_execucao.py", "cerebro/saude_elos.py", "CLAUDE.md §12-A"]
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
  - **turno começou e não terminou** — a tarefa de fundo morreu ou pendurou; o vigia destrava em ~8 min
    (~30 min quando a conversa conduz uma aprovação de portão).
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
- O tempo de espera do vigia tem **duas medidas**, cada uma pelo pior caso real: **~8 min no atendimento**
  (ali a IA roda com limites curtos — quem escreveu está esperando do outro lado) e **~30 min no portão**
  (a resposta religa o fluxo inteiro, que pode demorar de verdade). Ele destrava o que está preso, não
  interrompe o que ainda está trabalhando. Era 30 para os dois até 2026-08-27, quando um contato ficou
  16 minutos no vácuo esperando o vigia de um atendimento simples.

## Quando o sistema externo aceita, mas o dado não chega
Uma família de problema que os sinais acima **não** pegam, porque ninguém falhou: a requisição foi
aceita (o serviço respondeu "criado com sucesso") e mesmo assim um campo chegou vazio do outro lado.
Aí a causa quase nunca é o agente — é **como o instrumento foi montado**: o campo está sendo enviado
numa parte da requisição que o serviço ignora (ver [[instrumentos/construir-conector]]). Regra prática:
*registro criado com um campo vazio* = confira o destino desse campo antes de qualquer outra hipótese.
**Nada disso aparece no rastro como erro**, e é por isso que a checagem tem de ser deliberada.

## A página de status e o vigia dos elos
Desde 2026-08-27 o Batuta **sonda ativamente cada ligação da própria corrente** — banco de dados,
memória de conversa, provedores de IA (com a chave, sem gastar token), cada canal Telegram (inclusive
se o Telegram está conseguindo **entregar** mensagens pra gente), Meta, Storage, a borda pública, o
serviço MCP e os motores internos (fila, agendador, vigia). O resultado vive na página **`/status`**
da interface (o selo de versão da barra lateral leva até ela) e na API em `GET /saude/elos`.

- Cada elo aparece **verde (operacional) / âmbar (com limitação) / vermelho (fora do ar)**, com o
  erro traduzido e há quanto tempo está assim.
- **Toda queda e volta vira evento** no registro do sistema (`elo.caiu`, `elo.voltou`,
  `elo.reconectado`) — dá para reconstruir depois QUANDO um problema começou e acabou.
- Os elos de banco têm **auto-cura**: duas falhas seguidas derrubam o pool e reconectam sozinhos.
  Os demais têm o botão **Reconectar** (admins da consultoria) quando há cura possível.
- Instrumentos de cliente **não** são sondados automaticamente (custo/limites) — o teste deles é sob
  demanda, no Construtor.

**Por que existe:** em 2026-08-27 a rede entre o servidor e o banco **congelou por ~30 minutos** —
sem erro, sem fechamento, bytes parados em trânsito. O app respondia normalmente e todos os
atendimentos ficaram mudos; ninguém tinha para onde olhar. A família de problema *"a rede congelou"*
não dispara NENHUM erro clássico: o sinal é **tudo travar ao mesmo tempo e destravar junto**, turnos
levando minutos no que sempre levou segundos, e (no banco de logs) `turno.morreu` com erros de
conexão/SSL. Hoje a página de status mostra o elo exato que caiu, e os limites de rede novos
(o cérebro corta conexão congelada em ~30 s) transformam o congelamento em erro rápido e honesto.

## Para a IA
Diante de *"não funcionou"*, siga esta ordem, sem adivinhar:
0. **Descarte primeiro a hipótese "ligação quebrada".** A página **`/status`** do Batuta mostra cada
   elo (banco, IA, canais, borda, motores) em verde/âmbar/vermelho. Elo caído = o problema não é do
   time nem do modelo, é da ligação — e o conserto está ali (botão Reconectar), não no prompt. Você
   **não tem ferramenta** para ler os elos: **peça ao consultor para abrir `/status`** — sobretudo
   quando o sintoma é *tudo* parando ao mesmo tempo, ou uma demora fora do normal em várias frentes.
1. **Leia o rastro** (execução e seus passos) antes de opinar. Ferramenta que não aparece nos instrumentos
   acionados **não foi chamada** pelo modelo — isso é adesão do modelo ao prompt, não defeito do motor.
2. **Procure falha devolvida como resposta** nos erros de instrumento do passo: é o caso em que o agente diz
   ter feito e não fez.
3. **Verifique degradação**: turno carimbado como legado, conversa presa, evento de indisponibilidade.
4. **Se o serviço aceitou mas o dado não chegou**, leia a configuração do instrumento (destino dos
   campos) — não conclua que o agente errou.
5. Só então discuta prompt ou modelo. **Culpar o modelo é quase sempre diagnóstico preguiçoso:** o
   Batuta precisa funcionar com qualquer um, e problema real costuma estar em configuração, conexão ou
   fiação. Se for mesmo adesão do modelo ao prompt, prove com o rastro (a ferramenta não foi chamada).
Ao explicar ao consultor, diga **o que aconteceu e o que fazer** — nunca "ocorreu um erro". Se houver código
de erro, repasse-o. E **não invente causa**: se você não tem como saber (por exemplo, em que parte da
requisição um campo caiu), diga que vai verificar e verifique.

## Relacionado
- [[automacoes/execucoes-e-inspecao]]
- [[operacao/falhas-e-retentativa]]
- [[mensageria/conversas]]
