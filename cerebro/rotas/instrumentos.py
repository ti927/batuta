"""Endpoints de Instrumentos.

CRUD de instrumentos de um time, a lista de tipos disponíveis no encaixe, e o
acionamento isolado de um instrumento (testar / base da Fase 4). A configuração
e os argumentos são validados contra o esquema do tipo (instrumentos/base.py).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import instrumentos as encaixe
from esquemas import (
    AcionarInstrumento,
    InstrumentoCriar,
    InstrumentoEditar,
    InstrumentoLer,
    TipoInstrumentoLer,
)
from modelos import Instrumento
from rotas._comum import time_do_dono
from sessao import obter_sessao

rotas = APIRouter(tags=["instrumentos"])


def _instrumento_do_dono(sessao: Session, instrumento_id: uuid.UUID) -> Instrumento:
    inst = sessao.get(Instrumento, instrumento_id)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrumento não encontrado")
    time_do_dono(sessao, inst.time_id)
    return inst


# Declarado ANTES de /instrumentos/{id} para que "tipos" não seja lido como UUID.
@rotas.get("/instrumentos/tipos", response_model=list[TipoInstrumentoLer])
def listar_tipos():
    return [
        TipoInstrumentoLer(
            tipo=t.tipo,
            nome_exibicao=t.nome_exibicao,
            descricao=t.descricao,
            esquema_config=t.Config.model_json_schema(),
            esquema_args=t.Args.model_json_schema(),
        )
        for t in encaixe.tipos_disponiveis()
    ]


@rotas.get("/times/{time_id}/instrumentos", response_model=list[InstrumentoLer])
def listar(time_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    time_do_dono(sessao, time_id)
    consulta = (
        select(Instrumento)
        .where(Instrumento.time_id == time_id)
        .order_by(Instrumento.criado_em)
    )
    return sessao.scalars(consulta).all()


@rotas.post(
    "/times/{time_id}/instrumentos",
    response_model=InstrumentoLer,
    status_code=status.HTTP_201_CREATED,
)
def criar(
    time_id: uuid.UUID,
    dados: InstrumentoCriar,
    sessao: Session = Depends(obter_sessao),
):
    time_do_dono(sessao, time_id)
    try:
        config_limpa = encaixe.validar_configuracao(dados.tipo, dados.configuracao)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    inst = Instrumento(
        time_id=time_id,
        nome=dados.nome,
        tipo=dados.tipo,
        configuracao=config_limpa,
    )
    sessao.add(inst)
    sessao.commit()
    sessao.refresh(inst)
    return inst


@rotas.get("/instrumentos/{instrumento_id}", response_model=InstrumentoLer)
def obter(instrumento_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    return _instrumento_do_dono(sessao, instrumento_id)


@rotas.put("/instrumentos/{instrumento_id}", response_model=InstrumentoLer)
def editar(
    instrumento_id: uuid.UUID,
    dados: InstrumentoEditar,
    sessao: Session = Depends(obter_sessao),
):
    inst = _instrumento_do_dono(sessao, instrumento_id)
    try:
        config_limpa = encaixe.validar_configuracao(inst.tipo, dados.configuracao)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    inst.nome = dados.nome
    inst.configuracao = config_limpa
    sessao.commit()
    sessao.refresh(inst)
    return inst


@rotas.delete(
    "/instrumentos/{instrumento_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remover(instrumento_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    inst = _instrumento_do_dono(sessao, instrumento_id)
    sessao.delete(inst)
    sessao.commit()


@rotas.post("/instrumentos/{instrumento_id}/acionar")
def acionar(
    instrumento_id: uuid.UUID,
    dados: AcionarInstrumento,
    sessao: Session = Depends(obter_sessao),
):
    """Aciona o instrumento isoladamente, pelo encaixe — testa o tipo e é a
    base do que a Fase 4 fará durante a orquestração."""
    inst = _instrumento_do_dono(sessao, instrumento_id)
    tipo = encaixe.obter_tipo(inst.tipo)
    if tipo is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Tipo de instrumento desconhecido: {inst.tipo!r}",
        )
    try:
        config = tipo.Config.model_validate(inst.configuracao or {})
        args = tipo.Args.model_validate(dados.argumentos or {})
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    return tipo.executar(config, args)
