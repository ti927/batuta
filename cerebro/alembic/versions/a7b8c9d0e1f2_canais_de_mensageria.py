"""canais de mensageria (Telegram primeiro) — tabelas + origem/espera na execucao

Cria as tabelas do canal plugável (PRODUTO §10):
- `canais` (por organização), `identidades_canal`, `mensagens_canal` (log +
  idempotência via índice único (canal_id, id_externo)) e `segredos_canal`
  (cofre do token, espelha `segredos_instrumento`).
- Colunas aditivas em `execucoes`: origem do canal (Modo B) e canal/identificador
  esperados na pausa (Modo A). Tudo nullable — não afeta execuções comuns.

Migração ADITIVA. O motor de orquestração não é tocado.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id_data() -> list:
    """As três colunas do mixin IdData, iguais às demais tabelas."""
    return [
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'canais',
        sa.Column('organizacao_id', sa.UUID(), nullable=False),
        sa.Column('tipo', sa.String(length=50), nullable=False),
        sa.Column('nome', sa.String(length=200), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ativo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        *_id_data(),
        sa.ForeignKeyConstraint(['organizacao_id'], ['organizacoes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_canal_org', 'canais', ['organizacao_id'])

    op.create_table(
        'identidades_canal',
        sa.Column('organizacao_id', sa.UUID(), nullable=False),
        sa.Column('canal_id', sa.UUID(), nullable=False),
        sa.Column('identificador_externo', sa.String(length=200), nullable=False),
        sa.Column('rotulo', sa.String(length=200), nullable=True),
        sa.Column('usuario_id', sa.UUID(), nullable=True),
        *_id_data(),
        sa.ForeignKeyConstraint(['organizacao_id'], ['organizacoes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['canal_id'], ['canais.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_identidade_canal_identificador',
        'identidades_canal',
        ['canal_id', 'identificador_externo'],
        unique=True,
    )

    op.create_table(
        'mensagens_canal',
        sa.Column('organizacao_id', sa.UUID(), nullable=False),
        sa.Column('canal_id', sa.UUID(), nullable=False),
        sa.Column('execucao_id', sa.UUID(), nullable=True),
        sa.Column('direcao', sa.String(length=10), nullable=False),
        sa.Column('identificador_externo', sa.String(length=200), nullable=False),
        sa.Column('texto', sa.Text(), nullable=True),
        sa.Column('anexos', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id_externo', sa.String(length=200), nullable=True),
        *_id_data(),
        sa.ForeignKeyConstraint(['organizacao_id'], ['organizacoes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['canal_id'], ['canais.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['execucao_id'], ['execucoes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mensagem_canal_execucao', 'mensagens_canal', ['execucao_id'])
    op.create_index(
        'uq_mensagem_canal_id_externo',
        'mensagens_canal',
        ['canal_id', 'id_externo'],
        unique=True,
    )

    op.create_table(
        'segredos_canal',
        sa.Column('canal_id', sa.UUID(), nullable=False),
        sa.Column('campo', sa.String(length=80), nullable=False),
        sa.Column('valor_cifrado', sa.Text(), nullable=False),
        sa.Column('ultimos4', sa.String(length=8), nullable=True),
        *_id_data(),
        sa.ForeignKeyConstraint(['canal_id'], ['canais.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_segredo_canal_campo', 'segredos_canal', ['canal_id', 'campo'], unique=True)

    # Colunas aditivas na execução (origem — Modo B; espera — Modo A).
    op.add_column('execucoes', sa.Column('origem_canal_id', sa.UUID(), nullable=True))
    op.add_column('execucoes', sa.Column('origem_identificador', sa.String(length=200), nullable=True))
    op.add_column('execucoes', sa.Column('aguardando_canal_id', sa.UUID(), nullable=True))
    op.add_column('execucoes', sa.Column('aguardando_identificador', sa.String(length=200), nullable=True))
    op.create_foreign_key(
        'fk_execucao_origem_canal', 'execucoes', 'canais',
        ['origem_canal_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_execucao_aguardando_canal', 'execucoes', 'canais',
        ['aguardando_canal_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_execucao_aguardando_canal', 'execucoes', type_='foreignkey')
    op.drop_constraint('fk_execucao_origem_canal', 'execucoes', type_='foreignkey')
    op.drop_column('execucoes', 'aguardando_identificador')
    op.drop_column('execucoes', 'aguardando_canal_id')
    op.drop_column('execucoes', 'origem_identificador')
    op.drop_column('execucoes', 'origem_canal_id')

    op.drop_index('uq_segredo_canal_campo', table_name='segredos_canal')
    op.drop_table('segredos_canal')

    op.drop_index('uq_mensagem_canal_id_externo', table_name='mensagens_canal')
    op.drop_index('ix_mensagem_canal_execucao', table_name='mensagens_canal')
    op.drop_table('mensagens_canal')

    op.drop_index('uq_identidade_canal_identificador', table_name='identidades_canal')
    op.drop_table('identidades_canal')

    op.drop_index('ix_canal_org', table_name='canais')
    op.drop_table('canais')
