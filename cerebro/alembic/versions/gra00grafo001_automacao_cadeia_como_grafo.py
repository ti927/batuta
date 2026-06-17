"""passos_execucao.no_id (cadeia como grafo de nos tipados)

Fase 1 da FASE "Automacoes como GRAFO" (BUILD-PLAN.md).

Adiciona `passos_execucao.no_id` (String, nullable): o id do NO do grafo em que o
passo rodou. Necessaria para a retomada localizar o no pausado por id (e nao por
agente), agora que o MESMO agente pode aparecer em varios nos do grafo.

A conversao do formato antigo da `automacoes.cadeia` (dict-por-agente) para a forma
canonica de grafo (lista de nos tipados) NAO acontece nesta migracao, de proposito:
o motor passa a NORMALIZAR a cadeia na LEITURA (`orquestracao.grafo.normalizar`, que
e idempotente e converte antigo->novo). Assim:
  - o codigo antigo em producao continua lendo o formato antigo (a migracao so
    adiciona uma coluna que ele ignora) → seguro aplicar ANTES do deploy;
  - o codigo novo le tanto o antigo quanto o novo;
  - cada automacao migra de forma preguicosa para o formato novo quando for
    re-salva pelo construtor visual.

Migracao puramente ADITIVA e reversivel.

Revision ID: gra00grafo001
Revises: apv00canal001
Create Date: 2026-06-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'gra00grafo001'
down_revision: Union[str, Sequence[str], None] = 'apv00canal001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'passos_execucao',
        sa.Column('no_id', sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('passos_execucao', 'no_id')
