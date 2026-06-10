"""organizacao - modelo da IA de conversa (criadora/companheira) selecionavel

Adiciona `organizacoes.modelo_criadora` (String(100) nullable): o modelo de IA que
a conversa daquela organização usa. NULL = usa o padrão do código (Opus). O seletor
da tela só oferece modelos cujo provedor tem chave resolvível. Migração ADITIVA;
núcleo de orquestração intocado.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'organizacoes',
        sa.Column('modelo_criadora', sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('organizacoes', 'modelo_criadora')
