"""pedidos_aprovacao: cada pedido de aprovação por canal sabe a que execução pertence

ADITIVA: uma tabela nova. Antes a resposta do aprovador era roteada pela conversa
(bot + chat), que guarda uma execução só — duas esperando no mesmo bot se atropelavam.
Cada pedido guarda o código do botão e o id da mensagem enviada. CASCADE ao apagar a
execução ou o canal. Reversível.

Revision ID: apv00pedidos001
Revises: cnx00conexao001
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa

revision = "apv00pedidos001"
down_revision = "cnx00conexao001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pedidos_aprovacao",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("execucao_id", sa.UUID(), nullable=False),
        sa.Column("instrumento_id", sa.UUID(), nullable=False),
        sa.Column("contato_chave", sa.String(length=120), nullable=False),
        sa.Column("mensagem_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.String(length=32), nullable=True),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["execucao_id"], ["execucoes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrumento_id"], ["instrumentos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pedido_aprovacao_contato", "pedidos_aprovacao", ["instrumento_id", "contato_chave"])
    op.create_index("ix_pedido_aprovacao_codigo", "pedidos_aprovacao", ["codigo"])
    op.create_index("ix_pedido_aprovacao_execucao", "pedidos_aprovacao", ["execucao_id"])


def downgrade() -> None:
    op.drop_index("ix_pedido_aprovacao_execucao", table_name="pedidos_aprovacao")
    op.drop_index("ix_pedido_aprovacao_codigo", table_name="pedidos_aprovacao")
    op.drop_index("ix_pedido_aprovacao_contato", table_name="pedidos_aprovacao")
    op.drop_table("pedidos_aprovacao")
