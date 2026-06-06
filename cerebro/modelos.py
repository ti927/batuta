"""Modelos do core do Batuta (SQLAlchemy).

Vocabulário do produto em português (CLAUDE.md §14). Toda tabela de negócio
carrega, direta ou indiretamente, o vínculo com a organização, sustentando o
isolamento entre organizações e times do PRODUTO.md.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IdData:
    """Mixin: identificador único e datas de criação/atualização."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Usuario(IdData, Base):
    """Usuário do Batuta. Na Etapa 1 existe só o usuário fixo de testes;
    na Etapa 2 isto é substituído pelo Supabase Auth."""

    __tablename__ = "usuarios"
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    # Vínculo ao Supabase Auth (o `sub` do JWT). Nulo até o usuário aceitar o
    # convite e logar a primeira vez; é o que liga a identidade real ao registro.
    auth_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=True
    )
    # Desativação (MIGRACAO §3.7): um usuário inativo não acessa nada, mas o
    # registro e seu histórico permanecem.
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class Organizacao(IdData, Base):
    """A empresa. Espaço onde tudo daquela empresa vive."""

    __tablename__ = "organizacoes"
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    dono_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False
    )


class Time(IdData, Base):
    """A unidade de trabalho. Pertence a uma organização."""

    __tablename__ = "times"
    organizacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)


class Agente(IdData, Base):
    """Líder ou Agente. A distinção é o campo 'papel'. Cada time tem no
    máximo um agente com papel 'lider' (garantido por índice parcial)."""

    __tablename__ = "agentes"
    time_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("times.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    papel: Mapped[str] = mapped_column(String(20), nullable=False)  # "lider" | "agente"
    agent_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    tools_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    soul_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    modelo_ia: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index(
            "uq_um_lider_por_time",
            "time_id",
            unique=True,
            postgresql_where=text("papel = 'lider'"),
        ),
    )


class Instrumento(IdData, Base):
    """Uma capacidade que um agente invoca. Pertence a um time. A configuração
    é flexível (JSONB) porque cada tipo de instrumento pede campos diferentes."""

    __tablename__ = "instrumentos"
    time_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("times.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    configuracao: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AgenteInstrumento(Base):
    """Ligação N-para-N: instrumentos no cinto de um agente."""

    __tablename__ = "agente_instrumentos"
    agente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentes.id", ondelete="CASCADE"), primary_key=True
    )
    instrumento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instrumentos.id", ondelete="CASCADE"), primary_key=True
    )


class Automacao(IdData, Base):
    """A definição de um fluxo: o gatilho e a cadeia ordenada de agentes."""

    __tablename__ = "automacoes"
    time_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("times.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo_gatilho: Mapped[str] = mapped_column(String(50), nullable=False)
    configuracao_gatilho: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cadeia: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    ativa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class Execucao(IdData, Base):
    """O registro de cada vez que uma automação roda."""

    __tablename__ = "execucoes"
    automacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("automacoes.id", ondelete="CASCADE"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'aguardando'")
    )  # aguardando | em_andamento | aguardando_humano | concluida | falhou
    entrada: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resultado: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    iniciada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finalizada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PassoExecucao(IdData, Base):
    """Cada passo de uma execução: o agente que processou, o que recebeu e
    produziu. É o que permite inspecionar a orquestração passo a passo.
    O agente é nullable com SET NULL para preservar o histórico mesmo que o
    agente seja removido depois (auditoria)."""

    __tablename__ = "passos_execucao"
    execucao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execucoes.id", ondelete="CASCADE"), nullable=False
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    agente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agentes.id", ondelete="SET NULL"), nullable=True
    )
    entrada: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    saida: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'aguardando'")
    )
    iniciado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finalizado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ───────────────────── Identidade e acesso (Etapa 2, Fase 6) ─────────────────


class Membro(IdData, Base):
    """Vínculo de um usuário a uma organização, com seu papel de acesso
    (admin | operador | observador). É a fonte de permissão da Etapa 2 — substitui,
    na prática, o antigo 'dono' único da organização. Um usuário pode ser membro de
    várias organizações, com papel distinto em cada (índice único do par)."""

    __tablename__ = "membros"
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    organizacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False
    )
    papel: Mapped[str] = mapped_column(String(20), nullable=False)  # admin|operador|observador

    __table_args__ = (
        Index("uq_membro_usuario_org", "usuario_id", "organizacao_id", unique=True),
    )


class Convite(IdData, Base):
    """Convite para um email entrar numa organização com um papel. Ninguém se
    autoinscreve (MIGRACAO §3.7): um admin emite o convite; o convidado aceita e
    vira Membro."""

    __tablename__ = "convites"
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    organizacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False
    )
    papel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pendente'")
    )  # pendente|aceito|expirado|revogado
    convidado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    expira_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (Index("ix_convite_email_org", "email", "organizacao_id"),)


class Auditoria(IdData, Base):
    """Registro nominal de uma ação sensível (quem, o quê, quando, em qual recurso).
    `usuario_id` é SET NULL para preservar o registro mesmo que o usuário seja
    removido (igual a PassoExecucao.agente_id). `recurso_id`/`organizacao_id` são
    UUID soltos (não FK) de propósito: a auditoria sobrevive à exclusão do recurso."""

    __tablename__ = "auditoria"
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    acao: Mapped[str] = mapped_column(String(60), nullable=False)
    recurso_tipo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    recurso_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    organizacao_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    detalhe: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


# ───────────────────── Cofre de chaves (Etapa 2, Fase 7) ─────────────────────


class ChaveApi(IdData, Base):
    """Cofre criptografado de chaves de API de IA (PRODUTO §26, MIGRACAO Viradas 4/5).

    Cada chave pertence a uma organização (o cliente). Quando `organizacao_id` é
    nulo, é a CHAVE-MÃE DA CONSULTORIA — o fallback usado quando o cliente não tem
    chave própria. O valor fica sempre cifrado em `valor_cifrado` e NUNCA é
    reexibido (PRODUTO §26): a interface mostra apenas `ultimos4`.

    Os três tipos de IA (executora | criadora | companheira) são modelados desde
    já (MIGRACAO Virada 4); na Fase 7 só a 'executora' é consumida pelo motor.

    Há no máximo uma chave por (organização, tipo de IA, provedor) — inclusive
    para a chave-mãe (índice com NULLS NOT DISTINCT, pois `organizacao_id` é nulo
    nela). Trocar a chave atualiza a linha existente; `ativa` permite desligá-la
    sem apagar o registro."""

    __tablename__ = "chaves_api"
    organizacao_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=True
    )
    tipo_ia: Mapped[str] = mapped_column(String(20), nullable=False)  # executora|criadora|companheira
    provedor: Mapped[str] = mapped_column(String(40), nullable=False)  # anthropic|openai|google|...
    valor_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    ultimos4: Mapped[str | None] = mapped_column(String(8), nullable=True)
    apelido: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ativa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    __table_args__ = (
        Index(
            "uq_chave_org_tipo_provedor",
            "organizacao_id",
            "tipo_ia",
            "provedor",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )
