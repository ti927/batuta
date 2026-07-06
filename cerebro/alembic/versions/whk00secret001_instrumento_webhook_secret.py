"""instrumento: webhook_secret vira campo proprio (imune a edicao de config)

O cracha do webhook de um canal (Telegram) vivia dentro do JSONB `configuracao`.
Toda edicao do instrumento (formulario ou IA de conversa) reconstroi a config so
com os campos do schema e APAGAVA o cracha — o canal passava a mostrar
"Desconectado" e o usuario tinha de reconectar a cada ajuste. Passa a viver numa
coluna propria, que nenhum caminho de edicao de config toca.

Aditiva e nao-destrutiva. Backfill: move o cracha que hoje esta no JSON para a
coluna, para os canais ja conectados seguirem conectados sem reconectar. NAO
remove do JSON (rollback seguro: o codigo antigo volta a ler de la).

Revision ID: whk00secret001
Revises: prd00parede01
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa

revision = "whk00secret001"
down_revision = "prd00parede01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instrumentos",
        sa.Column("webhook_secret", sa.String(length=64), nullable=True),
    )
    op.execute(
        "UPDATE instrumentos "
        "SET webhook_secret = configuracao->>'webhook_secret' "
        "WHERE configuracao->>'webhook_secret' IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("instrumentos", "webhook_secret")
