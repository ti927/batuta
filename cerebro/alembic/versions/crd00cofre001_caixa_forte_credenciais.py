"""caixa-forte de credenciais nomeadas (tabela credenciais + referencias + toggle)

Passo 1 da FASE Caixa-forte (docs/CAIXA-FORTE-PLANO.md). Migração ADITIVA:

  - cria a tabela `credenciais` (saco tipado e cifrado de campos; organizacao_id
    nulo = credencial da consultoria; `compartilhavel` controla a visibilidade
    às organizações; `expira_em` reservado para OAuth futuro);
  - adiciona `instrumentos.credencial_id` (FK nullable, ON DELETE SET NULL): o
    instrumento APONTA para uma credencial em vez de guardar o segredo inline;
  - adiciona `chaves_api.compartilhavel` (Bool, default TRUE nas linhas
    existentes — retrocompatível: nada que está no ar muda de comportamento).

Não altera nem remove nada existente; o downgrade desfaz limpo.

Revision ID: crd00cofre001
Revises: msg00uso0001
Create Date: 2026-06-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'crd00cofre001'
down_revision: Union[str, Sequence[str], None] = 'msg00uso0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'credenciais',
        sa.Column('organizacao_id', sa.UUID(), nullable=True),
        sa.Column('nome', sa.String(length=200), nullable=False),
        sa.Column('tipo', sa.String(length=50), nullable=False),
        sa.Column('dados_cifrado', sa.Text(), nullable=False),
        sa.Column('resumo', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            'compartilhavel', sa.Boolean(),
            server_default=sa.text('false'), nullable=False,
        ),
        sa.Column('expira_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organizacao_id'], ['organizacoes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_credencial_org_nome', 'credenciais', ['organizacao_id', 'nome'],
        unique=True, postgresql_nulls_not_distinct=True,
    )
    op.add_column(
        'instrumentos', sa.Column('credencial_id', sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        'fk_instrumento_credencial', 'instrumentos', 'credenciais',
        ['credencial_id'], ['id'], ondelete='SET NULL',
    )
    op.add_column(
        'chaves_api',
        sa.Column(
            'compartilhavel', sa.Boolean(),
            server_default=sa.text('true'), nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chaves_api', 'compartilhavel')
    op.drop_constraint('fk_instrumento_credencial', 'instrumentos', type_='foreignkey')
    op.drop_column('instrumentos', 'credencial_id')
    op.drop_index('uq_credencial_org_nome', table_name='credenciais')
    op.drop_table('credenciais')
