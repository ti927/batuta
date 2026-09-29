"""instrumentos.conexao: o estado da conexão com o sistema de fora

ADITIVA: uma coluna JSONB nula. Guarda o que o último teste descobriu (conectado ou
falhou, transporte, versão do protocolo, servidor, quando) — hoje para o servidor MCP.
Separada da `configuracao` porque o formulário a regrava inteira. Nunca guarda
segredo. Reversível.

Revision ID: cnx00conexao001
Revises: lnk00links0001
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "cnx00conexao001"
down_revision = "lnk00links0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instrumentos",
        sa.Column("conexao", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("instrumentos", "conexao")
