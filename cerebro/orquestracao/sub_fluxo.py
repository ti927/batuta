"""Sub-fluxo síncrono — o nó "Chamar outra automação" (Onda 3, lacuna 21).

Até aqui, uma automação só conseguia acionar outra pelo instrumento
`agendar_automacao`, que é **fogo-e-esquece**: grava um agendamento e a execução que
chamou segue em frente sem jamais saber o que aconteceu do outro lado. Um time de
conteúdo não conseguia chamar o time de revisão e **usar** o parecer — disparava e
torcia.

O nó `chamar` fecha isso: a automação-alvo roda inteira, com execução e rastro
próprios, e o **resultado volta** para quem chamou.

## A mecânica é REÚSO, não invenção

O motor já sabia pausar uma execução guardando tudo (ficha, ramos que ainda não
rodaram, ponto do grafo) e retomá-la depois: é o que a aprovação faz desde sempre, e
o que o nó "Esperar" reusou trocando só quem solta. Aqui trocamos de novo:

| Pausa | Quem solta |
|---|---|
| aprovação | a resposta de uma pessoa |
| "Esperar" | o relógio (`fila.soltar_esperas_vencidas`) |
| **"Chamar outra automação"** | **a execução-filha, ao chegar num veredito** |

Por isso três coisas caem de graça, sem código próprio:

- **Se a filha parar para pedir aprovação, o chamador simplesmente continua parado.**
  Não é caso especial — é a mesma pausa, aninhada.
- **Reiniciar o Batuta não perde nada:** o estado vive no banco, não na memória.
- **A ficha atravessa**, nos dois sentidos.

## Os dois elos, e por que são dois

- `execucoes.chamada_por_execucao_id` (filha → chamador) dá a **linhagem**: é por ela
  que se barra o ciclo A→B→A e se mede a profundidade, e é ela que a tela usa para
  mostrar "chamada por".
- `pendencias[].aguarda_execucao` (chamador → filha) é o **retorno**: diz exatamente
  qual execução aquele ramo está esperando. Sem isso, um chamador que chamou várias
  vezes (ou foi re-rodado) teria de adivinhar qual filha é a sua.

## O que volta

A filha nasce com uma CÓPIA da ficha do chamador — ela precisa saber tudo o que ele
sabia, que é justamente o que o `agendar_automacao` perdia. Na volta, a ficha da filha
é mesclada de volta **por cima** da do chamador: como ela partiu de uma cópia, toda
diferença é trabalho que ela fez, e o valor dela é o mais recente. O texto final dela
vira a entrada do próximo nó do chamador.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from modelos import Automacao, Execucao, PassoExecucao
from observabilidade.escritor import registrar_evento
from orquestracao import grafo

logger = logging.getLogger("batuta.sub_fluxo")

# Estado do CHAMADOR enquanto a filha roda. Nome próprio (e não `aguardando_humano`)
# porque não há nada que uma pessoa deva fazer: misturar os dois faria a lista de
# execuções pedir atenção do consultor para algo que só depende de outra automação.
ESTADO_CHAMADOR = "aguardando_sub_fluxo"

# Origem carimbada na execução-filha. Fica FORA de `circuito.ORIGENS_SOZINHA` de
# propósito: o disjuntor conta o que falha rodando sozinho, e aqui quem rodou foi o
# chamador — a falha já conta para ele. Sem isso, uma automação usada como sub-fluxo
# por um chamador quebrado se desligaria por culpa alheia.
ORIGEM = "sub_fluxo"

# Estados em que a filha já tem veredito e o chamador pode seguir.
ESTADOS_FINAIS = ("concluida", "falhou", "cancelada")


def linhagem(sessao: Session, execucao_id: uuid.UUID | None) -> list[uuid.UUID]:
    """As automações da execução e de todos os seus ancestrais, da filha para o topo.

    É a corrente de chamadas. Subir por ela é o que permite dizer "esta automação já
    está rodando mais acima" antes de criar a filha — em vez de descobrir na terceira
    volta, com três execuções pagas."""
    ids: list[uuid.UUID] = []
    atual = execucao_id
    # Teto de voltas: a linhagem não pode ser mais funda que o permitido, e um dado
    # estragado (um ciclo gravado no banco) não pode prender este laço para sempre.
    for _ in range(grafo.MAX_PROFUNDIDADE_CHAMADA + 2):
        if atual is None:
            break
        linha = sessao.execute(
            select(Execucao.automacao_id, Execucao.chamada_por_execucao_id).where(
                Execucao.id == atual
            )
        ).first()
        if linha is None:
            break
        ids.append(linha[0])
        atual = linha[1]
    return ids


def pode_chamar(
    sessao: Session, execucao_id: uuid.UUID | None, alvo_id: str | None
) -> tuple[Automacao | None, str | None]:
    """A automação-alvo, ou o motivo honesto de não dar para chamá-la.

    Devolve `(automacao, None)` quando pode, e `(None, "frase")` quando não. A frase é
    escrita para quem vai ler o rastro e precisar CONSERTAR — diz o que houve e o que
    fazer, nunca "erro ao chamar sub-fluxo" (§12-A)."""
    if not alvo_id:
        return None, (
            "Este passo chama outra automação, mas nenhuma foi escolhida. Abra a "
            "automação, clique no passo e escolha em 'Automação a chamar'."
        )
    try:
        alvo_uuid = uuid.UUID(str(alvo_id))
    except (ValueError, AttributeError, TypeError):
        return None, (
            "Este passo aponta para uma automação que não existe mais. Abra a "
            "automação, clique no passo e escolha a automação a chamar."
        )
    alvo = sessao.get(Automacao, alvo_uuid)
    if alvo is None:
        return None, (
            "A automação que este passo chama foi apagada. Abra a automação, clique "
            "no passo e escolha outra."
        )

    corrente = linhagem(sessao, execucao_id)
    if alvo.id in corrente:
        return None, (
            f"Este passo chama a automação '{alvo.nome}', que já está rodando mais "
            "acima nesta mesma corrente de chamadas — seria um laço sem fim. Escolha "
            "outra automação, ou tire a chamada de um dos dois lados."
        )
    if len(corrente) >= grafo.MAX_PROFUNDIDADE_CHAMADA:
        return None, (
            f"Esta chamada passaria de {grafo.MAX_PROFUNDIDADE_CHAMADA} automações "
            "encadeadas (uma chamando a outra). O limite existe para uma corrente "
            "esquecida não sair gastando sozinha. Encurte a corrente."
        )
    return alvo, None


def ids_da_arvore(sessao: Session, execucao_id: uuid.UUID | None) -> list[uuid.UUID]:
    """Esta execução e todas as filhas que ela gerou (e as filhas delas).

    Serve aos TETOS de custo e de tempo: sem isto, bastaria pôr o trabalho caro num
    sub-fluxo para o teto do chamador nunca ser alcançado — o limite viraria enfeite.
    A aba Uso não muda: ela continua somando cada execução por si, e ninguém conta o
    mesmo dinheiro duas vezes."""
    if execucao_id is None:
        return []
    todos: list[uuid.UUID] = [execucao_id]
    fronteira = [execucao_id]
    for _ in range(grafo.MAX_PROFUNDIDADE_CHAMADA + 1):
        if not fronteira:
            break
        filhas = list(
            sessao.scalars(
                select(Execucao.id).where(
                    Execucao.chamada_por_execucao_id.in_(fronteira)
                )
            ).all()
        )
        novas = [f for f in filhas if f not in todos]
        todos.extend(novas)
        fronteira = novas
    return todos


def _texto_de_volta(filha: Execucao) -> str:
    """O que a filha devolve ao chamador, em texto.

    Numa falha, devolve o ERRO — e não vazio: o ramo de erro do chamador precisa
    saber o que quebrou para poder tratar, e um texto vazio faria o próximo agente
    inventar uma explicação."""
    resultado = filha.resultado or {}
    if filha.estado == "concluida":
        return str(resultado.get("texto") or "")
    if filha.estado == "cancelada":
        return "A automação chamada foi cancelada antes de terminar."
    return f"A automação chamada falhou. Erro: {resultado.get('erro') or 'não informado'}"


def _atualizar_passo(
    sessao: Session, chamador: Execucao, ordem: int | None, filha: Execucao, texto: str
) -> None:
    """Reescreve o passo do nó `chamar` com o que voltou.

    Um passo é o registro de UM nó, e o do `chamar` nasce dizendo só "chamou". Deixá-lo
    assim faria a linha do tempo mentir quando a filha falhasse: o passo apareceria
    verde ao lado de uma execução vermelha. Best-effort — o retorno do sub-fluxo não
    pode ser desfeito porque o rastro não pôde ser embelezado."""
    if ordem is None:
        return
    passo = sessao.scalars(
        select(PassoExecucao).where(
            PassoExecucao.execucao_id == chamador.id, PassoExecucao.ordem == ordem
        )
    ).first()
    if passo is None:
        return
    saida = dict(passo.saida or {})
    saida["texto"] = texto
    # O elo já existe desde a chamada; aqui só se carimba o desfecho, no MESMO lugar
    # (um segundo campo com a mesma informação é como as duas telas passam a discordar).
    saida["sub_execucao"] = {
        **(saida.get("sub_execucao") or {}), "id": str(filha.id), "estado": filha.estado,
    }
    passo.saida = saida
    passo.estado = "concluido" if filha.estado == "concluida" else "falhou"
    passo.finalizado_em = datetime.now(timezone.utc)


def _devolver(sessao: Session, chamador: Execucao, filha: Execucao | None) -> None:
    """Traz a filha de volta para o chamador: mescla a ficha, entrega o texto ao ramo
    que esperava e devolve a execução à fila (ou a faz falhar, quando não há para onde
    seguir)."""
    pendencias = list(chamador.pendencias or [])
    esperando = next(
        (i for i in pendencias if i.get("aguarda_execucao")), None
    )
    ordem = (esperando or {}).get("passo_ordem")

    if filha is None:
        # A filha sumiu (apagada). Nada a mesclar e nada a esperar: o chamador não
        # pode ficar parado para sempre por causa de um registro que não existe mais.
        texto = "A automação chamada não existe mais (a execução dela foi apagada)."
        estado_filha = "falhou"
    else:
        texto = _texto_de_volta(filha)
        estado_filha = filha.estado
        # A ficha da filha por cima da do chamador: ela partiu de uma cópia da dele,
        # então toda diferença é trabalho dela — e o valor dela é o mais recente.
        if filha.dados:
            chamador.dados = {**(chamador.dados or {}), **dict(filha.dados)}
        _atualizar_passo(sessao, chamador, ordem, filha, texto)

    demais = [i for i in pendencias if not i.get("aguarda_execucao")]

    if estado_filha == "concluida":
        seguir = [
            {
                **{k: v for k, v in (esperando or {}).items()
                   if k not in ("aguarda_execucao", "passo_ordem", "destinos_erro")},
                "entradas": [texto],
            }
        ] if esperando else []
    else:
        # A filha não terminou bem. Se o nó tem saída "Se der erro" desenhada, o fluxo
        # segue por ela levando a mensagem — a falha vira um caminho. Senão, o
        # chamador falha: seguir adiante com um resultado que não existe entregaria
        # trabalho pela metade narrado como inteiro.
        destinos_erro = (esperando or {}).get("destinos_erro") or []
        seguir = [
            {
                **{k: v for k, v in (esperando or {}).items()
                   if k not in ("aguarda_execucao", "passo_ordem", "destinos_erro", "no")},
                "no": d,
                "entradas": [texto],
            }
            for d in destinos_erro
        ]
        if not seguir and not demais:
            chamador.estado = "falhou"
            chamador.resultado = {"erro": texto}
            chamador.finalizada_em = datetime.now(timezone.utc)
            chamador.pendencias = None
            chamador.atividade = None
            chamador.atividade_em = None
            registrar_evento(
                categoria="execucao", acao="sub_fluxo.falhou", nivel="error",
                resultado="falha", recurso_tipo="execucao", recurso_id=chamador.id,
                detalhe={"filha": str(filha.id) if filha else None, "erro": texto},
            )
            return

    if chamador.teste_de_no:
        # "Testar este passo" num nó `chamar`: a automação-alvo rodou DE VERDADE (é o
        # que o teste precisa provar), e o teste acaba quando ela acaba. Sem isto o
        # chamador voltaria para a fila e rodaria o passo SEGUINTE — um teste de um
        # passo só que roda dois.
        chamador.estado = "concluida" if estado_filha == "concluida" else "falhou"
        chamador.resultado = (
            {"texto": texto} if estado_filha == "concluida" else {"erro": texto}
        )
        chamador.finalizada_em = datetime.now(timezone.utc)
        chamador.pendencias = None
        chamador.atividade = None
        chamador.atividade_em = None
        return

    chamador.estado = "aguardando"
    chamador.pendencias = (seguir + demais) or None
    registrar_evento(
        categoria="execucao", acao="sub_fluxo.voltou",
        recurso_tipo="execucao", recurso_id=chamador.id,
        detalhe={
            "filha": str(filha.id) if filha else None, "estado_filha": estado_filha
        },
    )


def soltar_chamadores_concluidos(sessao: Session) -> int:
    """Devolve à fila os chamadores cuja automação-filha já chegou a um veredito.

    É o vigia do sub-fluxo, e o ÚNICO caminho de retorno — o fim de uma execução
    também o chama, para o retorno ser imediato em vez de esperar o próximo giro. Uma
    implementação só, invocada de dois lugares: um segundo caminho de retorno seria
    exatamente o tipo de duplicação que um dia diverge.

    Cobre também a filha que sumiu: sem isso, apagar uma execução deixaria o chamador
    parado para sempre, e nada em andamento pode ficar sem quem o varra (§12-A).

    Devolve quantos soltou."""
    chamadores = sessao.scalars(
        select(Execucao).where(Execucao.estado == ESTADO_CHAMADOR)
    ).all()
    soltos = 0
    for chamador in chamadores:
        esperando = next(
            (i for i in (chamador.pendencias or []) if i.get("aguarda_execucao")), None
        )
        if esperando is None:
            # Parado esperando, mas sem dizer o quê: só pode ser dado estragado. Não
            # deixar preso é mais importante que entender como chegou aqui.
            _devolver(sessao, chamador, None)
            soltos += 1
            continue
        try:
            filha_id = uuid.UUID(str(esperando["aguarda_execucao"]))
        except (ValueError, TypeError):
            _devolver(sessao, chamador, None)
            soltos += 1
            continue
        filha = sessao.get(Execucao, filha_id)
        if filha is None:
            _devolver(sessao, chamador, None)
            soltos += 1
        elif filha.estado in ESTADOS_FINAIS:
            _devolver(sessao, chamador, filha)
            soltos += 1
    if soltos:
        sessao.commit()
        logger.info("%d chamador(es) voltaram do sub-fluxo.", soltos)
        from fila import enfileirar

        enfileirar()
    # Nada a soltar: NÃO damos rollback — a sessão pode não ser nossa (mesma razão
    # documentada em `fila.soltar_esperas_vencidas`).
    return soltos


def soltar_sub_fluxos_job() -> None:
    """Entrada do agendador: abre a própria sessão e devolve os chamadores prontos."""
    from sessao import CriadorDeSessao

    sessao = CriadorDeSessao()
    try:
        soltar_chamadores_concluidos(sessao)
    finally:
        sessao.close()
