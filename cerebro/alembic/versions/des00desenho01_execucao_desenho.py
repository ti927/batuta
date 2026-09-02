"""execucoes.desenho — a execução guarda o fluxo que ela rodou

Onda 4 do "motor vira grafo de verdade" (2026-09-02), lacunas 28 e 29. Até aqui a
execução NÃO guardava o desenho: o motor e a retomada liam a `automacoes.cadeia`
**viva**. Duas consequências ruins, uma delas um bug de verdade:

- (28) inspecionar uma execução antiga mostrava o fluxo de HOJE, não o que rodou;
- (29) editar a automação com uma aprovação em aberto mudava o caminho NO MEIO da
  corrida — a retomada seguia por setas que não existiam quando a execução começou.

Mudança ÚNICA e ADITIVA:
- `execucoes.desenho` (JSONB, nulável): a foto do grafo no momento do DISPARO
  (`disparo.criar_execucao`, funil único dos 4 gatilhos). Execuções antigas ficam
  NULL e continuam lendo a cadeia viva — comportamento idêntico ao de antes.

Nulável (e não `NOT NULL DEFAULT '{}'`) de propósito, mesma razão da `dados`: um
DEFAULT no servidor obrigaria reescrever a tabela `execucoes` inteira (grande em
produção) durante o deploy.

Retrocompatível. Rollback trivial (drop_column).

Revision ID: des00desenho01
Revises: fch00ficha001
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'des00desenho01'
down_revision: Union[str, Sequence[str], None] = 'fch00ficha001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'execucoes',
        sa.Column('desenho', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('execucoes', 'desenho')
