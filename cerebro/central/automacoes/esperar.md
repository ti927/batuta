---
titulo: "O passo Esperar"
area: "automacoes"
slug: "esperar"
tags: ["esperar", "espera", "tempo", "adiar", "agendar", "pausa", "delay", "depois"]
revisado_em: "2026-09-03"
fontes: ["cerebro/orquestracao/cadeia.py", "cerebro/orquestracao/grafo.py", "cerebro/fila.py"]
---

# O passo Esperar

## Em uma frase
Um passo que **segura o fluxo por um tempo** e o solta depois — sem perder nada do que já
foi feito.

## Para que serve / quando usar
Quando o próximo passo só faz sentido mais tarde:

- publicar um carrossel **24 h** depois de o story ir ao ar;
- cobrar um lead **2 dias** depois do primeiro contato;
- reconferir um pedido **30 minutos** depois de enviá-lo.

Antes deste passo, a única saída era **agendar outra automação** — que começa do zero, sem a
ficha e sem o ponto do fluxo. Tudo o que tinha sido apurado se perdia no caminho, e o time
precisava redescobrir o contexto do próprio trabalho.

## Como usar (na tela)
1. No construtor, adicione o passo **Esperar**.
2. Diga **quanto** e em que **unidade**: minutos, horas ou dias.
3. Ligue a saída dele ao passo que deve rodar depois.

## Exemplos
- Gerar post → **Esperar 24 horas** → publicar o carrossel.
- Enviar proposta → **Esperar 2 dias** → agente de follow-up.

## Limites e cuidados
- **A ficha e o ponto do fluxo são preservados.** A execução volta exatamente daquele passo,
  com tudo o que os agentes já tinham guardado. É a diferença entre esperar e recomeçar.
- **A execução inteira espera.** Se o fluxo tinha outros caminhos abertos, todos param e
  voltam juntos — não fica metade rodando e metade parada.
- Enquanto espera, ela aparece como **"aguardando o tempo"**, com a data em que volta. Não
  pede nada de você (diferente de "aguardando você", que é uma aprovação).
- **Sem tempo definido, o fluxo passa direto** e o rastro avisa. Parar para sempre por causa
  de um campo vazio seria pior — mas o passo só faz o que você pediu se você preencher.
- **Teto de 60 dias** por espera. Não é limitação técnica: é para um zero a mais não deixar
  uma execução dormindo até o ano que vem.
- **Reiniciar o Batuta não perde a espera:** ela vive no banco, não na memória do servidor.
- A espera **não consome** o teto de tempo da execução — esse conta trabalho, não relógio
  (veja [[operacao/falhas-e-retentativa]]).
- O passo pode atrasar até meio minuto além do combinado: quem solta é um vigia que roda a
  cada 30 segundos. Para uma espera de horas ou dias isso é invisível; para "1 minuto",
  conte com essa folga.

## Para a IA
Tipo de nó `esperar`, com `espera: {quanto, unidade}` (`minutos`|`horas`|`dias`). Estrutural:
não roda agente e não consome IA — mas **deixa passo no rastro** (`tipo: "espera_tempo"`),
porque uma pausa de dois dias que não aparecesse na linha do tempo seria um buraco
inexplicável entre dois passos.

Proponha este passo quando o consultor disser "depois de X tempo", "no dia seguinte", "só na
semana que vem". **Não** proponha agendar outra automação para isso: aquilo perde a ficha e o
contexto, e é justamente o problema que este passo resolve. Agendar outra automação continua
certo quando o que se quer é um fluxo **novo**, com entrada própria.

A execução fica em `aguardando_tempo` com `retomar_em` — ao diagnosticar, isso **não é** um
travamento nem uma pendência de ninguém: ela volta sozinha.

## Relacionado
- [[automacoes/cadeia-e-grafo]]
- [[automacoes/pedir-aprovacao]]
- [[instrumentos/agendar-automacao]]
- [[operacao/falhas-e-retentativa]]
