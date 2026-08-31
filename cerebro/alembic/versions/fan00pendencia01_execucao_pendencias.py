"""execucoes.pendencias — os ramos que ficaram esperando quando a execução pausou

Onda 1 do "motor vira grafo de verdade" (2026-08-31). O motor deixou de caminhar o
grafo com um PONTEIRO ÚNICO (que seguia uma saída e descartava as outras em silêncio)
e passou a caminhar por ONDAS: um nó pode liberar VÁRIOS caminhos, e todos rodam.

Consequência: quando um nó PAUSA no meio de uma onda (portão de aprovação), os outros
ramos daquela onda ainda não rodaram. Sem guardá-los, a retomada seguiria só o caminho
do portão e o trabalho dos demais sumiria — exatamente o tipo de perda silenciosa que
esta frente existe para acabar.

Mudança ÚNICA e ADITIVA:
- `execucoes.pendencias` (JSONB, nulável): `[{"no": "<id>", "entradas": ["<texto>"]}]`.
  Execuções antigas ficam NULL → comportamento idêntico ao de antes.

Retrocompatível. Rollback trivial (drop_column).

Revision ID: fan00pendencia01
Revises: tip00passo001
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fan00pendencia01'
down_revision: Union[str, Sequence[str], None] = 'tip00passo001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'execucoes',
        sa.Column('pendencias', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('execucoes', 'pendencias')
