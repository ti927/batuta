"""execucoes.dono/dono_ate/espera_ate: a execucao passa a ter DONO e a espera, PRAZO

Tres colunas ADITIVAS que curam o mesmo defeito estrutural (docs/FALHAS-DO-MOTOR.md):
estado que pertence a EXECUCAO morava so na borda, e quando a borda nao estava la -- ou
estava em duplicidade -- o motor nao sabia de nada.

`dono` + `dono_ate` (§4.1): a TRAVA. Ate hoje a unica trava de uma espera por humano era
`conversas.estado = 'bot_respondendo'`, que a tela nao enxerga. Em 21/09 uma resposta pelo
Telegram e um clique na tela entraram na MESMA execucao com 1m45s de diferenca, abriram o
MESMO thread do LangGraph e bifurcaram o checkpoint; a Anthropic recusou o historico pela
metade com um 400 e uma execucao de quase 4 horas morreu. Agora quem vai mexer numa
execucao pega o dono primeiro, e quem nao consegue recebe recusa honesta. `dono_ate` e o
prazo: dono nenhum trava para sempre, nem que o processo morra segurando.

`espera_ate` (§4.2): o RELOGIO. O relogio de uma espera morava em `conversas.aguardando_ate`,
entao uma aprovacao pedida so pela tela (sem canal amarrado) nao era varrida por NINGUEM --
o unico estado do sistema sem vigia. Ficava parada para sempre, em silencio. Agora a propria
execucao carrega quando aquela espera vira motivo de alarme.

Nao muda nenhum comportamento por si so -- as tres nascem nulas e o codigo antigo as ignora.
Reversivel (drop_column) -> rollback trivial.

Revision ID: dno00dono0001
Revises: rcp00recupera01
Create Date: 2026-09-21
"""

import sqlalchemy as sa
from alembic import op

revision = "dno00dono0001"
down_revision = "rcp00recupera01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("execucoes", sa.Column("dono", sa.String(40), nullable=True))
    op.add_column(
        "execucoes", sa.Column("dono_ate", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "execucoes", sa.Column("espera_ate", sa.DateTime(timezone=True), nullable=True)
    )
    # O vigia da espera esquecida varre por (estado, espera_ate). Sem indice ele leria a
    # tabela inteira a cada volta -- e ele roda de 2 em 2 minutos, para sempre.
    op.create_index(
        "ix_execucoes_espera_ate",
        "execucoes",
        ["espera_ate"],
        postgresql_where=sa.text("espera_ate IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_execucoes_espera_ate", table_name="execucoes")
    op.drop_column("execucoes", "espera_ate")
    op.drop_column("execucoes", "dono_ate")
    op.drop_column("execucoes", "dono")
