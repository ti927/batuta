"""memoria do agente: agente aprende com o proprio trabalho (ficha por assunto)

ADITIVA: (1) duas colunas em `agentes` — `memoria_ativa` (bool, default FALSE →
comportamento atual preservado) e `memoria_recall` (String, default 'sempre'); (2)
tabela nova `memorias_agente` (ficha por assunto, UPSERT via UNIQUE(agente_id, assunto),
CASCADE ao apagar o agente). NAO toca o nucleo de orquestracao. Reversivel → rollback
trivial. Codigo antigo ignora colunas/tabela novas.

Revision ID: mem00memag001
Revises: atv00atividade001
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "mem00memag001"
down_revision = "atv00atividade001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agentes",
        sa.Column(
            "memoria_ativa",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "agentes",
        sa.Column(
            "memoria_recall",
            sa.String(length=20),
            server_default=sa.text("'sempre'"),
            nullable=False,
        ),
    )
    op.create_table(
        "memorias_agente",
        sa.Column("agente_id", sa.UUID(), nullable=False),
        sa.Column("assunto", sa.String(length=200), nullable=False),
        sa.Column("conteudo", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["agente_id"], ["agentes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_memoria_agente_assunto",
        "memorias_agente",
        ["agente_id", "assunto"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_memoria_agente_assunto", table_name="memorias_agente")
    op.drop_table("memorias_agente")
    op.drop_column("agentes", "memoria_recall")
    op.drop_column("agentes", "memoria_ativa")
