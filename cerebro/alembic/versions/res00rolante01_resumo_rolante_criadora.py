"""conversas_criacao - resumo rolante + janela (economia de tokens, Frente B Parte A)

Adiciona `conversas_criacao.resumo` (Text, nullable) e `resumo_ate` (Integer, NOT NULL
default 0). Em vez de reenviar a conversa INTEIRA todo turno, a criadora passa a enviar
`resumo` + a janela `mensagens[resumo_ate:]`. ADITIVA e retrocompatível: `resumo_ate=0`
(o default aplicado às linhas existentes) reproduz o comportamento de antes. Núcleo de
orquestração intocado.

Revision ID: res00rolante01
Revises: log00evento001
Create Date: 2026-07-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'res00rolante01'
down_revision: Union[str, Sequence[str], None] = 'log00evento001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('conversas_criacao', sa.Column('resumo', sa.Text(), nullable=True))
    op.add_column(
        'conversas_criacao',
        sa.Column('resumo_ate', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('conversas_criacao', 'resumo_ate')
    op.drop_column('conversas_criacao', 'resumo')
