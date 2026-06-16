"""automacao - canal de aprovacao (aprovacao por mensageria)

Adiciona `automacoes.aprovacao_instrumento_id` (FK nullable para instrumentos,
ON DELETE SET NULL): o instrumento de canal (enviar_telegram/enviar_whatsapp)
pelo qual o portao de aprovacao humana pode ser resolvido por mensageria,
COEXISTINDO com a tela. NULL = so tela (padrao e comportamento de hoje). O
destinatario (aprovador) vem do `destinatario_padrao` do proprio instrumento.

Migracao ADITIVA e anulavel → segura na ordem de deploy. Nucleo de orquestracao
intocado (e so borda).

Revision ID: apv00canal001
Revises: ico00inst0001
Create Date: 2026-06-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'apv00canal001'
down_revision: Union[str, Sequence[str], None] = 'ico00inst0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'fk_automacao_aprovacao_instrumento', 'automacoes', type_='foreignkey'
    )
    op.drop_column('automacoes', 'aprovacao_instrumento_id')
