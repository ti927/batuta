"""fase 9 - modo da conversa de criacao

Adiciona a coluna `modo` a `conversas_criacao` (investigacao | projeto | montagem).
A criadora opera em tres fases com gate de prompt + ferramentas; o modo persiste a
fase atual da conversa. Aditiva: linhas existentes assumem o default 'investigacao'.

Revision ID: d9e1a7c2b4f0
Revises: fcf05d5f64f7
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd9e1a7c2b4f0'
down_revision: Union[str, Sequence[str], None] = 'fcf05d5f64f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'conversas_criacao',
        sa.Column(
            'modo',
            sa.String(length=20),
            server_default=sa.text("'investigacao'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('conversas_criacao', 'modo')
