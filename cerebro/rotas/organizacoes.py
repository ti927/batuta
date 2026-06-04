"""Endpoints CRUD de Organizações.

A posse é por papel (Etapa 2, Fase 6): quem é membro vê; só admin edita/apaga.
Criar uma organização é permitido a qualquer usuário autenticado e ativo — o
criador entra como `admin` da nova organização na mesma transação (não há, nesta
fase, um "admin da consultoria" acima das organizações; isso chega na Fase 7).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
from auth import usuario_atual
from esquemas import OrganizacaoCriar, OrganizacaoEditar, OrganizacaoLer
from modelos import Membro, Organizacao, Usuario
from rotas._comum import organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(prefix="/organizacoes", tags=["organizacoes"])


@rotas.get("", response_model=list[OrganizacaoLer])
def listar(
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """As organizações em que o usuário é membro (qualquer papel)."""
    consulta = (
        select(Organizacao)
        .join(Membro, Membro.organizacao_id == Organizacao.id)
        .where(Membro.usuario_id == usuario.id)
        .order_by(Organizacao.criado_em)
    )
    return sessao.scalars(consulta).all()


@rotas.post("", response_model=OrganizacaoLer, status_code=status.HTTP_201_CREATED)
def criar(
    dados: OrganizacaoCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    org = Organizacao(nome=dados.nome, dono_id=usuario.id)
    sessao.add(org)
    sessao.flush()  # garante org.id antes de criar o vínculo de membro
    sessao.add(
        Membro(usuario_id=usuario.id, organizacao_id=org.id, papel="admin")
    )
    auditoria.registrar(
        sessao, usuario=usuario, acao="organizacao.criada",
        recurso_tipo="organizacao", recurso_id=org.id, organizacao_id=org.id,
    )
    sessao.commit()
    sessao.refresh(org)
    return org


@rotas.get("/{organizacao_id}", response_model=OrganizacaoLer)
def obter(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return organizacao_acessivel(sessao, usuario, organizacao_id)


@rotas.put("/{organizacao_id}", response_model=OrganizacaoLer)
def editar(
    organizacao_id: uuid.UUID,
    dados: OrganizacaoEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    org = organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    org.nome = dados.nome
    sessao.commit()
    sessao.refresh(org)
    return org


@rotas.delete("/{organizacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    org = organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    auditoria.registrar(
        sessao, usuario=usuario, acao="organizacao.removida",
        recurso_tipo="organizacao", recurso_id=org.id, organizacao_id=org.id,
    )
    sessao.delete(org)
    sessao.commit()
