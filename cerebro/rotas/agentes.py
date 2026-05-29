"""Endpoints CRUD de Agentes (Líder e Agentes).

Agentes pertencem a um time; o time a uma organização; a organização ao
usuário atual. Toda operação confere essa cadeia de posse.

Regra do produto (PRODUTO.md §10): cada time tem no máximo um Líder. O banco
garante isso por índice parcial; aqui checamos antes para devolver uma mensagem
clara (409) em vez de um erro cru de banco.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from esquemas import AgenteCriar, AgenteEditar, AgenteLer
from modelos import Agente, Organizacao, Time
from sessao import obter_sessao
from usuario_fixo import usuario_atual_id

rotas = APIRouter(tags=["agentes"])


def _time_do_dono(sessao: Session, time_id: uuid.UUID) -> Time:
    time = sessao.get(Time, time_id)
    if time is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Time não encontrado")
    org = sessao.get(Organizacao, time.organizacao_id)
    if org is None or org.dono_id != usuario_atual_id():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Time não encontrado")
    return time


def _agente_do_dono(sessao: Session, agente_id: uuid.UUID) -> Agente:
    agente = sessao.get(Agente, agente_id)
    if agente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente não encontrado")
    _time_do_dono(sessao, agente.time_id)
    return agente


def _ja_existe_lider(
    sessao: Session, time_id: uuid.UUID, ignorar_id: uuid.UUID | None = None
) -> bool:
    consulta = select(Agente.id).where(
        Agente.time_id == time_id, Agente.papel == "lider"
    )
    if ignorar_id is not None:
        consulta = consulta.where(Agente.id != ignorar_id)
    return sessao.scalars(consulta).first() is not None


CONFLITO_LIDER = "Este time já tem um Líder. Cada time pode ter apenas um."


@rotas.get("/times/{time_id}/agentes", response_model=list[AgenteLer])
def listar(time_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    _time_do_dono(sessao, time_id)
    consulta = (
        select(Agente).where(Agente.time_id == time_id).order_by(Agente.criado_em)
    )
    return sessao.scalars(consulta).all()


@rotas.post(
    "/times/{time_id}/agentes",
    response_model=AgenteLer,
    status_code=status.HTTP_201_CREATED,
)
def criar(
    time_id: uuid.UUID, dados: AgenteCriar, sessao: Session = Depends(obter_sessao)
):
    _time_do_dono(sessao, time_id)
    if dados.papel == "lider" and _ja_existe_lider(sessao, time_id):
        raise HTTPException(status.HTTP_409_CONFLICT, CONFLITO_LIDER)
    agente = Agente(time_id=time_id, **dados.model_dump())
    sessao.add(agente)
    sessao.commit()
    sessao.refresh(agente)
    return agente


@rotas.get("/agentes/{agente_id}", response_model=AgenteLer)
def obter(agente_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    return _agente_do_dono(sessao, agente_id)


@rotas.put("/agentes/{agente_id}", response_model=AgenteLer)
def editar(
    agente_id: uuid.UUID, dados: AgenteEditar, sessao: Session = Depends(obter_sessao)
):
    agente = _agente_do_dono(sessao, agente_id)
    if dados.papel == "lider" and _ja_existe_lider(
        sessao, agente.time_id, ignorar_id=agente.id
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, CONFLITO_LIDER)
    for campo, valor in dados.model_dump().items():
        setattr(agente, campo, valor)
    sessao.commit()
    sessao.refresh(agente)
    return agente


@rotas.delete("/agentes/{agente_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(agente_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    agente = _agente_do_dono(sessao, agente_id)
    sessao.delete(agente)
    sessao.commit()
