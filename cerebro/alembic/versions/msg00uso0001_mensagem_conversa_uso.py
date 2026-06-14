"""mensageria - coluna uso em mensagens_conversa (contabilizacao por categoria)

Adiciona a coluna `uso` (JSONB, nullable) em `mensagens_conversa`: a mensagem do
AGENTE passa a guardar a LISTA de entradas de uso de IA do turno (chamada do
agente + transcrições de áudio), cada uma com origem e categoria, para a
mensageria entrar nos painéis de uso. Migração ADITIVA — só acrescenta a coluna;
não toca nenhuma tabela do motor nem o núcleo de orquestração.

Revision ID: msg00uso0001
Revises: f7b8c9d0e1f2
Create Date: 2026-06-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'msg00uso0001'
down_revision: Union[str, Sequence[str], None] = 'f7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'mensagens_conversa',
        sa.Column('uso', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('mensagens_conversa', 'uso')
