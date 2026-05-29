"""Endpoints CRUD de Organizações.

Na Etapa 1 toda organização pertence ao usuário fixo de testes. As consultas
são sempre filtradas por esse dono — é o que sustenta o isolamento entre
organizações do PRODUTO.md (CLAUDE.md §8) e o ponto a trocar na Etapa 2.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from esquemas import OrganizacaoCriar, OrganizacaoEditar, OrganizacaoLer
from modelos import Organizacao
from sessao import obter_sessao
from usuario_fixo import usuario_atual_id

rotas = APIRouter(prefix="/organizacoes", tags=["organizacoes"])


def _buscar_do_dono(sessao: Session, organizacao_id: uuid.UUID) -> Organizacao:
    """Busca uma organização garantindo que pertence ao usuário atual.
    Levanta 404 se não existe ou é de outro dono."""
    org = sessao.get(Organizacao, organizacao_id)
    if org is None or org.dono_id != usuario_atual_id():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organização não encontrada")
    return org


@rotas.get("", response_model=list[OrganizacaoLer])
def listar(sessao: Session = Depends(obter_sessao)):
    consulta = (
        select(Organizacao)
        .where(Organizacao.dono_id == usuario_atual_id())
        .order_by(Organizacao.criado_em)
    )
    return sessao.scalars(consulta).all()


@rotas.post("", response_model=OrganizacaoLer, status_code=status.HTTP_201_CREATED)
def criar(dados: OrganizacaoCriar, sessao: Session = Depends(obter_sessao)):
    org = Organizacao(nome=dados.nome, dono_id=usuario_atual_id())
    sessao.add(org)
    sessao.commit()
    sessao.refresh(org)
    return org


@rotas.get("/{organizacao_id}", response_model=OrganizacaoLer)
def obter(organizacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    return _buscar_do_dono(sessao, organizacao_id)


@rotas.put("/{organizacao_id}", response_model=OrganizacaoLer)
def editar(
    organizacao_id: uuid.UUID,
    dados: OrganizacaoEditar,
    sessao: Session = Depends(obter_sessao),
):
    org = _buscar_do_dono(sessao, organizacao_id)
    org.nome = dados.nome
    sessao.commit()
    sessao.refresh(org)
    return org


@rotas.delete("/{organizacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(organizacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    org = _buscar_do_dono(sessao, organizacao_id)
    sessao.delete(org)
    sessao.commit()
