"""instrumentos.escopo: instrumento do time (padrão) ou da organização

ADITIVA: coluna com padrão 'time' — todo instrumento existente segue sendo do time,
sem mudar nada. 'organizacao' = todos os times da organização podem encaixá-lo; a
identificação é feita uma vez e serve a todos. Reversível.

Revision ID: esc00escopo001
Revises: apv00pedidos001
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa

revision = "esc00escopo001"
down_revision = "apv00pedidos001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instrumentos",
        sa.Column("escopo", sa.String(length=20), server_default=sa.text("'time'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("instrumentos", "escopo")
