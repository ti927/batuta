"""mensageria fase 1 - conversas e mensagens_conversa

Cria as duas tabelas da camada de conversa (mão dupla): `conversas` (a sessão,
1 viva por canal+contato) e `mensagens_conversa` (a thread). Migração ADITIVA —
não toca nenhuma tabela do motor (automacoes/execucoes/passos_execucao/
instrumentos); o núcleo de orquestração permanece intocado.

Revision ID: f7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'conversas',
        sa.Column('instrumento_id', sa.UUID(), nullable=False),
        sa.Column('canal', sa.String(length=20), server_default=sa.text("'telegram'"), nullable=False),
        sa.Column('contato_chave', sa.String(length=120), nullable=False),
        sa.Column('contato_nome', sa.String(length=200), nullable=True),
        sa.Column('estado', sa.String(length=30), server_default=sa.text("'aberta'"), nullable=False),
        sa.Column('destino_tipo', sa.String(length=20), nullable=True),
        sa.Column('destino_id', sa.UUID(), nullable=True),
        sa.Column('execucao_id', sa.UUID(), nullable=True),
        sa.Column('aguardando_ate', sa.DateTime(timezone=True), nullable=True),
        sa.Column('nudge_enviado', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('atribuida_a', sa.UUID(), nullable=True),
        sa.Column('custo_acumulado_usd', sa.Numeric(precision=12, scale=6), server_default=sa.text('0'), nullable=False),
        sa.Column('turnos', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('ultima_entrada_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['instrumento_id'], ['instrumentos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['execucao_id'], ['execucoes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['atribuida_a'], ['usuarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_conversa_viva',
        'conversas',
        ['instrumento_id', 'contato_chave'],
        unique=True,
        postgresql_where=sa.text("estado <> 'fechada'"),
    )
    op.create_index('ix_conversa_instrumento', 'conversas', ['instrumento_id'], unique=False)

    op.create_table(
        'mensagens_conversa',
        sa.Column('conversa_id', sa.UUID(), nullable=False),
        sa.Column('papel', sa.String(length=20), nullable=False),
        sa.Column('conteudo', sa.Text(), nullable=True),
        sa.Column('midia', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('entregue', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversa_id'], ['conversas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mensagem_conversa', 'mensagens_conversa', ['conversa_id', 'criado_em'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_mensagem_conversa', table_name='mensagens_conversa')
    op.drop_table('mensagens_conversa')
    op.drop_index('ix_conversa_instrumento', table_name='conversas')
    op.drop_index('uq_conversa_viva', table_name='conversas')
    op.drop_table('conversas')
