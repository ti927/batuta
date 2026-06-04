"""Endpoints de Instrumentos.

CRUD de instrumentos de um time, a lista de tipos disponíveis no encaixe, e o
acionamento isolado de um instrumento. Acesso por papel (Fase 6): membro vê;
operador cria/edita/aciona; só admin apaga.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import instrumentos as encaixe
from auth import usuario_atual
from esquemas import (
    AcionarInstrumento,
    InstrumentoCriar,
    InstrumentoEditar,
    InstrumentoLer,
    TipoInstrumentoLer,
)
from modelos import Instrumento, Usuario
from rotas._comum import instrumento_acessivel, time_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["instrumentos"])


# Declarado ANTES de /instrumentos/{id} para que "tipos" não seja lido como UUID.
@rotas.get("/instrumentos/tipos", response_model=list[TipoInstrumentoLer])
def listar_tipos(usuario: Usuario = Depends(usuario_atual)):
    """O catálogo de tipos do encaixe não é de nenhuma organização; basta estar
    autenticado para consultá-lo."""
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
def listar(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time_acessivel(sessao, usuario, time_id)
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
    usuario: Usuario = Depends(usuario_atual),
):
    time = time_acessivel(sessao, usuario, time_id, minimo="operador")
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
    sessao.flush()
    auditoria.registrar(
        sessao, usuario=usuario, acao="instrumento.criado",
        recurso_tipo="instrumento", recurso_id=inst.id,
        organizacao_id=time.organizacao_id,
    )
    sessao.commit()
    sessao.refresh(inst)
    return inst


@rotas.get("/instrumentos/{instrumento_id}", response_model=InstrumentoLer)
def obter(
    instrumento_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return instrumento_acessivel(sessao, usuario, instrumento_id)


@rotas.put("/instrumentos/{instrumento_id}", response_model=InstrumentoLer)
def editar(
    instrumento_id: uuid.UUID,
    dados: InstrumentoEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="operador")
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
def remover(
    instrumento_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="admin")
    auditoria.registrar(
        sessao, usuario=usuario, acao="instrumento.removido",
        recurso_tipo="instrumento", recurso_id=inst.id,
        organizacao_id=auditoria.org_do_time(sessao, inst.time_id),
    )
    sessao.delete(inst)
    sessao.commit()


@rotas.post("/instrumentos/{instrumento_id}/acionar")
def acionar(
    instrumento_id: uuid.UUID,
    dados: AcionarInstrumento,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Aciona o instrumento isoladamente, pelo encaixe — testa o tipo e é a
    base do que a Fase 4 fará durante a orquestração."""
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="operador")
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
