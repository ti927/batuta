"""automacao.configuracao (comportamento do fluxo: perfil + ajustes)

Adiciona `automacoes.configuracao` (JSONB NOT NULL default '{}'): guarda o
comportamento do fluxo configuravel pelo usuario — `{perfil, ajustes:{...}}`. As
regras do motor/mensageria (espera, teto, turnos, saudacao, horario, portao,
encerramento) cascateiam global < canal < perfil/ajustes do fluxo < no, resolvidas
numa fonte unica (mensageria/config.py::resolver_config). `{}` = usa o canal/padrao
(comportamento de hoje).

Migracao puramente ADITIVA e reversivel → segura na ordem de deploy (o codigo antigo
ignora a coluna; o codigo novo le com fallback ao padrao).

Revision ID: cfg00fluxo001
Revises: gra00grafo001
Create Date: 2026-06-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cfg00fluxo001'
down_revision: Union[str, Sequence[str], None] = 'gra00grafo001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'automacoes',
        sa.Column(
            'configuracao',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('automacoes', 'configuracao')
