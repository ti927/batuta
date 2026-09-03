"""execucoes.teste_de_no — testar um passo isolado

Onda 4, fatia 5 (2026-09-03), lacuna 26. Para experimentar UM agente — ver se o
markdown está bom, se o instrumento responde — era preciso rodar a automação
INTEIRA, pagando todos os passos e acionando tudo o que vem depois. Quem estava
desenhando um fluxo de 6 passos para ajustar o 4º pagava os 3 primeiros a cada
tentativa.

Mudança ADITIVA:
- `execucoes.teste_de_no` (Boolean, default false): esta execução roda UM nó e
  para, sem seguir as setas. O nó por onde começar já existe desde a fatia 2
  (`no_inicial`), e a entrada de mentira vem no `entrada` de sempre — então o
  teste reaproveita o funil, a fila, o heartbeat e a tela de inspeção inteiros.

Uma execução de teste é uma execução DE VERDADE (custa dinheiro e aciona
instrumento real), por isso ela aparece na lista e deixa rastro, marcada. O que a
coluna muda é só onde ela para.

Retrocompatível: tudo o que existe nasce `false`, que é o comportamento de sempre.

Revision ID: tst00testeno01
Revises: cir00circuito01
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'tst00testeno01'
down_revision: Union[str, Sequence[str], None] = 'cir00circuito01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'execucoes',
        sa.Column(
            'teste_de_no', sa.Boolean(), nullable=False, server_default=sa.text('false')
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('execucoes', 'teste_de_no')
