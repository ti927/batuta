"""Endpoints da IA criadora (Fase 9).

A conversa de criação vive por ORGANIZAÇÃO (o time ainda não existe). Acesso por
papel (matriz da Fase 6, consistente com o resto): observador VÊ; operador
CONVERSA e monta o rascunho; só ADMIN aprova (materializar cria um time, e criar
time é admin). Modo rascunho (MIGRACAO §6.4): conversar/montar nunca escreve nas
tabelas de negócio — só `aprovar` o faz, em ação humana explícita.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
from auth import usuario_atual
from chaves import ORIGEM_LEGADO, resolver_chaves_por_organizacao
from criacao.loop import MODELO_CRIADORA, responder_turno
from criacao.materializar import (
    ConflitoMaterializacao,
    RascunhoInvalido,
    materializar,
)
from esquemas import (
    ConversaCriacaoLer,
    ConversaCriacaoResumo,
    IniciarConversaCriacao,
    MaterializacaoResultado,
    MensagemTurno,
    RespostaTurno,
)
from modelos import ConversaCriacao, Usuario
from orquestracao.modelos_ia import provedor_do_modelo
from rotas._comum import conversa_criacao_acessivel, organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["criacao"])


def _rodar_turno(sessao: Session, conversa: ConversaCriacao, mensagem: str) -> dict:
    """Resolve a chave da criadora (por organização, tipo 'criadora') e roda um
    turno, persistindo a conversa. Devolve {resposta, chips, rascunho, uso}."""
    chaves, origens = resolver_chaves_por_organizacao(
        sessao, conversa.organizacao_id, tipo_ia="criadora"
    )
    origem = origens.get(provedor_do_modelo(MODELO_CRIADORA), ORIGEM_LEGADO)
    resultado = responder_turno(conversa, mensagem, chaves=chaves, origem=origem)
    sessao.commit()
    return resultado


def _exigir_rascunho(conversa: ConversaCriacao) -> None:
    if conversa.estado != "rascunho":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta conversa já foi materializada ou descartada.",
        )


@rotas.post(
    "/organizacoes/{organizacao_id}/conversas-criacao",
    response_model=ConversaCriacaoLer,
    status_code=status.HTTP_201_CREATED,
)
def iniciar(
    organizacao_id: uuid.UUID,
    dados: IniciarConversaCriacao,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="operador")
    conversa = ConversaCriacao(
        organizacao_id=organizacao_id,
        criada_por_id=usuario.id,
        titulo=dados.titulo,
        modo="investigacao",  # toda conversa nasce entendendo o processo
    )
    sessao.add(conversa)
    sessao.flush()
    auditoria.registrar(
        sessao, usuario=usuario, acao="criacao.conversa_iniciada",
        recurso_tipo="conversa_criacao", recurso_id=conversa.id,
        organizacao_id=organizacao_id,
    )
    if dados.mensagem_inicial:
        _rodar_turno(sessao, conversa, dados.mensagem_inicial)
    else:
        sessao.commit()
    sessao.refresh(conversa)
    return conversa


@rotas.get(
    "/organizacoes/{organizacao_id}/conversas-criacao",
    response_model=list[ConversaCriacaoResumo],
)
def listar(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id)
    return sessao.scalars(
        select(ConversaCriacao)
        .where(ConversaCriacao.organizacao_id == organizacao_id)
        .order_by(ConversaCriacao.criado_em.desc())
    ).all()


@rotas.get("/conversas-criacao/{conversa_id}", response_model=ConversaCriacaoLer)
def obter(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return conversa_criacao_acessivel(sessao, usuario, conversa_id)


@rotas.get("/conversas-criacao/{conversa_id}/rascunho")
def obter_rascunho(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    conversa = conversa_criacao_acessivel(sessao, usuario, conversa_id)
    return conversa.rascunho


@rotas.post("/conversas-criacao/{conversa_id}/mensagens", response_model=RespostaTurno)
def enviar_mensagem(
    conversa_id: uuid.UUID,
    dados: MensagemTurno,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    conversa = conversa_criacao_acessivel(sessao, usuario, conversa_id, minimo="operador")
    _exigir_rascunho(conversa)
    return _rodar_turno(sessao, conversa, dados.mensagem)


@rotas.post(
    "/conversas-criacao/{conversa_id}/aprovar",
    response_model=MaterializacaoResultado,
)
def aprovar(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    conversa = conversa_criacao_acessivel(sessao, usuario, conversa_id, minimo="admin")
    try:
        return materializar(sessao, conversa, usuario)
    except RascunhoInvalido as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, {"problemas": e.problemas}
        )
    except ConflitoMaterializacao as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@rotas.post(
    "/conversas-criacao/{conversa_id}/descartar",
    status_code=status.HTTP_204_NO_CONTENT,
)
def descartar(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    conversa = conversa_criacao_acessivel(sessao, usuario, conversa_id, minimo="operador")
    _exigir_rascunho(conversa)
    conversa.estado = "descartada"
    auditoria.registrar(
        sessao, usuario=usuario, acao="criacao.descartada",
        recurso_tipo="conversa_criacao", recurso_id=conversa.id,
        organizacao_id=conversa.organizacao_id,
    )
    sessao.commit()
