"""Escopo do Batuta-MCP: da identidade do token ao `Usuario` e ao acesso por org/papel.

Ponte entre o token OAuth (que carrega só o `subject = Usuario.id`) e o banco. Toda
ferramenta do MCP começa resolvendo QUEM está falando (`usuario_do_token`) e então usa
os guardas canônicos de `rotas/_comum` (`time_acessivel`/`organizacao_acessivel`/…),
que sobem recurso → time → organização e exigem o papel mínimo. Nada é duplicado: é a
MESMA autorização das rotas REST, só que dirigida pelo token do MCP em vez do
`usuario_atual` do FastAPI.

A revogação é ao vivo: `usuario_do_token` relê `usuarios.ativo` e os guardas releem
`membros` a cada chamada — desativar o consultor ou tirá-lo da org corta o acesso na
hora, mesmo com um token ainda válido (mesma garantia do `auth.py`).
"""

import uuid

from mcp.server.auth.middleware.auth_context import get_access_token
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modelos import Agente, Membro, Organizacao, Time, Usuario

# Reexporta os guardas de acesso — uma fonte só de autorização (rotas + MCP).
from rotas._comum import (  # noqa: F401
    agente_acessivel,
    automacao_acessivel,
    conversa_acessivel,
    conversa_criacao_acessivel,
    execucao_acessivel,
    instrumento_acessivel,
    organizacao_acessivel,
    time_acessivel,
)


class SemAcesso(Exception):
    """Não dá para identificar o consultor a partir do token (ausente/inválido/inativo)."""


# ───────────────────────── Resolução de identidade ─────────────────────────

def usuario_por_auth_id(sessao: Session, auth_id: uuid.UUID) -> Usuario | None:
    """O `Usuario` do Batuta ligado a um login do Supabase (`auth_id`), ou None."""
    return sessao.scalars(
        select(Usuario).where(Usuario.auth_id == auth_id)
    ).first()


def usuario_ativo_por_id(sessao: Session, usuario_id: uuid.UUID) -> Usuario | None:
    """O `Usuario` por id, só se estiver ATIVO (revogação imediata)."""
    usuario = sessao.get(Usuario, usuario_id)
    return usuario if (usuario and usuario.ativo) else None


def usuario_do_sub(sessao: Session, sub: str | None) -> Usuario:
    """O consultor a partir do `subject` do token (id do `Usuario`). Levanta `SemAcesso`
    se ausente/inválido/inativo. Recebe o `sub` explicitamente porque o trabalho de banco
    roda numa thread, onde o contextvar do token não está disponível."""
    if not sub:
        raise SemAcesso("Token sem identificação de usuário.")
    try:
        usuario_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        raise SemAcesso("Identificação de usuário inválida no token.")
    usuario = usuario_ativo_por_id(sessao, usuario_id)
    if usuario is None:
        raise SemAcesso("Seu acesso não está mais ativo. Entre de novo.")
    return usuario


def sub_do_token() -> str | None:
    """O `subject` (id do `Usuario`) do access token da chamada atual, ou None. Chame no
    contexto async da ferramenta (onde o contextvar do token está setado)."""
    token = get_access_token()
    return token.subject if token else None


def usuario_do_token(sessao: Session) -> Usuario:
    """Atalho: resolve o consultor a partir do token da chamada atual (contexto async)."""
    return usuario_do_sub(sessao, sub_do_token())


# ───────────────────────── Consultas escopadas ─────────────────────────

def organizacoes_do_usuario(sessao: Session, usuario: Usuario) -> list[tuple[Organizacao, str]]:
    """As organizações em que o consultor é membro, com o papel dele em cada uma."""
    linhas = sessao.execute(
        select(Organizacao, Membro.papel)
        .join(Membro, Membro.organizacao_id == Organizacao.id)
        .where(Membro.usuario_id == usuario.id)
        .order_by(Organizacao.nome)
    ).all()
    return [(org, papel) for org, papel in linhas]


def times_do_usuario(
    sessao: Session, usuario: Usuario, organizacao_id: uuid.UUID | None = None
) -> list[Time]:
    """Os times que o consultor pode ver — de todas as suas organizações, ou de uma
    específica. O acesso vem sempre via `Membro` (não há vínculo direto usuário↔time)."""
    consulta = (
        select(Time)
        .join(Membro, Membro.organizacao_id == Time.organizacao_id)
        .where(Membro.usuario_id == usuario.id)
        .order_by(Time.nome)
    )
    if organizacao_id is not None:
        consulta = consulta.where(Time.organizacao_id == organizacao_id)
    return list(sessao.scalars(consulta).all())


def contar_agentes(sessao: Session, time_id: uuid.UUID) -> int:
    return sessao.scalar(
        select(func.count()).select_from(Agente).where(Agente.time_id == time_id)
    ) or 0
