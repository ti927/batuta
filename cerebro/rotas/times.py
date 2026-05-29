"""Endpoints CRUD de Times.

Times pertencem a uma organização; a organização pertence ao usuário atual.
Toda operação confere essa cadeia de posse — é o isolamento do PRODUTO.md.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from esquemas import TimeCriar, TimeEditar, TimeLer
from modelos import Organizacao, Time
from sessao import obter_sessao
from usuario_fixo import usuario_atual_id

rotas = APIRouter(tags=["times"])


def _organizacao_do_dono(sessao: Session, organizacao_id: uuid.UUID) -> Organizacao:
    org = sessao.get(Organizacao, organizacao_id)
    if org is None or org.dono_id != usuario_atual_id():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organização não encontrada")
    return org


def _time_do_dono(sessao: Session, time_id: uuid.UUID) -> Time:
    time = sessao.get(Time, time_id)
    if time is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Time não encontrado")
    # Confere que a organização do time pertence ao usuário atual.
    _organizacao_do_dono(sessao, time.organizacao_id)
    return time


@rotas.get("/organizacoes/{organizacao_id}/times", response_model=list[TimeLer])
def listar(organizacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    _organizacao_do_dono(sessao, organizacao_id)
    consulta = (
        select(Time)
        .where(Time.organizacao_id == organizacao_id)
        .order_by(Time.criado_em)
    )
    return sessao.scalars(consulta).all()


@rotas.post(
    "/organizacoes/{organizacao_id}/times",
    response_model=TimeLer,
    status_code=status.HTTP_201_CREATED,
)
def criar(
    organizacao_id: uuid.UUID,
    dados: TimeCriar,
    sessao: Session = Depends(obter_sessao),
):
    _organizacao_do_dono(sessao, organizacao_id)
    time = Time(
        organizacao_id=organizacao_id, nome=dados.nome, descricao=dados.descricao
    )
    sessao.add(time)
    sessao.commit()
    sessao.refresh(time)
    return time


@rotas.get("/times/{time_id}", response_model=TimeLer)
def obter(time_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    return _time_do_dono(sessao, time_id)


@rotas.put("/times/{time_id}", response_model=TimeLer)
def editar(
    time_id: uuid.UUID, dados: TimeEditar, sessao: Session = Depends(obter_sessao)
):
    time = _time_do_dono(sessao, time_id)
    time.nome = dados.nome
    time.descricao = dados.descricao
    sessao.commit()
    sessao.refresh(time)
    return time


@rotas.delete("/times/{time_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(time_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    time = _time_do_dono(sessao, time_id)
    sessao.delete(time)
    sessao.commit()
