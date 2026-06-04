"""Helpers de posse compartilhados pelas rotas.

Centralizam a checagem de isolamento (PRODUTO.md): todo recurso é alcançável
só pelo dono atual, subindo a cadeia agente → time → organização → dono.
Levantam 404 quando o recurso não existe ou é de outro dono.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from auth import exigir_papel
from modelos import Agente, Automacao, Execucao, Instrumento, Organizacao, Time, Usuario
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


# ───────────── Acesso por papel (Etapa 2, Fase 6 — substitui os _do_dono) ─────
#
# Cada helper sobe a cadeia recurso → time → organização e exige um papel mínimo
# do usuário NAQUELA organização (via auth.exigir_papel): 404 se o recurso não
# existe OU o usuário não é membro (não revela existência); 403 se é membro com
# papel insuficiente. `minimo` segue a matriz da Fase 6 (observador < operador <
# admin). Os _do_dono acima ficam só até a Tarefa 6.5 trocar todas as rotas.


def organizacao_acessivel(
    sessao: Session, usuario: Usuario, organizacao_id: uuid.UUID, minimo: str = "observador"
) -> Organizacao:
    org = sessao.get(Organizacao, organizacao_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organização não encontrada")
    exigir_papel(sessao, usuario, organizacao_id, minimo)
    return org


def time_acessivel(
    sessao: Session, usuario: Usuario, time_id: uuid.UUID, minimo: str = "observador"
) -> Time:
    time = sessao.get(Time, time_id)
    if time is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Time não encontrado")
    exigir_papel(sessao, usuario, time.organizacao_id, minimo)
    return time


def agente_acessivel(
    sessao: Session, usuario: Usuario, agente_id: uuid.UUID, minimo: str = "observador"
) -> Agente:
    agente = sessao.get(Agente, agente_id)
    if agente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente não encontrado")
    time = sessao.get(Time, agente.time_id)
    exigir_papel(sessao, usuario, time.organizacao_id, minimo)
    return agente


def instrumento_acessivel(
    sessao: Session, usuario: Usuario, instrumento_id: uuid.UUID, minimo: str = "observador"
) -> Instrumento:
    inst = sessao.get(Instrumento, instrumento_id)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrumento não encontrado")
    time = sessao.get(Time, inst.time_id)
    exigir_papel(sessao, usuario, time.organizacao_id, minimo)
    return inst


def automacao_acessivel(
    sessao: Session, usuario: Usuario, automacao_id: uuid.UUID, minimo: str = "observador"
) -> Automacao:
    auto = sessao.get(Automacao, automacao_id)
    if auto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Automação não encontrada")
    time = sessao.get(Time, auto.time_id)
    exigir_papel(sessao, usuario, time.organizacao_id, minimo)
    return auto


def execucao_acessivel(
    sessao: Session, usuario: Usuario, execucao_id: uuid.UUID, minimo: str = "observador"
) -> Execucao:
    execucao = sessao.get(Execucao, execucao_id)
    if execucao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execução não encontrada")
    auto = sessao.get(Automacao, execucao.automacao_id)
    time = sessao.get(Time, auto.time_id)
    exigir_papel(sessao, usuario, time.organizacao_id, minimo)
    return execucao
