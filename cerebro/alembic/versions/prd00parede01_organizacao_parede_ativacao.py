"""organizacao - parede de aprovacao ligavel/desligavel (config global da org)

Adiciona `organizacoes.parede_ativacao` (Boolean NOT NULL default TRUE): liga/desliga
a parede de aprovacao da organizacao. TRUE (padrao) = comportamento atual (ativar uma
automacao exige no-portao antes de acao irreversivel). FALSE = ativa sem essa exigencia.
Migracao ADITIVA; nucleo de orquestracao intocado.

Revision ID: prd00parede01
Revises: cfg00fluxo001
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'prd00parede01'
down_revision: Union[str, Sequence[str], None] = 'cfg00fluxo001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'organizacoes',
        sa.Column(
            'parede_ativacao',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('organizacoes', 'parede_ativacao')
