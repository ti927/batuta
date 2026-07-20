"""evento_log: banco de logs pesquisavel (observabilidade)

Tabela ADITIVA de BORDA. Um registro por evento relevante do sistema (requisicoes com erro,
disparos, ciclo de execucao, agendamentos, mensageria, turnos da IA, escrita, falhas de auth),
carimbando a IDENTIDADE DO SERVIDOR (host/pid/commit/ambiente) — o dado que faltou no incidente
do cerebro local. Nao toca o nucleo. Reversivel (drop_table) -> rollback trivial.

Revision ID: log00evento001
Revises: agm00motivo001
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "log00evento001"
down_revision = "agm00motivo001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evento_log",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("nivel", sa.String(length=10), nullable=False),
        sa.Column("categoria", sa.String(length=30), nullable=False),
        sa.Column("acao", sa.String(length=80), nullable=False),
        sa.Column("resultado", sa.String(length=10), nullable=True),
        sa.Column("usuario_id", UUID(as_uuid=True), nullable=True),
        sa.Column("organizacao_id", UUID(as_uuid=True), nullable=True),
        sa.Column("time_id", UUID(as_uuid=True), nullable=True),
        sa.Column("recurso_tipo", sa.String(length=40), nullable=True),
        sa.Column("recurso_id", UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("host", sa.String(length=120), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("commit", sa.String(length=64), nullable=True),
        sa.Column("ambiente", sa.String(length=10), nullable=True),
        sa.Column("ip_cliente", sa.String(length=64), nullable=True),
        sa.Column("origem", sa.String(length=40), nullable=True),
        sa.Column("http_metodo", sa.String(length=10), nullable=True),
        sa.Column("rota", sa.String(length=200), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("latencia_ms", sa.Integer(), nullable=True),
        sa.Column("erro_texto", sa.Text(), nullable=True),
        sa.Column("detalhe", JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_log_org_tempo", "evento_log", ["organizacao_id", "criado_em"])
    op.create_index("ix_log_usuario_tempo", "evento_log", ["usuario_id", "criado_em"])
    op.create_index("ix_log_categoria_tempo", "evento_log", ["categoria", "criado_em"])
    op.create_index("ix_log_request", "evento_log", ["request_id"])
    op.create_index("ix_log_ambiente_tempo", "evento_log", ["ambiente", "criado_em"])
    op.create_index(
        "ix_log_erros_tempo",
        "evento_log",
        ["nivel", "criado_em"],
        postgresql_where=sa.text("nivel IN ('error', 'critical')"),
    )
    op.create_index(
        "ix_log_detalhe_gin", "evento_log", ["detalhe"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_log_detalhe_gin", table_name="evento_log")
    op.drop_index("ix_log_erros_tempo", table_name="evento_log")
    op.drop_index("ix_log_ambiente_tempo", table_name="evento_log")
    op.drop_index("ix_log_request", table_name="evento_log")
    op.drop_index("ix_log_categoria_tempo", table_name="evento_log")
    op.drop_index("ix_log_usuario_tempo", table_name="evento_log")
    op.drop_index("ix_log_org_tempo", table_name="evento_log")
    op.drop_table("evento_log")
