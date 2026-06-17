"""drop automacoes.aprovacao_instrumento_id (aprovacao migrou para o NO)

Fase 6 da FASE "Automacoes como GRAFO". A aprovacao por canal deixou de ser por
automacao (coluna `aprovacao_instrumento_id`) e passou a viver no NO com portao da
cadeia (`no.aprovacao = {instrumento_id, destinatario}`, construtor visual). O
codigo novo nao usa mais a coluna; esta migracao a remove.

ORDEM DE DEPLOY (licao una00prov001): subir o codigo que NAO usa a coluna ANTES de
dropa-la. Logo, aplicar esta migracao SOMENTE depois do deploy do codigo desta fase
— senao o codigo antigo no ar (que ainda mapeia a coluna) quebra. Reversivel: o
downgrade recria a coluna (sem os dados antigos, que ja viraram config no no).

Revision ID: apv00drop001
Revises: gra00grafo001
Create Date: 2026-06-16 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'apv00drop001'
down_revision: Union[str, Sequence[str], None] = 'gra00grafo001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # O nome da FK foi fixado em apv00canal001.
    op.drop_constraint(
        'fk_automacao_aprovacao_instrumento', 'automacoes', type_='foreignkey'
    )
    op.drop_column('automacoes', 'aprovacao_instrumento_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'automacoes',
        sa.Column('aprovacao_instrumento_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_automacao_aprovacao_instrumento',
        'automacoes',
        'instrumentos',
        ['aprovacao_instrumento_id'],
        ['id'],
        ondelete='SET NULL',
    )
