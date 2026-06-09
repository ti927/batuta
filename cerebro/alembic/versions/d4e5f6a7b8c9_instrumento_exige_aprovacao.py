"""instrumento - interruptor de aprovacao humana por instancia

Adiciona `instrumentos.exige_aprovacao` (bool nullable): NULL = automático (deriva
do tipo/config), True = sempre exige portão de aprovação, False = nunca. Permite que
o usuário defina, por instrumento, se a ação exige aprovação humana — em vez de a
irreversibilidade ser fixa por tipo. Migração ADITIVA; núcleo de orquestração intocado.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'instrumentos',
        sa.Column('exige_aprovacao', sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('instrumentos', 'exige_aprovacao')
