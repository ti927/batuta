"""quadros: o CEREBRO da organizacao -- Parte 1, Entrega 1 (a fundacao)

ADITIVA: tres tabelas novas, nenhuma coluna mexida.

- `quadros`: o quadro da organizacao (colunas com tipo, chave, limites ajustaveis).
  Nome unico por organizacao sem diferenciar maiuscula.
- `quadro_linhas`: as linhas (`valores` JSONB por id de coluna). O indice UNICO parcial
  (quadro_id, chave_valor) e o que torna a gravacao pela chave atomica. GIN em `valores`
  para filtrar sem varrer. Carimbo de quem gravou (origem/agente/execucao/usuario).
- `quadro_alteracoes`: o historico, so se acrescenta. `linha_id` sem FK de proposito
  (a linha apagada continua tendo historico).

NAO toca o motor. Codigo antigo ignora as tabelas novas. Reversivel: o downgrade apaga
as tres (e os dados delas). Ver `docs/CEREBRO-PLANO.md`.

Revision ID: qdr00quadros001
Revises: prs00preset001
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "qdr00quadros001"
down_revision = "prs00preset001"
branch_labels = None
depends_on = None


def _id_e_datas() -> list:
    return [
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
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
    ]


def upgrade() -> None:
    op.create_table(
        "quadros",
        sa.Column("organizacao_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column(
            "colunas",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "chave",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "limites",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("criado_por_id", sa.UUID(), nullable=True),
        *_id_e_datas(),
        sa.ForeignKeyConstraint(
            ["organizacao_id"], ["organizacoes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["criado_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_quadro_nome_por_org",
        "quadros",
        ["organizacao_id", sa.text("lower(nome)")],
        unique=True,
    )

    op.create_table(
        "quadro_linhas",
        sa.Column("quadro_id", sa.UUID(), nullable=False),
        sa.Column("organizacao_id", sa.UUID(), nullable=False),
        sa.Column(
            "valores",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("chave_valor", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("origem", sa.String(length=20), nullable=False),
        sa.Column("agente_id", sa.UUID(), nullable=True),
        sa.Column("execucao_id", sa.UUID(), nullable=True),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        *_id_e_datas(),
        sa.ForeignKeyConstraint(["quadro_id"], ["quadros.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organizacao_id"], ["organizacoes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["agente_id"], ["agentes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["execucao_id"], ["execucoes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_quadro_linha_chave",
        "quadro_linhas",
        ["quadro_id", "chave_valor"],
        unique=True,
        postgresql_where=sa.text("chave_valor is not null"),
    )
    op.create_index(
        "ix_quadro_linha_quadro", "quadro_linhas", ["quadro_id", "criado_em"]
    )
    op.create_index("ix_quadro_linha_execucao", "quadro_linhas", ["execucao_id"])
    op.create_index(
        "ix_quadro_linha_valores",
        "quadro_linhas",
        ["valores"],
        postgresql_using="gin",
    )

    op.create_table(
        "quadro_alteracoes",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("quadro_id", sa.UUID(), nullable=False),
        sa.Column("linha_id", sa.UUID(), nullable=False),
        sa.Column("acao", sa.String(length=10), nullable=False),
        sa.Column("antes", postgresql.JSONB(), nullable=True),
        sa.Column("depois", postgresql.JSONB(), nullable=True),
        sa.Column("origem", sa.String(length=20), nullable=False),
        sa.Column("agente_id", sa.UUID(), nullable=True),
        sa.Column("execucao_id", sa.UUID(), nullable=True),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column(
            "quando",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["quadro_id"], ["quadros.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_quadro_alteracao_linha", "quadro_alteracoes", ["linha_id", "quando"]
    )
    op.create_index(
        "ix_quadro_alteracao_quadro", "quadro_alteracoes", ["quadro_id", "quando"]
    )


def downgrade() -> None:
    op.drop_index("ix_quadro_alteracao_quadro", table_name="quadro_alteracoes")
    op.drop_index("ix_quadro_alteracao_linha", table_name="quadro_alteracoes")
    op.drop_table("quadro_alteracoes")
    op.drop_index("ix_quadro_linha_valores", table_name="quadro_linhas")
    op.drop_index("ix_quadro_linha_execucao", table_name="quadro_linhas")
    op.drop_index("ix_quadro_linha_quadro", table_name="quadro_linhas")
    op.drop_index("uq_quadro_linha_chave", table_name="quadro_linhas")
    op.drop_table("quadro_linhas")
    op.drop_index("uq_quadro_nome_por_org", table_name="quadros")
    op.drop_table("quadros")
