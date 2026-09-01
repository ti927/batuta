"""A parede de ativação morre: caem `organizacoes.parede_ativacao` e `instrumentos.exige_aprovacao`

Decisão do maestro (2026-08-31): **toda aprovação é feita pelo agente**. O Batuta tinha
DUAS travas de aprovação coexistindo — o PORTÃO (um interruptor num nó do desenho) e a
PAREDE (uma chave da organização que recusava ativar uma automação cujo agente
irreversível não tivesse portão antes). Ele passou meses sem saber que eram duas, e a
segunda ainda ligava a trava nativa da conversa, fazendo o agente pedir confirmação
duas vezes no mesmo atendimento.

As duas saem. Quem segura uma ação que precisa de gente é o próprio agente, chamando o
instrumento `pedir_aprovacao` — porque o markdown dele manda, não porque um interruptor
escondido mandou.

O que esta migração apaga:
- `organizacoes.parede_ativacao` (criada em `prd00parede01`, que NÃO pode ser removida:
  é `down_revision` de `whk00secret001`);
- `instrumentos.exige_aprovacao`, coluna morta desde que a irreversibilidade passou a
  ser derivada de tipo+config (`instrumentos/base.py::acao_irreversivel`).

Nada além dessas duas colunas é tocado. `acao_irreversivel` continua existindo no
código: é a base da POLÍTICA DE FALHA (`PRODUTO §16`) e do selo do catálogo — só deixou
de ser uma trava de ativação.

Revision ID: apr00instrumento01
Revises: fan00pendencia01
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'apr00instrumento01'
down_revision: Union[str, Sequence[str], None] = 'fan00pendencia01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('organizacoes', 'parede_ativacao')
    op.drop_column('instrumentos', 'exige_aprovacao')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'instrumentos',
        sa.Column('exige_aprovacao', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'organizacoes',
        sa.Column(
            'parede_ativacao', sa.Boolean(), nullable=False,
            server_default=sa.text('true'),
        ),
    )
