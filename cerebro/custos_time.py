"""Custo de um time separado entre a IA DOS AGENTES e os INSTRUMENTOS (2026-09-26).

Um agente que pensa com o Claude e aciona um instrumento que gera imagem com a OpenAI
tem DOIS custos. O banco já os guardava em categorias diferentes, mas o resumo do time
mostrava um número só — e o custo de instrumento não dizia QUAL instrumento gastou.

Fonte única do corte, usada pela aba Início do time (`rotas/times.py`) e pela
ferramenta `ver_uso` do MCP: se cada uma somasse do seu jeito, um dia mostrariam
números diferentes para o mesmo time.

Mesmas fontes do custo acumulado de sempre: passos das execuções das automações do
time + uso dos turnos de atendimento dos canais do time. A IA criadora é da
organização e fica de fora.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import precos
from modelos import (
    Agente,
    Automacao,
    Conversa,
    Execucao,
    Instrumento,
    MensagemConversa,
    PassoExecucao,
)


def _uuid(valor) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(valor)) if valor else None
    except ValueError:
        return None


def _pares_do_time(sessao: Session, time_id: uuid.UUID):
    """(entrada de uso, agente_id) de tudo que o time gastou."""
    passos = sessao.scalars(
        select(PassoExecucao)
        .join(Execucao, Execucao.id == PassoExecucao.execucao_id)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .where(Automacao.time_id == time_id)
    ).all()
    for p in passos:
        for e in precos.entradas_dos_passos([p]):
            yield e, p.agente_id

    linhas = sessao.execute(
        select(MensagemConversa, Conversa.destino_tipo, Conversa.destino_id)
        .join(Conversa, Conversa.id == MensagemConversa.conversa_id)
        .join(Instrumento, Instrumento.id == Conversa.instrumento_id)
        .where(Instrumento.time_id == time_id)
        .where(MensagemConversa.uso.isnot(None))
    ).all()
    for msg, destino_tipo, destino_id in linhas:
        # Desde 2026-09-26 cada entrada do turno carrega o agente que respondeu. Antes
        # disso, a melhor pista é o destino da conversa quando ele é um agente.
        reserva = destino_id if destino_tipo == "agente" else None
        for e in precos.entradas_das_mensagens([msg]):
            yield e, e.get("agente_id") or reserva


def custos_do_time(sessao: Session, time_id: uuid.UUID) -> dict:
    """{custo_usd, ia_agentes_usd, instrumentos_usd, por_agente, por_instrumento} —
    as listas vêm com o NOME ATUAL de cada agente/instrumento e ordenadas do mais caro
    para o mais barato."""
    corte = precos.separar_custos(_pares_do_time(sessao, time_id))

    ids_agentes = [i for i in (_uuid(k) for k in corte["por_agente"]) if i]
    nomes_agentes = dict(
        sessao.execute(select(Agente.id, Agente.nome).where(Agente.id.in_(ids_agentes))).all()
    ) if ids_agentes else {}
    por_agente = []
    for chave, v in corte["por_agente"].items():
        aid = _uuid(chave)
        por_agente.append({
            "agente_id": str(aid) if aid else None,
            "nome": nomes_agentes.get(aid) if aid else None,
            "ia_usd": round(v["ia_usd"], 6),
            "instrumentos_usd": round(v["instrumentos_usd"], 6),
            "total_usd": round(v["ia_usd"] + v["instrumentos_usd"], 6),
        })
    por_agente.sort(key=lambda a: a["total_usd"], reverse=True)

    ids_inst = [i for i in (_uuid(v["instrumento_id"]) for v in corte["por_instrumento"].values()) if i]
    atuais = {
        i.id: i for i in sessao.scalars(select(Instrumento).where(Instrumento.id.in_(ids_inst)))
    } if ids_inst else {}
    por_instrumento = []
    for v in corte["por_instrumento"].values():
        atual = atuais.get(_uuid(v["instrumento_id"]))
        por_instrumento.append({
            **v,
            # O nome de hoje, se o instrumento ainda existe; senão o da hora da chamada.
            "nome": atual.nome if atual else v["nome"],
            "tipo": atual.tipo if atual else v["tipo"],
            "custo_usd": round(v["custo_usd"], 6),
        })
    por_instrumento.sort(key=lambda i: i["custo_usd"], reverse=True)

    return {
        "custo_usd": round(corte["ia_agentes_usd"] + corte["instrumentos_usd"], 6),
        "ia_agentes_usd": corte["ia_agentes_usd"],
        "instrumentos_usd": corte["instrumentos_usd"],
        "por_agente": por_agente,
        "por_instrumento": por_instrumento,
    }
