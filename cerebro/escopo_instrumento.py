"""Escopo do instrumento: do TIME (o de sempre) ou da ORGANIZAÇÃO (Fase 4, 2026-09-29).

Um instrumento da organização aparece para todos os times dela e pode ir para o cinto
de qualquer agente; a identificação (senha, token, login OAuth) é feita UMA vez e
serve a todos. Ele continua tendo um time de ORIGEM (`instrumentos.time_id`): é por
ele que passam as verificações de acesso e a resolução de chaves — a organização é a
mesma, então nada muda para quem usa.

Regras (decisão do maestro):
- só ADMIN cria, promove, rebaixa, configura e mexe nos segredos de um instrumento da
  organização; o operador só o encaixa no cinto;
- rebaixar para "time" é bloqueado enquanto outro time o usa;
- excluir é bloqueado enquanto qualquer agente o usa;
- canal de CONVERSA é sempre do time: um bot da organização só envia avisos e pedidos
  de aprovação (a resposta volta para a execução certa — `mensageria/aprovacao.py`);
- duplicar um time REFERENCIA o instrumento da organização, não copia;
- o custo e o rastro ficam com o time que executou.
"""

from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from modelos import Agente, AgenteInstrumento, Automacao, Instrumento, Time

TIME = "time"
ORGANIZACAO = "organizacao"
ESCOPOS = (TIME, ORGANIZACAO)


def da_organizacao(inst) -> bool:
    return (getattr(inst, "escopo", None) or TIME) == ORGANIZACAO


def _org_do_time(sessao: Session, time_id) -> uuid.UUID | None:
    t = sessao.get(Time, time_id) if time_id else None
    return t.organizacao_id if t else None


def filtro_visiveis(time: Time):
    """Condição SQL: os instrumentos que ESTE time enxerga — os dele e os da
    organização (de qualquer time dela)."""
    times_da_org = select(Time.id).where(Time.organizacao_id == time.organizacao_id)
    return or_(
        Instrumento.time_id == time.id,
        and_(Instrumento.escopo == ORGANIZACAO, Instrumento.time_id.in_(times_da_org)),
    )


def visivel_para_o_time(sessao: Session, inst: Instrumento, time_id) -> bool:
    """O instrumento pode ir para o cinto de um agente deste time?"""
    if inst.time_id == time_id:
        return True
    return da_organizacao(inst) and _org_do_time(sessao, inst.time_id) == _org_do_time(sessao, time_id)


def usado_por(sessao: Session, inst: Instrumento) -> dict:
    """Quem depende deste instrumento: agentes (com o time), as automações em que esses
    agentes aparecem e os pedidos de aprovação que mandam por ele (canal)."""
    agentes = sessao.execute(
        select(Agente.id, Agente.nome, Agente.time_id, Time.nome)
        .join(AgenteInstrumento, AgenteInstrumento.agente_id == Agente.id)
        .join(Time, Time.id == Agente.time_id)
        .where(AgenteInstrumento.instrumento_id == inst.id)
        .order_by(Time.nome, Agente.nome)
    ).all()
    ids_agentes = {str(a[0]) for a in agentes}
    times_dos_agentes = {a[2] for a in agentes}

    automacoes = []
    if times_dos_agentes:
        for auto in sessao.scalars(
            select(Automacao).where(Automacao.time_id.in_(times_dos_agentes)).order_by(Automacao.nome)
        ):
            refs = {
                str(n.get("ref") or n.get("id"))
                for n in _nos(auto.cadeia)
                if isinstance(n, dict)
            }
            if refs & ids_agentes:
                automacoes.append(auto)

    # Pedir aprovação que manda por este canal (referência por configuração).
    instrumentos = []
    if inst.tipo in ("enviar_telegram", "enviar_whatsapp"):
        for outro in sessao.scalars(
            select(Instrumento).where(Instrumento.tipo == "pedir_aprovacao")
        ):
            if (outro.configuracao or {}).get("canal_instrumento_id") == str(inst.id):
                instrumentos.append(outro)

    nomes_times: dict = {}
    for a in agentes:
        nomes_times[a[2]] = a[3]
    for o in instrumentos:
        if o.time_id not in nomes_times:
            t = sessao.get(Time, o.time_id)
            nomes_times[o.time_id] = t.nome if t else "?"
    return {
        "times": [{"id": str(tid), "nome": nome} for tid, nome in nomes_times.items()],
        "agentes": [
            {"id": str(a[0]), "nome": a[1], "time_id": str(a[2]), "time": a[3]} for a in agentes
        ],
        "automacoes": [
            {"id": str(x.id), "nome": x.nome, "time_id": str(x.time_id)} for x in automacoes
        ],
        "instrumentos": [
            {"id": str(o.id), "nome": o.nome, "time_id": str(o.time_id)} for o in instrumentos
        ],
    }


def _nos(cadeia) -> list:
    nos = (cadeia or {}).get("nos") or []
    return list(nos.values()) if isinstance(nos, dict) else list(nos)


def em_uso(uso: dict) -> bool:
    return bool(uso["agentes"] or uso["instrumentos"])


def outros_times(uso: dict, time_id) -> list[str]:
    """Os nomes dos times, além do de origem, que usam o instrumento."""
    return sorted({t["nome"] for t in uso["times"] if t["id"] != str(time_id)})


def resumo_do_uso(uso: dict) -> str:
    """Frase para recusas: quem está usando."""
    partes = [f"{a['nome']} ({a['time']})" for a in uso["agentes"]]
    partes += [f"o pedido de aprovação “{i['nome']}”" for i in uso["instrumentos"]]
    return ", ".join(partes)


def rehospedar_antes_de_excluir_time(sessao: Session, time: Time) -> list[str]:
    """Excluir um time apagaria em cascata os instrumentos da ORGANIZAÇÃO que moram
    nele — e os outros times ficariam sem eles. Antes de excluir, eles mudam de casa:
    para um time que os usa, ou para qualquer outro time da organização. Se não houver
    outro time, vão junto (ninguém mais os usaria). Devolve os nomes rehospedados."""
    movidos: list[str] = []
    outros = sessao.scalars(
        select(Time).where(Time.organizacao_id == time.organizacao_id, Time.id != time.id)
        .order_by(Time.criado_em)
    ).all()
    if not outros:
        return movidos
    for inst in sessao.scalars(
        select(Instrumento).where(Instrumento.time_id == time.id, Instrumento.escopo == ORGANIZACAO)
    ):
        usuarios = {
            a["time_id"] for a in usado_por(sessao, inst)["agentes"] if a["time_id"] != str(time.id)
        }
        destino = next((t for t in outros if str(t.id) in usuarios), outros[0])
        inst.time_id = destino.id
        movidos.append(inst.nome)
    sessao.flush()
    return movidos
