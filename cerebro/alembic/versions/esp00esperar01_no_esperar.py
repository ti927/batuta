"""execucoes.retomar_em — o nó "Esperar"

Onda 3, fatia 3 (2026-09-03), lacuna 20. Não havia espera temporal no fluxo. Para
"publique isto daqui a dois dias" só existia agendar OUTRA execução — que começa do
zero, sem a ficha e sem o ponto do grafo: todo o contexto do que já tinha sido feito
se perdia no caminho.

O motor já sabia PAUSAR e RETOMAR mantendo tudo (é o que a aprovação faz desde
sempre: `execucoes.pendencias` guarda os ramos que ainda não rodaram, e a ficha
atravessa a espera). Faltava um motivo de pausa que não fosse gente: o relógio.

Mudança ADITIVA:
- `execucoes.retomar_em` (timestamptz, nulável): quando esta execução, parada num nó
  "Esperar", volta para a fila. Nula em toda execução que não está esperando tempo.

O estado novo `aguardando_tempo` mora na coluna `estado`, que já é texto livre — não
há enum a migrar. Retrocompatível; rollback trivial.

Revision ID: esp00esperar01
Revises: tst00testeno01
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'esp00esperar01'
down_revision: Union[str, Sequence[str], None] = 'tst00testeno01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'execucoes', sa.Column('retomar_em', sa.DateTime(timezone=True), nullable=True)
    )
    # O vigia procura exatamente por (estado, retomar_em): índice parcial, para ele não
    # varrer a tabela inteira a cada 2 minutos.
    op.create_index(
        'ix_execucoes_esperando_tempo',
        'execucoes',
        ['retomar_em'],
        postgresql_where=sa.text("estado = 'aguardando_tempo'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_execucoes_esperando_tempo', table_name='execucoes')
    op.drop_column('execucoes', 'retomar_em')
