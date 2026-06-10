"""Endpoints CRUD de Organizações.

A posse é por papel (Etapa 2, Fase 6): quem é membro vê; só admin edita/apaga.
Criar uma organização é permitido a qualquer usuário autenticado e ativo — o
criador entra como `admin` da nova organização na mesma transação (não há, nesta
fase, um "admin da consultoria" acima das organizações; isso chega na Fase 7).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
from auth import usuario_atual
from chaves import provedores_disponiveis
from esquemas import (
    ModeloCriadoraEditar,
    OrganizacaoCriar,
    OrganizacaoEditar,
    OrganizacaoLer,
)
from modelos import Membro, Organizacao, Usuario
from orquestracao.modelos_ia import provedor_do_modelo
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


@rotas.put("/{organizacao_id}/modelo-criadora", response_model=OrganizacaoLer)
def definir_modelo_criadora(
    organizacao_id: uuid.UUID,
    dados: ModeloCriadoraEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Define o modelo da IA de conversa (criadora/companheira) da organização.
    `modelo` nulo volta ao padrão (Opus). Recusa um modelo cujo provedor não tem
    chave resolvível (própria ou da consultoria) — não adianta escolher um modelo
    que vai falhar na hora de conversar."""
    org = organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    if dados.modelo:
        try:
            provedor = provedor_do_modelo(dados.modelo)
        except ValueError:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Modelo de IA '{dados.modelo}' não reconhecido.",
            )
        if not provedores_disponiveis(
            sessao, organizacao_id, tipo_ia="criadora"
        ).get(provedor):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"O modelo '{dados.modelo}' usa {provedor}, mas não há chave de IA "
                "desse provedor (nem própria, nem da consultoria).",
            )
    org.modelo_criadora = dados.modelo or None
    auditoria.registrar(
        sessao, usuario=usuario, acao="organizacao.modelo_criadora",
        recurso_tipo="organizacao", recurso_id=org.id, organizacao_id=org.id,
        detalhe={"modelo": org.modelo_criadora},
    )
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
