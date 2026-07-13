"""agendamentos: disparo FUTURO de automacao por um agente (borda)

Tabela ADITIVA na BORDA: um agente, ao fim de uma execucao e conforme o resultado,
agenda um disparo futuro da automacao-ALVO (a mesma ou a de outro time da mesma
organizacao — alvo fixado na config do instrumento pelo humano). Um sweeper
periodico (agendador) pega os `pendente` vencidos, cria a execucao (motor) e marca
`enfileirado`. NAO toca nenhuma tabela do motor; o nucleo de orquestracao permanece
intocado. Reversivel (drop_table) → rollback trivial.

Revision ID: agd00agenda001
Revises: igc00coment001
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa

revision = "agd00agenda001"
down_revision = "igc00coment001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agendamentos",
        sa.Column("automacao_id", sa.UUID(), nullable=False),
        sa.Column("quando_executar", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entrada", sa.Text(), nullable=True),
        sa.Column(
            "estado",
            sa.String(length=20),
            server_default=sa.text("'pendente'"),
            nullable=False,
        ),
        sa.Column("execucao_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["automacao_id"], ["automacoes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execucao_id"], ["execucoes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agendamentos_pendentes",
        "agendamentos",
        ["estado", "quando_executar"],
        unique=False,
    )
    op.create_index(
        "ix_agendamentos_automacao",
        "agendamentos",
        ["automacao_id", "estado"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agendamentos_automacao", table_name="agendamentos")
    op.drop_index("ix_agendamentos_pendentes", table_name="agendamentos")
    op.drop_table("agendamentos")
