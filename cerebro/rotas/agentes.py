"""Endpoints CRUD de Agentes (Líder e Agentes).

Acesso por papel (Fase 6): membro vê (observador); operador cria/edita; só admin
apaga. Regra do produto (PRODUTO.md §10): cada time tem no máximo um Líder —
garantido por índice parcial no banco e checado aqui para uma mensagem clara (409).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import usuario_atual
from esquemas import AgenteCriar, AgenteEditar, AgenteLer
from modelos import Agente, Usuario
from rotas._comum import agente_acessivel, time_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["agentes"])


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
def listar(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time_acessivel(sessao, usuario, time_id)
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
    time_id: uuid.UUID,
    dados: AgenteCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time_acessivel(sessao, usuario, time_id, minimo="operador")
    if dados.papel == "lider" and _ja_existe_lider(sessao, time_id):
        raise HTTPException(status.HTTP_409_CONFLICT, CONFLITO_LIDER)
    agente = Agente(time_id=time_id, **dados.model_dump())
    sessao.add(agente)
    sessao.commit()
    sessao.refresh(agente)
    return agente


@rotas.get("/agentes/{agente_id}", response_model=AgenteLer)
def obter(
    agente_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return agente_acessivel(sessao, usuario, agente_id)


@rotas.put("/agentes/{agente_id}", response_model=AgenteLer)
def editar(
    agente_id: uuid.UUID,
    dados: AgenteEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    agente = agente_acessivel(sessao, usuario, agente_id, minimo="operador")
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
def remover(
    agente_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    agente = agente_acessivel(sessao, usuario, agente_id, minimo="admin")
    sessao.delete(agente)
    sessao.commit()
