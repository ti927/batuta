"""quadro_links: links de leitura de um quadro para painéis de fora

ADITIVA: uma tabela nova. Guarda só o HASH do link (sha256) + os 4 últimos caracteres;
revogar/expirar cortam na hora; limite de leituras por minuto visível e ajustável.
CASCADE ao apagar o quadro. Reversível. Ver docs/CEREBRO-PLANO.md.

Revision ID: lnk00links0001
Revises: qdr00quadros001
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = "lnk00links0001"
down_revision = "qdr00quadros001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quadro_links",
        sa.Column("quadro_id", sa.UUID(), nullable=False),
        sa.Column("organizacao_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_final", sa.String(length=8), nullable=False),
        sa.Column("limite_por_minuto", sa.Integer(), server_default=sa.text("60"), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_uso_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("criado_por_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["quadro_id"], ["quadros.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizacao_id"], ["organizacoes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["criado_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_quadro_link_quadro", "quadro_links", ["quadro_id"])


def downgrade() -> None:
    op.drop_index("ix_quadro_link_quadro", table_name="quadro_links")
    op.drop_table("quadro_links")
