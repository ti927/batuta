"""execucoes.no_inicial e execucoes.origem_execucao_id — rodar de novo a partir daqui

Onda 4, fatia 2 (2026-09-02), lacuna 25. Até aqui, quando um fluxo morria no meio, a
única saída era rodar a automação INTEIRA de novo — jogando fora os passos bons e
pagando tudo outra vez. Aconteceu em 02/09: o artigo do EST tinha 4 passos prontos e
morreu no último; não havia como retomá-lo.

O motor já sabia começar de um nó no meio (`executar_cadeia(no_inicial=...)`, usado
pela retomada de aprovação). Faltava alguém pedir — e faltava a execução saber que
nasceu de outra.

Mudanças ADITIVAS:
- `execucoes.no_inicial` (String(100), nulável): o nó por onde ESTA execução começa.
  Nulo = começa pelo início do grafo (o caso de sempre).
- `execucoes.origem_execucao_id` (UUID, nulável, FK para `execucoes` com SET NULL): de
  qual execução esta é uma re-rodada. SET NULL (e não CASCADE) de propósito: apagar a
  execução antiga não pode levar junto a nova, que é trabalho de verdade.

Retrocompatível (tudo nulo nas execuções existentes). Rollback trivial.

Revision ID: rex00reexecucao01
Revises: des00desenho01
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'rex00reexecucao01'
down_revision: Union[str, Sequence[str], None] = 'des00desenho01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('execucoes', sa.Column('no_inicial', sa.String(length=100), nullable=True))
    op.add_column(
        'execucoes',
        sa.Column('origem_execucao_id', sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_execucoes_origem_execucao',
        'execucoes', 'execucoes',
        ['origem_execucao_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_execucoes_origem_execucao', 'execucoes', type_='foreignkey')
    op.drop_column('execucoes', 'origem_execucao_id')
    op.drop_column('execucoes', 'no_inicial')
