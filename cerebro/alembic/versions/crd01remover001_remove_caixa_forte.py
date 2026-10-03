"""remove a caixa-forte de credenciais nomeadas (a página ficou só com as chaves de IA)

Decisão do maestro (2026-10-02): a página de chaves guarda só as chaves das IAs; toda
credencial de outra plataforma mora no próprio instrumento (`segredos_instrumento`).
A tela, o MCP e a conexão Google já tinham saído (commit 3c36583). Esta migração
derruba o que sobrou no banco: a coluna `instrumentos.credencial_id` e a tabela
`credenciais`.

A produção tinha ZERO credenciais e nenhum instrumento apontando para uma (conferido
em 2026-10-02). Por segurança, o upgrade RECUSA rodar se encontrar alguma — apagar
segredo de cliente sem querer não tem volta.

Reversível: o downgrade recria a tabela e a coluna como eram (vazias).

Revision ID: crd01remover001
Revises: igc01remover001
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "crd01remover001"
down_revision = "igc01remover001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conexao = op.get_bind()
    restantes = conexao.execute(sa.text("SELECT count(*) FROM credenciais")).scalar()
    apontando = conexao.execute(
        sa.text("SELECT count(*) FROM instrumentos WHERE credencial_id IS NOT NULL")
    ).scalar()
    if restantes or apontando:
        raise RuntimeError(
            f"Há {restantes} credencial(is) nomeada(s) e {apontando} instrumento(s) "
            "apontando para uma. Mova esses segredos para dentro dos instrumentos "
            "antes de remover a caixa-forte."
        )
    op.drop_constraint("fk_instrumento_credencial", "instrumentos", type_="foreignkey")
    op.drop_column("instrumentos", "credencial_id")
    op.drop_index("uq_credencial_org_nome", table_name="credenciais")
    op.drop_table("credenciais")


def downgrade() -> None:
    op.create_table(
        "credenciais",
        sa.Column("organizacao_id", sa.UUID(), nullable=True),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("dados_cifrado", sa.Text(), nullable=False),
        sa.Column("resumo", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "compartilhavel", sa.Boolean(),
            server_default=sa.text("false"), nullable=False,
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organizacao_id"], ["organizacoes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_credencial_org_nome", "credenciais", ["organizacao_id", "nome"],
        unique=True, postgresql_nulls_not_distinct=True,
    )
    op.add_column("instrumentos", sa.Column("credencial_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_instrumento_credencial", "instrumentos", "credenciais",
        ["credencial_id"], ["id"], ondelete="SET NULL",
    )
