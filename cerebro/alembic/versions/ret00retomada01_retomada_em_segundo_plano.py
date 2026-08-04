"""execucoes.retomada_resposta — retomada de portão em segundo plano (§12-A)

Aprovar um portão pela TELA rodava a retomada DENTRO do request (`retomar_execucao`),
que executa o próximo passo — muitas vezes pesado (publicar no Instagram, gerar mídia).
Passando do tempo-limite do proxy (Cloudflare ~100s), a conexão era cortada e o navegador
mostrava "a conexão falhou" — sempre, de forma determinística. A correção move a retomada
para a fila (mesmo padrão do disparo): a resposta do humano fica em `retomada_resposta` e
a execução volta a `aguardando`; um trabalhador a reivindica e roda a retomada em segundo
plano, com heartbeat + polling na tela.

Mudança ÚNICA e ADITIVA:
- `execucoes.retomada_resposta` (Text, nulável). Nulo = disparo normal; preenchido = o
  worker deve RETOMAR (não rodar do zero) com esse texto como a resposta do humano.

Retrocompatível: toda execução existente tem `retomada_resposta = NULL` → comportamento
idêntico. Rollback trivial (drop_column).

Revision ID: ret00retomada01
Revises: snd00sombra01
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ret00retomada01'
down_revision: Union[str, Sequence[str], None] = 'snd00sombra01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'execucoes',
        sa.Column('retomada_resposta', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('execucoes', 'retomada_resposta')
