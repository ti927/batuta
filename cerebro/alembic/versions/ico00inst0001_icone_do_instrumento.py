"""instrumento - icone escolhido pelo usuario

Adiciona `instrumentos.icone` (texto nullable): o id do icone que o usuario
escolheu para o instrumento na tela de cadastro/edicao (ex.: "fab:whatsapp",
"fas:database"). NULL = sem escolha → a UI mostra o icone generico (chave). E
so metadado de apresentacao na borda; nucleo de orquestracao intocado.

Migracao ADITIVA e anulavel → segura na ordem de deploy.

Revision ID: ico00inst0001
Revises: una00prov001
Create Date: 2026-06-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ico00inst0001'
down_revision: Union[str, Sequence[str], None] = 'una00prov001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'instrumentos',
        sa.Column('icone', sa.String(length=60), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('instrumentos', 'icone')
