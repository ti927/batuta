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


# ────────────────────────── Instrumentos ─────────────────────────


class InstrumentoCriar(BaseModel):
    """Dados para criar um instrumento. A configuração é validada contra o
    esquema do tipo (o encaixe), não aqui."""

    nome: str = Field(min_length=1, max_length=200)
    tipo: str = Field(min_length=1, max_length=50)
    configuracao: dict = Field(default_factory=dict)


class InstrumentoEditar(BaseModel):
    """Edita um instrumento. O tipo é fixo após a criação; muda-se nome e
    configuração."""

    nome: str = Field(min_length=1, max_length=200)
    configuracao: dict = Field(default_factory=dict)


class InstrumentoLer(BaseModel):
    """Instrumento como a API o devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    time_id: uuid.UUID
    nome: str
    tipo: str
    configuracao: dict | None
    criado_em: datetime
    atualizado_em: datetime


class TipoInstrumentoLer(BaseModel):
    """Um tipo de instrumento disponível no encaixe, para a interface montar
    o formulário de configuração e de acionamento."""

    tipo: str
    nome_exibicao: str
    descricao: str
    esquema_config: dict
    esquema_args: dict


class AcionarInstrumento(BaseModel):
    """Argumentos para acionar um instrumento isoladamente (teste/Fase 4).
    Validados contra o esquema de Args do tipo."""

    argumentos: dict = Field(default_factory=dict)


class VincularInstrumento(BaseModel):
    """Pendura um instrumento no cinto de um agente."""

    instrumento_id: uuid.UUID


# ─────────────────────────── Execução ────────────────────────────


class ExecutarAgente(BaseModel):
    """Entrada para acionar um agente isoladamente (Tarefa 4.2)."""

    entrada: str = Field(min_length=1)
