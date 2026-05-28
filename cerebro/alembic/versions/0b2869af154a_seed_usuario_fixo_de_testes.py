"""seed usuario fixo de testes

Revision ID: 0b2869af154a
Revises: 6acb578bd5e6
Create Date: 2026-05-28 14:04:21.906032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b2869af154a'
down_revision: Union[str, Sequence[str], None] = '6acb578bd5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# UUID fixo do usuário de testes da Etapa 1 (ver cerebro/usuario_fixo.py).
USUARIO_FIXO_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Insere o usuário fixo de testes (idempotente)."""
    op.execute(
        sa.text(
            "insert into usuarios (id, nome, email) "
            "values (cast(:id as uuid), :nome, :email) on conflict (id) do nothing"
        ).bindparams(
            id=USUARIO_FIXO_ID,
            nome="Usuário de Testes",
            email="teste@batuta.local",
        )
    )


def downgrade() -> None:
    """Remove o usuário fixo de testes."""
    op.execute(
        sa.text("delete from usuarios where id = cast(:id as uuid)").bindparams(
            id=USUARIO_FIXO_ID
        )
    )
