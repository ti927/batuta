"""fase 10 - memoria de longo prazo do projeto (destilada)

Cria `memorias_projeto`: a memória de longo prazo da IA sobre um projeto (fatos,
decisões, preferências). Abordagem DESTILADA, não vetorial — apenas linhas de texto
curadas pela IA, presas à conversa (o projeto) e à organização (parede de
isolamento). Migração ADITIVA: o núcleo de orquestração não é tocado.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'memorias_projeto',
        sa.Column(
            'id', sa.UUID(),
            server_default=sa.text('gen_random_uuid()'), nullable=False,
        ),
        sa.Column(
            'criado_em', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column(
            'atualizado_em', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column('conversa_id', sa.UUID(), nullable=False),
        sa.Column('organizacao_id', sa.UUID(), nullable=False),
        sa.Column('categoria', sa.String(length=20), nullable=False),
        sa.Column('conteudo', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ['conversa_id'], ['conversas_criacao.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['organizacao_id'], ['organizacoes.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_memoria_projeto_conversa', 'memorias_projeto', ['conversa_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_memoria_projeto_conversa', table_name='memorias_projeto')
    op.drop_table('memorias_projeto')
