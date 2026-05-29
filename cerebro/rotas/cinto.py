"""O cinto: o vínculo entre agentes e instrumentos.

Cada agente tem um cinto próprio (PRODUTO.md §13). Aqui se pendura e se tira
instrumento do cinto, e se lê o cinto. Um instrumento só pode ser pendurado num
agente do mesmo time — é o que mantém o isolamento e a coerência.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from esquemas import InstrumentoLer, VincularInstrumento
from modelos import AgenteInstrumento, Instrumento
from rotas._comum import agente_do_dono
from sessao import obter_sessao

rotas = APIRouter(tags=["cinto"])


@rotas.get("/agentes/{agente_id}/instrumentos", response_model=list[InstrumentoLer])
def listar_cinto(agente_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    agente_do_dono(sessao, agente_id)
    consulta = (
        select(Instrumento)
        .join(
            AgenteInstrumento,
            AgenteInstrumento.instrumento_id == Instrumento.id,
        )
        .where(AgenteInstrumento.agente_id == agente_id)
        .order_by(Instrumento.nome)
    )
    return sessao.scalars(consulta).all()


@rotas.post(
    "/agentes/{agente_id}/instrumentos",
    response_model=InstrumentoLer,
    status_code=status.HTTP_201_CREATED,
)
def vincular(
    agente_id: uuid.UUID,
    dados: VincularInstrumento,
    sessao: Session = Depends(obter_sessao),
):
    agente = agente_do_dono(sessao, agente_id)
    inst = sessao.get(Instrumento, dados.instrumento_id)
    # O instrumento precisa existir e ser do mesmo time do agente.
    if inst is None or inst.time_id != agente.time_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Instrumento não encontrado neste time"
        )
    ja = sessao.get(AgenteInstrumento, (agente_id, inst.id))
    if ja is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Instrumento já está no cinto deste agente"
        )
    sessao.add(AgenteInstrumento(agente_id=agente_id, instrumento_id=inst.id))
    sessao.commit()
    return inst


@rotas.delete(
    "/agentes/{agente_id}/instrumentos/{instrumento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def desvincular(
    agente_id: uuid.UUID,
    instrumento_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
):
    agente_do_dono(sessao, agente_id)
    vinculo = sessao.get(AgenteInstrumento, (agente_id, instrumento_id))
    if vinculo is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Este instrumento não está no cinto"
        )
    sessao.delete(vinculo)
    sessao.commit()
