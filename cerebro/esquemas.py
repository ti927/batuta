"""Esquemas de entrada e saída da API (Pydantic v2).

Separam o que a API recebe e devolve dos modelos do banco (SQLAlchemy).
Vocabulário do produto em português (CLAUDE.md §14).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Papel = Literal["lider", "agente"]

# ───────────────────────── Organizações ─────────────────────────


class OrganizacaoCriar(BaseModel):
    """Dados para criar uma organização."""

    nome: str = Field(min_length=1, max_length=200)


class OrganizacaoEditar(BaseModel):
    """Dados para editar uma organização."""

    nome: str = Field(min_length=1, max_length=200)


class OrganizacaoLer(BaseModel):
    """Organização como a API a devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    dono_id: uuid.UUID
    criado_em: datetime
    atualizado_em: datetime


# ───────────────────────────── Times ─────────────────────────────


class TimeCriar(BaseModel):
    """Dados para criar um time."""

    nome: str = Field(min_length=1, max_length=200)
    descricao: str | None = None


class TimeEditar(BaseModel):
    """Dados para editar um time."""

    nome: str = Field(min_length=1, max_length=200)
    descricao: str | None = None


class TimeLer(BaseModel):
    """Time como a API o devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organizacao_id: uuid.UUID
    nome: str
    descricao: str | None
    criado_em: datetime
    atualizado_em: datetime


# ──────────────────────────── Agentes ────────────────────────────


class AgenteCriar(BaseModel):
    """Dados para criar um agente (Líder ou Agente)."""

    nome: str = Field(min_length=1, max_length=200)
    papel: Papel
    agent_md: str | None = None
    skill_md: str | None = None
    tools_md: str | None = None
    soul_md: str | None = None
    modelo_ia: str | None = Field(default=None, max_length=100)


class AgenteEditar(BaseModel):
    """Dados para editar um agente."""

    nome: str = Field(min_length=1, max_length=200)
    papel: Papel
    agent_md: str | None = None
    skill_md: str | None = None
    tools_md: str | None = None
    soul_md: str | None = None
    modelo_ia: str | None = Field(default=None, max_length=100)


class AgenteLer(BaseModel):
    """Agente como a API o devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    time_id: uuid.UUID
    nome: str
    papel: Papel
    agent_md: str | None
    skill_md: str | None
    tools_md: str | None
    soul_md: str | None
    modelo_ia: str | None
    criado_em: datetime
    atualizado_em: datetime
