"""instrumentos.icone_auto: o ícone do serviço (MCP ou site da API), guardado

ADITIVA: duas colunas nulas; nenhum instrumento muda (sem ícone automático, a tela
segue com o escolhido ou o genérico). Reversível.

Revision ID: icn00auto001
Revises: whk00assinatura001
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa

revision = "icn00auto001"
down_revision = "whk00assinatura001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instrumentos", sa.Column("icone_auto", sa.Text(), nullable=True))
    op.add_column(
        "instrumentos", sa.Column("icone_auto_em", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("instrumentos", "icone_auto_em")
    op.drop_column("instrumentos", "icone_auto")
