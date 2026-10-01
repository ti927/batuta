"""remove a tabela eventos_comentario_instagram (a integração direta com a Meta saiu)

O gatilho "comentário do Instagram" saiu em 2026-10-01: comentário de rede social chega
pelo gatilho webhook (com dedupe próprio em `eventos_webhook`). A tabela estava VAZIA
na produção (backup em C:/dev/batuta-backups/2026-10-01_fase3_prontos_antes_de_apagar.json).
Reversível: o downgrade recria a tabela como era.

Revision ID: igc01remover001
Revises: icn00auto001
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa

revision = "igc01remover001"
down_revision = "icn00auto001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_evento_comentario_ig_automacao",
        table_name="eventos_comentario_instagram",
    )
    op.drop_index(
        "uq_evento_comentario_ig", table_name="eventos_comentario_instagram"
    )
    op.drop_table("eventos_comentario_instagram")


def downgrade() -> None:
    op.create_table(
        "eventos_comentario_instagram",
        sa.Column("comment_id", sa.String(length=120), nullable=False),
        sa.Column("automacao_id", sa.UUID(), nullable=False),
        sa.Column("organizacao_id", sa.UUID(), nullable=False),
        sa.Column("credencial_id", sa.UUID(), nullable=True),
        sa.Column("media_id", sa.String(length=120), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organizacao_id"], ["organizacoes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["credencial_id"], ["credenciais.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["execucao_id"], ["execucoes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_evento_comentario_ig",
        "eventos_comentario_instagram",
        ["comment_id", "automacao_id"],
        unique=True,
    )
    op.create_index(
        "ix_evento_comentario_ig_automacao",
        "eventos_comentario_instagram",
        ["automacao_id", "criado_em"],
        unique=False,
    )
