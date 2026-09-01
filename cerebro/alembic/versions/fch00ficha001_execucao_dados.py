"""execucoes.dados — a ficha da execução (os valores que atravessam o grafo)

Onda 2 do "motor vira grafo de verdade" (2026-09-01). Fecha a lacuna-raiz de dados:
entre um nó e outro trafegava **só texto**, então a entrada do gatilho MORRIA no
primeiro nó. Se o agente do nó 1 não repetisse o dado no texto final, o nó 2 recebia
uma frase solta — foi assim que a execução `f1e23565` mandou "Aprovado. Seguindo para
publicação" ao Gerador Carrossel, que respondeu "não recebi título, subtítulo e URL".

Mudança ÚNICA e ADITIVA:
- `execucoes.dados` (JSONB, nulável): `{"entrada": "<o que o gatilho trouxe>", ...}`.
  Cresce quando um agente chama `anotar`. Execuções antigas ficam NULL → o motor lê
  com `or {}` e o comportamento é idêntico ao de antes.

Nulável (e não `NOT NULL DEFAULT '{}'`) de propósito: um DEFAULT no servidor obrigaria
reescrever toda a tabela `execucoes` (que é grande em produção) durante o deploy.

Retrocompatível. Rollback trivial (drop_column).

Revision ID: fch00ficha001
Revises: apr00instrumento01
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fch00ficha001'
down_revision: Union[str, Sequence[str], None] = 'apr00instrumento01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'execucoes',
        sa.Column('dados', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('execucoes', 'dados')
