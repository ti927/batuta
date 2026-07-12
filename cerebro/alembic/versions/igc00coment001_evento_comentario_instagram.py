"""webhook de comentarios do Instagram: tabela de eventos (dedupe/teto/auditoria)

GAP 2 (memoria project-fix-org-ativa-e-gaps-ia-criadora). Uma tabela ADITIVA na
BORDA de comentarios: registra cada comentario recebido pelo webhook para
(1) DEDUPE por (comment_id, automacao_id) — a Meta reentrega quando nao recebe o
200 a tempo; (2) TETO por automacao numa janela — nao estourar custo de IA num
post viral; (3) AUDITORIA de qual comentario disparou qual execucao. NAO toca
nenhuma tabela do motor (automacoes/execucoes/instrumentos/passos_execucao); o
nucleo de orquestracao permanece intocado. Reversivel (drop_table) → rollback
trivial.

Revision ID: igc00coment001
Revises: whk00secret001
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa

revision = "igc00coment001"
down_revision = "whk00secret001"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index(
        "ix_evento_comentario_ig_automacao",
        table_name="eventos_comentario_instagram",
    )
    op.drop_index(
        "uq_evento_comentario_ig", table_name="eventos_comentario_instagram"
    )
    op.drop_table("eventos_comentario_instagram")
