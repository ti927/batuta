"""agendamentos.recuperado_em: o resgate de um agendamento que NAO disparou

Coluna ADITIVA. Um agendamento cancelado (alvo desativado/removido, ou cancelado a mao)
podia ate hoje ser lido, mas nao recuperado: nao havia como refazer o disparo perdido sem
adivinhar o texto que o agente tinha montado. Agora a tela oferece "Disparar agora" e
"Reagendar", e esta coluna marca QUANDO o resgate aconteceu -- para o botao sumir depois
de usado (um fluxo importante disparado duas vezes por engano e trabalho em dobro) e para
a linha mostrar que ja foi tratada.

A execucao nascida de um "Disparar agora" e amarrada na coluna `execucao_id`, que ja
existia com exatamente este significado ("qual execucao este agendamento gerou") e estava
sempre nula nos cancelados -- por isso o resgate imediato nao precisou de coluna propria.

Nao toca o motor. Reversivel (drop_column) -> rollback trivial.

Revision ID: rcp00recupera01
Revises: sub00chamada01
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa

revision = "rcp00recupera01"
down_revision = "sub00chamada01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agendamentos",
        sa.Column("recuperado_em", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agendamentos", "recuperado_em")
