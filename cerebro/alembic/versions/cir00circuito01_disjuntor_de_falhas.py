"""execucoes.origem e o disjuntor de falhas da automação

Onda 4, fatia 3 (2026-09-03), lacuna 27. Uma automação que dispara sozinha podia
falhar TODO DIA sem que ninguém percebesse: cada falha avisava (Onda 1), mas nada
somava as falhas nem tirava do ar o que claramente parou de funcionar. Foi o susto
de 02/09 — cinco automações de blog quase passaram a falhar diariamente em silêncio.

Agora, três falhas seguidas DESLIGAM a automação e avisam pelo canal do time.

Mudanças ADITIVAS:
- `execucoes.origem` (String(20), nulável): quem disparou esta execução
  (manual|agendamento|webhook|comentario_instagram|sistema). O valor já existia — era
  gravado só no banco de logs. Agora fica na própria execução, porque o disjuntor
  precisa distinguir a automação que falha SOZINHA (agendada/webhook) de um teste
  manual, que tem gente olhando e não pode ser desligado sob o nariz de quem testa.
- `automacoes.desligada_por_falhas_em` (timestamptz, nulável): quando o disjuntor
  desligou. É o que diferencia "desliguei eu" de "o Batuta desligou", e o que a tela
  usa para explicar por que a automação está fora do ar.
- `automacoes.falhas_contam_desde` (timestamptz, nulável): a marca a partir da qual as
  falhas contam. Preenchida ao (re)ativar. Sem ela, religar uma automação recém-
  desligada a derrubaria na PRIMEIRA falha seguinte — as 3 falhas velhas ainda estariam
  lá. A contagem é DERIVADA das execuções (não há contador a manter e, portanto, não há
  contador para dessincronizar); esta coluna é o marco zero dessa contagem.

Retrocompatível (tudo nulo no que já existe): sem `falhas_contam_desde` a contagem
simplesmente olha todo o histórico, e sem `origem` a execução antiga não conta como
disparo automático. Rollback trivial.

Revision ID: cir00circuito01
Revises: rex00reexecucao01
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cir00circuito01'
down_revision: Union[str, Sequence[str], None] = 'rex00reexecucao01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('execucoes', sa.Column('origem', sa.String(length=20), nullable=True))
    op.add_column(
        'automacoes',
        sa.Column('desligada_por_falhas_em', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'automacoes',
        sa.Column('falhas_contam_desde', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('automacoes', 'falhas_contam_desde')
    op.drop_column('automacoes', 'desligada_por_falhas_em')
    op.drop_column('execucoes', 'origem')
