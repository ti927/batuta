"""Helpers de acesso por papel, compartilhados pelas rotas (Etapa 2, Fase 6).

Centralizam o isolamento: cada helper sobe a cadeia recurso → time → organização
e exige um papel mínimo do usuário NAQUELA organização (via `auth.exigir_papel`).
Semântica: 404 se o recurso não existe OU o usuário não é membro (não revela
existência a quem é de fora); 403 se é membro, mas com papel insuficiente.
`minimo` segue a matriz da Fase 6: observador < operador < admin.

Substituem os antigos `*_do_dono` (baseados no usuário fixo de testes), removidos
na Tarefa 6.5 junto com a aposentadoria de `usuario_fixo`.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from auth import exigir_papel
from modelos import Agente, Automacao, Execucao, Instrumento, Organizacao, Time, Usuario


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
