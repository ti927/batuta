"""agendamentos.motivo: por que um agendamento foi cancelado (visivel, nao em silencio)

Coluna ADITIVA. Um agendamento cancelado (manual OU pela varredura, quando o alvo esta
desativado/removido) passa a guardar o MOTIVO em frase humana, para a aba "Agendadas" das
Execucoes mostrar (§12-A: nada falha em silencio). Nulo enquanto pendente/enfileirado.
Nao toca o motor. Reversivel (drop_column) -> rollback trivial.

Revision ID: agm00motivo001
Revises: trn00turno001
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa

revision = "agm00motivo001"
down_revision = "trn00turno001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agendamentos", sa.Column("motivo", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agendamentos", "motivo")
