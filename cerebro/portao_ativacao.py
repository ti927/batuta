"""A parede de ativação (o paradigma novo da IA criadora).

Tudo o que a IA monta é REAL desde o começo, mas dorme: a automação nasce inativa
e nada roda até alguém ATIVAR. A única parede técnica na ativação é o portão de
aprovação humana antes de uma AÇÃO IRREVERSÍVEL (publicar, enviar, gravar em sistema
externo): um agente que use um instrumento irreversível só pode ser ativado se a
cadeia pausar para um humano ANTES de ele rodar.

Semântica do portão (CUIDADO — fonte de bug clássico): o motor lê `pausa_humano`
no NÓ (`orquestracao/cadeia.py`: `no.get("pausa_humano")`), não na saída. Pausar um
nó significa "depois deste agente, espere a aprovação humana antes de seguir". Logo,
para blindar um agente irreversível X, TODO nó que tem uma saída levando a X precisa
ter `pausa_humano: true` — e X não pode ser o início (não há nó antes dele).

Reaproveitado pela rota de automações (vira HTTP 422) e pela ferramenta da IA (vira
texto de volta para ela corrigir na conversa)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import instrumentos as encaixe
from modelos import Agente, AgenteInstrumento, Instrumento


def coletar_agentes(
    sessao: Session, time_id: uuid.UUID
) -> tuple[dict[str, str], set[str]]:
    """Devolve `(nomes, irreversiveis)` para o time:
    - `nomes`: {agente_id(str): nome} de TODOS os agentes (para mensagens claras).
    - `irreversiveis`: ids dos agentes com ao menos um instrumento de ação
      irreversível no cinto."""
    nomes = {
        str(aid): nome
        for aid, nome in sessao.execute(
            select(Agente.id, Agente.nome).where(Agente.time_id == time_id)
        ).all()
    }
    irreversiveis: set[str] = set()
    for aid, tipo, configuracao, exige in sessao.execute(
        select(
            AgenteInstrumento.agente_id,
            Instrumento.tipo,
            Instrumento.configuracao,
            Instrumento.exige_aprovacao,
        )
        .join(Instrumento, Instrumento.id == AgenteInstrumento.instrumento_id)
        .join(Agente, Agente.id == AgenteInstrumento.agente_id)
        .where(Agente.time_id == time_id)
    ).all():
        # Resolve por INSTÂNCIA: o interruptor manda; senão deriva do tipo+config
        # (REST pelo método, SQL pelo somente_leitura). Uma consulta não exige portão.
        if encaixe.exige_portao(tipo, configuracao, exige):
            irreversiveis.add(str(aid))
    return nomes, irreversiveis


def problemas_de_portao(
    cadeia: dict, nomes: dict[str, str], irreversiveis: set[str]
) -> list[str]:
    """Lista, em português, os problemas de portão que impedem a ativação (vazia =
    pode ativar). Pura e testável: não toca no banco."""
    problemas: list[str] = []
    nos = (cadeia or {}).get("nos") or {}
    inicio = (cadeia or {}).get("inicio")

    def nome(aid: str) -> str:
        return nomes.get(aid, "agente")

    for aid in sorted(irreversiveis, key=nome):
        # Início: roda primeiro, não há como pausar antes dele.
        if aid == inicio:
            problemas.append(
                f"O agente '{nome(aid)}' faz uma ação que não dá para desfazer e é "
                f"o início da automação — não há passo antes dele para a aprovação. "
                f"Ponha um agente antes, com portão de aprovação humana."
            )
            continue
        # Nós cujas saídas levam a este agente (os "anteriores" a ele na cadeia).
        anteriores = [
            no_id
            for no_id, no in nos.items()
            if any(
                (s or {}).get("destino") == aid for s in (no or {}).get("saidas") or []
            )
        ]
        if not anteriores:
            # Não é início nem destino de ninguém: não roda nesta automação → sem risco.
            continue
        sem_portao = [
            no_id
            for no_id in anteriores
            if not bool((nos.get(no_id) or {}).get("pausa_humano"))
        ]
        if sem_portao:
            quais = ", ".join(f"'{nome(n)}'" for n in sem_portao)
            problemas.append(
                f"O agente '{nome(aid)}' faz uma ação que não dá para desfazer "
                f"(publicar/enviar/gravar), mas o passo anterior ({quais}) não tem "
                f"portão de aprovação humana antes dele. Marque a pausa para humano "
                f"nesse passo, para alguém aprovar antes de a ação acontecer."
            )
    return problemas


def validar(sessao: Session, time_id: uuid.UUID, cadeia: dict) -> list[str]:
    """Conveniência: coleta os agentes do time e devolve os problemas de portão
    para a `cadeia` dada (a que está sendo ativada). Vazia = pode ativar."""
    nomes, irreversiveis = coletar_agentes(sessao, time_id)
    return problemas_de_portao(cadeia, nomes, irreversiveis)
