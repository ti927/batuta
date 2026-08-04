"""passos_execucao.tipo — classificação do passo na timeline (Fatia 4.1)

Primeiro passo da unificação do PORTÃO como passo único de espera-por-humano
(`docs/REMODELAGEM-MOTOR.md §5, Fatia 4`; suspensão dirigida do congelamento nº 2,
`MIGRACAO.md §6.1`, 2026-08-04). Dá vocabulário à timeline: cada passo passa a
declarar o seu `tipo` — `agente` | `roteador` | `espera_humano` | `mensagem_entrante`.
O passo de PORTÃO passa a ser carimbado `espera_humano`.

Mudança ÚNICA e ADITIVA:
- `passos_execucao.tipo` (String(20), nulável). Passos antigos ficam NULL (sem
  retroação); nada lê a coluna ainda (4.1 só POPULA) → zero mudança de comportamento.

Retrocompatível. Rollback trivial (drop_column).

Revision ID: tip00passo001
Revises: ret00retomada01
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'tip00passo001'
down_revision: Union[str, Sequence[str], None] = 'ret00retomada01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'passos_execucao',
        sa.Column('tipo', sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('passos_execucao', 'tipo')
