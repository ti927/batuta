"""organizacao - logo/foto (data URI no banco)

Adiciona `organizacoes.logo_url` (Text nullable): o logo da organização guardado
como data URI (a imagem é encolhida no navegador antes de salvar). NULL = sem logo
(a UI mostra a inicial do nome). Migração ADITIVA.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'organizacoes',
        sa.Column('logo_url', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('organizacoes', 'logo_url')
