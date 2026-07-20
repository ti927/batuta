"""Consulta do banco de logs (observabilidade).

`GET /logs` — restrito aos admins da consultoria. Filtra e pagina a tabela `evento_log`
para diagnóstico ("de onde/quem/quando/qual erro"). Ainda SEM tela (a busca visual é fase
futura); por ora serve a API, para o operador e a IA irem direto aos logs.

Por padrão esconde `ambiente=local` (eventos de dev não interessam à visão de produção); um
filtro explícito de `ambiente` os traz de volta — inclusive para flagrar um `local` onde não
devia (a lição do cérebro local).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from auth import usuario_atual
from consultoria import exigir_admin_consultoria
from modelos import EventoLog, Usuario
from sessao import obter_sessao

rotas = APIRouter(tags=["logs"])


class EventoLogLer(BaseModel):
    id: uuid.UUID
    criado_em: datetime
    nivel: str
    categoria: str
    acao: str
    resultado: str | None
    usuario_id: uuid.UUID | None
    organizacao_id: uuid.UUID | None
    time_id: uuid.UUID | None
    recurso_tipo: str | None
    recurso_id: uuid.UUID | None
    request_id: str | None
    host: str | None
    commit: str | None
    ambiente: str | None
    ip_cliente: str | None
    origem: str | None
    http_metodo: str | None
    rota: str | None
    http_status: int | None
    latencia_ms: int | None
    erro_texto: str | None
    detalhe: dict | None

    model_config = {"from_attributes": True}


@rotas.get("/logs", response_model=list[EventoLogLer])
def listar_logs(
    usuario: Usuario = Depends(usuario_atual),
    sessao: Session = Depends(obter_sessao),
    nivel: str | None = None,
    categoria: str | None = None,
    usuario_id: uuid.UUID | None = None,
    organizacao_id: uuid.UUID | None = None,
    time_id: uuid.UUID | None = None,
    request_id: str | None = None,
    origem: str | None = None,
    ambiente: str | None = None,
    texto: str | None = None,
    antes: datetime | None = None,  # cursor: eventos com criado_em < antes
    limite: int = Query(100, ge=1, le=500),
) -> list[EventoLog]:
    """Busca paginada no banco de logs (mais recente → mais antigo). `antes` pagina; os
    demais parâmetros filtram. Só admin da consultoria."""
    exigir_admin_consultoria(usuario)
    q = select(EventoLog)
    if nivel:
        q = q.where(EventoLog.nivel == nivel.lower())
    if categoria:
        q = q.where(EventoLog.categoria == categoria)
    if usuario_id:
        q = q.where(EventoLog.usuario_id == usuario_id)
    if organizacao_id:
        q = q.where(EventoLog.organizacao_id == organizacao_id)
    if time_id:
        q = q.where(EventoLog.time_id == time_id)
    if request_id:
        q = q.where(EventoLog.request_id == request_id)
    if origem:
        q = q.where(EventoLog.origem == origem)
    if ambiente:
        q = q.where(EventoLog.ambiente == ambiente)
    else:
        q = q.where(or_(EventoLog.ambiente != "local", EventoLog.ambiente.is_(None)))
    if texto:
        termo = f"%{texto}%"
        q = q.where(or_(EventoLog.acao.ilike(termo), EventoLog.erro_texto.ilike(termo)))
    if antes:
        q = q.where(EventoLog.criado_em < antes)
    q = q.order_by(EventoLog.criado_em.desc()).limit(limite)
    return list(sessao.scalars(q).all())
