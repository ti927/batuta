"""conversa eterna - dropa rascunho, modo e estado de conversas_criacao

Pivô da IA criadora (plano de migração): uma IA, uma conversa que nunca termina,
operando sobre o TIME REAL. Some o rascunho-como-documento (a IA escreve direto nas
tabelas reais), somem os três modos e o ciclo rascunho/materializada/descartada. A
conversa vincula-se ao time por `time_id` (que já existia, agora preenchido cedo).

Revision ID: a1b2c3d4e5f6
Revises: d9e1a7c2b4f0
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd9e1a7c2b4f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('conversas_criacao', 'rascunho')
    op.drop_column('conversas_criacao', 'modo')
    op.drop_column('conversas_criacao', 'estado')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'conversas_criacao',
        sa.Column(
            'estado',
            sa.String(length=20),
            server_default=sa.text("'rascunho'"),
            nullable=False,
        ),
    )
    op.add_column(
        'conversas_criacao',
        sa.Column(
            'modo',
            sa.String(length=20),
            server_default=sa.text("'investigacao'"),
            nullable=False,
        ),
    )
    op.add_column(
        'conversas_criacao',
        sa.Column(
            'rascunho',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
