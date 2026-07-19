"""turnos_criacao: turno da IA criadora roda em SEGUNDO PLANO (borda)

Tabela ADITIVA na BORDA. Antes, o turno da conversa rodava DENTRO do POST /mensagens
— uma requisicao longa e bloqueante (a IA raciocina e usa ferramentas por minutos).
Qualquer timeout de proxy ou oscilacao de rede cortava a conexao no meio, sem resposta:
a tela via so um erro generico e a mensagem se perdia. Agora o POST enfileira (cria o
turno `aguardando`) e um pool (`fila_turnos`) puxa e roda, publicando `atividade` ao vivo.
Espelha o ciclo de `execucoes`. NAO toca nenhuma tabela do motor; o nucleo de
orquestracao permanece intocado. Reversivel (drop_table) -> rollback trivial.

Revision ID: trn00turno001
Revises: mem00memag001
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "trn00turno001"
down_revision = "mem00memag001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "turnos_criacao",
        sa.Column("conversa_id", sa.UUID(), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("pergunta", sa.Text(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            server_default=sa.text("'aguardando'"),
            nullable=False,
        ),
        sa.Column("atividade", sa.String(length=200), nullable=True),
        sa.Column("atividade_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resultado", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("erro_mensagem", sa.Text(), nullable=True),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversa_id"], ["conversas_criacao.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_turnos_criacao_fila",
        "turnos_criacao",
        ["estado", "criado_em"],
        unique=False,
    )
    op.create_index(
        "ix_turnos_criacao_conversa",
        "turnos_criacao",
        ["conversa_id", "estado"],
        unique=False,
    )
    # Invariante: no maximo um turno NAO-terminal por conversa (trava de banco que
    # fecha a corrida de dois envios quase simultaneos). Indice unico PARCIAL.
    op.create_index(
        "uq_turno_ativo_por_conversa",
        "turnos_criacao",
        ["conversa_id"],
        unique=True,
        postgresql_where=sa.text("estado in ('aguardando', 'em_andamento')"),
    )


def downgrade() -> None:
    op.drop_index("uq_turno_ativo_por_conversa", table_name="turnos_criacao")
    op.drop_index("ix_turnos_criacao_conversa", table_name="turnos_criacao")
    op.drop_index("ix_turnos_criacao_fila", table_name="turnos_criacao")
    op.drop_table("turnos_criacao")
