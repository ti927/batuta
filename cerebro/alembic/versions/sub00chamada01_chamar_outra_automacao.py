"""execucoes.chamada_por_execucao_id — o nó "Chamar outra automação"

Onda 3, fatia 4 (2026-09-04), lacuna 21. Uma automação só conseguia acionar outra
pelo instrumento `agendar_automacao`, que é fogo-e-esquece: dispara e nunca fica
sabendo o que aconteceu. Não havia como um time chamar outro e USAR o resultado.

O nó `chamar` roda a automação-alvo inteira, com execução e rastro próprios, e o
resultado volta para quem chamou. A pausa reusa a máquina da aprovação e do nó
"Esperar" (`execucoes.pendencias` guarda os ramos que ainda não rodaram e a ficha
atravessa); o que muda é quem solta: a própria execução-filha, ao chegar num veredito.

Mudança ADITIVA:
- `execucoes.chamada_por_execucao_id` (uuid, nulável, FK para `execucoes.id` com
  ON DELETE SET NULL): de qual execução esta é o sub-fluxo. É a LINHAGEM — por ela se
  barra o laço A→B→A e se mede a profundidade da corrente antes de criar mais uma
  filha (uma automação que se chama rodaria para sempre, gastando dinheiro de verdade
  a cada volta). SET NULL, e não CASCADE: apagar o chamador não pode levar junto o
  trabalho que a filha realmente fez.

O elo de VOLTA (chamador → filha) não é coluna: vive em `pendencias[].aguarda_execucao`,
o JSONB que já guarda os ramos pausados, porque é por RAMO que se espera — e é o ramo
que sabe por onde continuar quando a resposta chega.

O estado novo `aguardando_sub_fluxo` mora na coluna `estado`, que já é texto livre —
não há enum a migrar. Retrocompatível; rollback trivial.

Revision ID: sub00chamada01
Revises: esp00esperar01
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'sub00chamada01'
down_revision: Union[str, Sequence[str], None] = 'esp00esperar01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'execucoes',
        sa.Column('chamada_por_execucao_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_execucoes_chamada_por',
        'execucoes',
        'execucoes',
        ['chamada_por_execucao_id'],
        ['id'],
        ondelete='SET NULL',
    )
    # Subir a linhagem (filha → chamador) e descer a árvore (chamador → filhas, para o
    # teto de custo somar o que os sub-fluxos gastaram) são consultas por esta coluna.
    op.create_index(
        'ix_execucoes_chamada_por',
        'execucoes',
        ['chamada_por_execucao_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_execucoes_chamada_por', table_name='execucoes')
    op.drop_constraint('fk_execucoes_chamada_por', 'execucoes', type_='foreignkey')
    op.drop_column('execucoes', 'chamada_por_execucao_id')
