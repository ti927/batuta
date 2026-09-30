"""gatilho webhook: segredo da assinatura (automacoes) + avisos recebidos (eventos_webhook)

ADITIVA: duas colunas nulas em `automacoes` (nenhuma automação existente muda: sem
segredo, o webhook segue aceitando como antes) e a tabela `eventos_webhook`, que só
passa a receber linhas quando um aviso chega. Reversível.

Revision ID: whk00assinatura001
Revises: esc00escopo001
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "whk00assinatura001"
down_revision = "esc00escopo001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("automacoes", sa.Column("segredo_webhook_cifrado", sa.Text(), nullable=True))
    op.add_column(
        "automacoes", sa.Column("segredo_webhook_ultimos4", sa.String(length=8), nullable=True)
    )
    op.create_table(
        "eventos_webhook",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("automacao_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evento_id", sa.String(length=200), nullable=False),
        sa.Column("execucao_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["automacao_id"], ["automacoes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execucao_id"], ["execucoes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_evento_webhook", "eventos_webhook", ["automacao_id", "evento_id"], unique=True)
    op.create_index("ix_evento_webhook_automacao", "eventos_webhook", ["automacao_id", "criado_em"])


def downgrade() -> None:
    op.drop_index("ix_evento_webhook_automacao", table_name="eventos_webhook")
    op.drop_index("uq_evento_webhook", table_name="eventos_webhook")
    op.drop_table("eventos_webhook")
    op.drop_column("automacoes", "segredo_webhook_ultimos4")
    op.drop_column("automacoes", "segredo_webhook_cifrado")
