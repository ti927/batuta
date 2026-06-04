"""Endpoints CRUD de Times.

Acesso por papel (Fase 6): membro vê (observador); operador cria/edita; só admin
apaga ou cria um time novo na organização (MIGRACAO §3.7: criar projetos/times = admin).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import usuario_atual
from esquemas import TimeCriar, TimeEditar, TimeLer
from modelos import Time, Usuario
from rotas._comum import organizacao_acessivel, time_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["times"])


@rotas.get("/organizacoes/{organizacao_id}/times", response_model=list[TimeLer])
def listar(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id)
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
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    time = Time(
        organizacao_id=organizacao_id, nome=dados.nome, descricao=dados.descricao
    )
    sessao.add(time)
    sessao.commit()
    sessao.refresh(time)
    return time


@rotas.get("/times/{time_id}", response_model=TimeLer)
def obter(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return time_acessivel(sessao, usuario, time_id)


@rotas.put("/times/{time_id}", response_model=TimeLer)
def editar(
    time_id: uuid.UUID,
    dados: TimeEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time = time_acessivel(sessao, usuario, time_id, minimo="operador")
    time.nome = dados.nome
    time.descricao = dados.descricao
    sessao.commit()
    sessao.refresh(time)
    return time


@rotas.delete("/times/{time_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time = time_acessivel(sessao, usuario, time_id, minimo="admin")
    sessao.delete(time)
    sessao.commit()
