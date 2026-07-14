"""atividade da execucao: feedback ao vivo ("o que esta acontecendo agora")

Duas colunas ADITIVAS em `execucoes`: `atividade` (frase curta do que o agente faz
agora, ex.: "Montando a imagem…") e `atividade_em` (quando foi atualizada). Escritas
na BORDA (orquestracao/atividade) enquanto um instrumento lento roda sem gravar passo,
para a tela nao parecer travada. Nao tocam o nucleo do grafo; so informativo.
Reversivel (drop_column) → rollback trivial. Codigo antigo ignora colunas novas.

Revision ID: atv00atividade001
Revises: agd00agenda001
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa

revision = "atv00atividade001"
down_revision = "agd00agenda001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execucoes", sa.Column("atividade", sa.String(length=200), nullable=True)
    )
    op.add_column(
        "execucoes",
        sa.Column("atividade_em", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("execucoes", "atividade_em")
    op.drop_column("execucoes", "atividade")
