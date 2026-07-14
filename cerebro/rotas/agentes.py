"""Endpoints CRUD de Agentes (Líder e Agentes).

Acesso por papel (Fase 6): membro vê (observador); operador cria/edita; só admin
apaga. Regra do produto (PRODUTO.md §10): cada time tem no máximo um Líder —
garantido por índice parcial no banco e checado aqui para uma mensagem clara (409).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import memoria_agente
from auth import usuario_atual
from esquemas import (
    AgenteCriar,
    AgenteEditar,
    AgenteLer,
    MemoriaAgenteCriar,
    MemoriaAgenteEditar,
    MemoriaAgenteLer,
)
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
    time = time_acessivel(sessao, usuario, time_id, minimo="operador")
    if dados.papel == "lider" and _ja_existe_lider(sessao, time_id):
        raise HTTPException(status.HTTP_409_CONFLICT, CONFLITO_LIDER)
    agente = Agente(time_id=time_id, **dados.model_dump())
    sessao.add(agente)
    sessao.flush()
    auditoria.registrar(
        sessao, usuario=usuario, acao="agente.criado", recurso_tipo="agente",
        recurso_id=agente.id, organizacao_id=time.organizacao_id,
    )
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
    # Detecta alteração de markdown EM PRODUÇÃO antes de aplicar (§3.7: auditável).
    campos_md = ("agent_md", "skill_md", "tools_md", "soul_md")
    md_alterados = [c for c in campos_md if getattr(agente, c) != getattr(dados, c)]
    for campo, valor in dados.model_dump().items():
        setattr(agente, campo, valor)
    if md_alterados:
        auditoria.registrar(
            sessao, usuario=usuario, acao="agente.markdown_alterado",
            recurso_tipo="agente", recurso_id=agente.id,
            organizacao_id=auditoria.org_do_time(sessao, agente.time_id),
            detalhe={"campos": md_alterados},
        )
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
    auditoria.registrar(
        sessao, usuario=usuario, acao="agente.removido", recurso_tipo="agente",
        recurso_id=agente.id,
        organizacao_id=auditoria.org_do_time(sessao, agente.time_id),
    )
    sessao.delete(agente)
    sessao.commit()


# ───────────────────── Memória do agente (fichas por assunto) ─────────────────────
# O agente aprende com o próprio trabalho (runtime). Aqui o HUMANO supervisiona:
# ver/criar/editar/apagar as fichas. Escrita = operador+; leitura = observador (padrão).


@rotas.get("/agentes/{agente_id}/memorias", response_model=list[MemoriaAgenteLer])
def listar_memorias(
    agente_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    agente_acessivel(sessao, usuario, agente_id)
    return memoria_agente.listar(sessao, agente_id)


@rotas.post(
    "/agentes/{agente_id}/memorias",
    response_model=MemoriaAgenteLer,
    status_code=status.HTTP_201_CREATED,
)
def criar_memoria(
    agente_id: uuid.UUID,
    dados: MemoriaAgenteCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    agente = agente_acessivel(sessao, usuario, agente_id, minimo="operador")
    m, resultado = memoria_agente.registrar(
        sessao, agente.id, dados.assunto, dados.conteudo
    )
    if m is None:
        motivo = (
            "A memória deste agente está cheia — edite ou remova fichas."
            if resultado == "recusada:teto"
            else "Assunto e conteúdo são obrigatórios."
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, motivo)
    auditoria.registrar(
        sessao, usuario=usuario, acao="agente.memoria_gravada", recurso_tipo="agente",
        recurso_id=agente.id,
        organizacao_id=auditoria.org_do_time(sessao, agente.time_id),
    )
    sessao.commit()
    sessao.refresh(m)
    return m


@rotas.put("/memorias-agente/{memoria_id}", response_model=MemoriaAgenteLer)
def editar_memoria(
    memoria_id: uuid.UUID,
    dados: MemoriaAgenteEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    m = memoria_agente.obter(sessao, memoria_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memória não encontrada.")
    agente = agente_acessivel(sessao, usuario, m.agente_id, minimo="operador")
    ok, motivo = memoria_agente.editar(
        sessao, m, assunto=dados.assunto, conteudo=dados.conteudo
    )
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, motivo)
    auditoria.registrar(
        sessao, usuario=usuario, acao="agente.memoria_editada", recurso_tipo="agente",
        recurso_id=agente.id,
        organizacao_id=auditoria.org_do_time(sessao, agente.time_id),
    )
    sessao.commit()
    sessao.refresh(m)
    return m


@rotas.delete(
    "/memorias-agente/{memoria_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remover_memoria(
    memoria_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    m = memoria_agente.obter(sessao, memoria_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memória não encontrada.")
    agente = agente_acessivel(sessao, usuario, m.agente_id, minimo="operador")
    auditoria.registrar(
        sessao, usuario=usuario, acao="agente.memoria_apagada", recurso_tipo="agente",
        recurso_id=agente.id,
        organizacao_id=auditoria.org_do_time(sessao, agente.time_id),
    )
    memoria_agente.apagar(sessao, m)
    sessao.commit()
