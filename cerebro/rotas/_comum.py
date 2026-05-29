"""Helpers de posse compartilhados pelas rotas.

Centralizam a checagem de isolamento (PRODUTO.md): todo recurso é alcançável
só pelo dono atual, subindo a cadeia agente → time → organização → dono.
Levantam 404 quando o recurso não existe ou é de outro dono.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modelos import Agente, Organizacao, Time
from usuario_fixo import usuario_atual_id


def organizacao_do_dono(sessao: Session, organizacao_id: uuid.UUID) -> Organizacao:
    org = sessao.get(Organizacao, organizacao_id)
    if org is None or org.dono_id != usuario_atual_id():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organização não encontrada")
    return org


def time_do_dono(sessao: Session, time_id: uuid.UUID) -> Time:
    time = sessao.get(Time, time_id)
    if time is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Time não encontrado")
    organizacao_do_dono(sessao, time.organizacao_id)
    return time


def agente_do_dono(sessao: Session, agente_id: uuid.UUID) -> Agente:
    agente = sessao.get(Agente, agente_id)
    if agente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente não encontrado")
    time_do_dono(sessao, agente.time_id)
    return agente
