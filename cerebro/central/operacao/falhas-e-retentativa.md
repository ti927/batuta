---
titulo: "Falhas e retentativa"
area: "operacao"
slug: "falhas-e-retentativa"
tags: ["falha", "erro", "retentavel", "idempotencia", "retentativa", "sweeper",
       "disjuntor", "desligada", "falhas seguidas"]
revisado_em: "2026-09-03"
fontes: ["cerebro/instrumentos/base.py", "cerebro/http_saida.py",
         "cerebro/orquestracao/circuito.py", "PRODUTO.md §16"]
---

# Falhas e retentativa

## Em uma frase
Quando um passo falha, o Batuta decide se **vale tentar de novo** (erro passageiro) ou se **para**
(erro definitivo) — e nunca refaz uma ação já feita.

## Para que serve / quando usar
Entender por que um fluxo às vezes se recupera sozinho e às vezes para na sua frente:

- **Retentável** — erro passageiro (rede, serviço fora do ar, "muitas requisições"/429, 5xx). O motor
  **tenta de novo**.
- **Não-retentável** — erro definitivo (chave recusada, parâmetro inválido, conteúdo bloqueado). O fluxo
  **para** com um recado claro; insistir não adianta.

## Como usar (na tela)
1. Na inspeção da execução, um passo que falhou mostra o **motivo em português** e se foi retentado.
2. Um erro definitivo pede uma **ação sua** (corrigir a chave, o parâmetro, o conteúdo) — não vai se
   resolver sozinho.

## Exemplos
- O provedor respondeu "muitas requisições" → retenta e segue.
- A chave da API foi recusada → para, para você corrigir a chave.

## Limites e cuidados
- **Idempotência:** depois que uma ação que age no mundo (publicar, gerar vídeo, responder comentário) já
  aconteceu, qualquer falha vira **não-retentável** — para nunca publicar/cobrar em dobro.
- Geração de vídeo/imagem pesada tem **teto de tempo**: se estourar, falha limpo numa vez só (não fica
  reprocessando e multiplicando custo).
- **Nem toda falha derruba o fluxo.** Um sistema externo pode responder "não deu" (por exemplo, arquivo
  grande demais) sem que isso seja um erro do Batuta: o agente recebe essa resposta como **dado** e decide
  como seguir — e às vezes narra sucesso. A falha fica registrada no rastro do passo, então confira o
  registro em vez de confiar no texto do agente (veja [[operacao/sinais-e-diagnostico]]).
- **Falha de rede tem recado próprio.** Quando o servidor do Batuta não consegue alcançar o endereço, a
  mensagem nomeia o host e diz que a segunda tentativa (por outro caminho de rede) também falhou. Nesse caso
  confira o endereço; se estiver certo, o destino provavelmente está fora do ar ou bloqueia servidores de
  nuvem. Repetir a chamada não costuma resolver.

## Quando a automação se desliga sozinha (o disjuntor)

Uma automação que **dispara sozinha** e falha **3 vezes seguidas** é **desligada pelo Batuta**, com um
recado pelo canal do time dizendo quantas falhas houve, em que passo parou a última e o que fazer.

Existe porque falhar todo dia é pior que falhar uma vez: sem isso, uma automação agendada com uma chave
vencida seguiria disparando, queimando dinheiro e enchendo o canal de avisos iguais — ou, se ninguém
abrisse os avisos, falhando em silêncio.

Três coisas que **não** contam para o disjuntor, e é importante saber por quê:

- **Disparo manual.** Quem clicou está olhando a tela e vê a falha na hora. Desligar a automação por baixo
  de quem está testando seria hostil — então testar à mão nunca desliga nada.
- **Falha causada pelo próprio Batuta** (execução interrompida por reinício do servidor ou recolhida por
  estar travada). O defeito não é da automação; sem essa exceção, três atualizações do Batuta em dias
  seguidos desligariam as automações do cliente. Ela também **não zera** a contagem: um reinício no meio de
  três falhas reais não pode mascarar o defeito.
- **Execução ainda em andamento ou parada numa aprovação.** Ainda pode terminar bem — não é veredito.

**Um sucesso zera a conta.** E **religar zera também**: quando você ativa a automação de novo, ela ganha as
três chances outra vez — pela tela ou pela IA, tanto faz.

## Como usar (na tela)
1. Uma automação desligada pelo disjuntor aparece **inativa**, e o Batuta diz que foi ele quem desligou.
2. Antes de religar, **conserte a causa** — se a chave está vencida, religar só gasta três execuções para
   voltar ao mesmo lugar. Abra as execuções que falharam e veja o passo.
3. Ative de novo. A contagem recomeça do zero.

## Para a IA
Traduza o erro para o consultor: se é retentável, o Batuta cuida; se é definitivo, diga **o que ele precisa
ajustar**. Nunca proponha "rodar de novo" quando o erro é de chave/parâmetro/conteúdo — corrija a causa.

Quando uma automação aparecer **inativa e com `desligada_por_falhas_em` preenchido**, não a reative de
cara: foi o disjuntor. Olhe primeiro as últimas execuções que falharam (`listar_execucoes` com
`apenas_problemas`, depois `diagnosticar_execucao`), diga ao consultor **o que quebrou**, e só proponha
religar depois que a causa estiver resolvida — reativar zera a contagem e dá três chances novas, então
religar sem consertar apenas adia o mesmo desligamento.

O teto vive em `orquestracao/circuito.py` (`FALHAS_PARA_DESLIGAR`), a contagem é derivada das execuções
(não há contador guardado) e o marco zero é `automacoes.falhas_contam_desde`, gravado ao ativar.

## Relacionado
- [[automacoes/execucoes-e-inspecao]]
- [[operacao/uso-e-custos]]
