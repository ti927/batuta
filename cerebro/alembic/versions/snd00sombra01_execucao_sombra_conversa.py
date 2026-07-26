"""execucoes - rastro-sombra de conversa (Frente A, Fatia 1a)

A conversa passa a deixar rastro nos MESMOS trilhos da orquestração (mesma tabela
`execucoes`, mesmos `passos_execucao`), para inspecionar o agente conversacional
passo a passo. Três mudanças, todas ADITIVAS:

- `execucoes.automacao_id` passa a ACEITAR nulo — o rastro de uma conversa não nasce
  de uma automação (nasce do agente atendente).
- `execucoes.modo` ('fluxo' | 'conversa') — distingue a execução de automação do
  rastro-sombra de um atendimento por mensageria. Default 'fluxo' nas linhas existentes.
- `execucoes.conversa_id` (FK conversas, ON DELETE CASCADE) — a conversa que a sombra
  acompanha.

Retrocompatível: toda execução de automação de hoje continua idêntica (automacao_id
preenchido, modo='fluxo'). A sombra vive no estado próprio 'conversa', que a fila e os
recuperadores de órfãs/presas IGNORAM — logo nenhum código operacional do motor muda.

Revision ID: snd00sombra01
Revises: res00rolante01
Create Date: 2026-07-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'snd00sombra01'
down_revision: Union[str, Sequence[str], None] = 'res00rolante01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'execucoes',
        sa.Column('modo', sa.String(length=20), nullable=False, server_default='fluxo'),
    )
    op.add_column(
        'execucoes',
        sa.Column('conversa_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_execucoes_conversa',
        'execucoes',
        'conversas',
        ['conversa_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.alter_column(
        'execucoes', 'automacao_id',
        existing_type=UUID(as_uuid=True), nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Apaga eventuais sombras (sem automação) antes de reexigir o NOT NULL.
    op.execute("DELETE FROM execucoes WHERE modo = 'conversa' OR automacao_id IS NULL")
    op.alter_column(
        'execucoes', 'automacao_id',
        existing_type=UUID(as_uuid=True), nullable=False,
    )
    op.drop_constraint('fk_execucoes_conversa', 'execucoes', type_='foreignkey')
    op.drop_column('execucoes', 'conversa_id')
    op.drop_column('execucoes', 'modo')
