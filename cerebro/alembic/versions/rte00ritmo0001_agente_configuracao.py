"""agentes.configuracao: o RITMO e a ESPERA passam a ser do trabalhador

Uma coluna ADITIVA que junta duas metades da mesma decisao, hoje separadas em telas
diferentes.

Ate aqui, QUEM e perguntado numa aprovacao morava no agente (o instrumento
`pedir_aprovacao`, no cinto dele), mas QUANTO TEMPO se espera morava no NO do desenho
(`no.config`). Duas metades da mesma regra, em dois lugares -- e a tela do no mostrava
as MESMAS 8 opcoes que a tela do fluxo, sem nada dizer qual era qual. Era a queixa do
maestro: "cada agente tambem tem configuracao de tempos e mensagens... ta uma bagunca".

A regra que fica (`mensageria/config.py`, docstring do topo): a configuracao pertence ao
nivel em que a coisa medida EXISTE. Contador que acumula (mensagens e custo de uma
conversa, passos de uma execucao) so pode ter um teto -- e do FLUXO. Propriedade de UM
ATO (quanto este passo trabalha, quanto esta espera tolera silencio) varia
legitimamente de passo para passo -- e do AGENTE. Um fluxo de aprovacao de compra com
uma confirmacao rapida de quem pediu E um diretor financeiro que viaja precisa das duas
reguas; com uma so, esse fluxo nao e construivel.

Nasce NULA e o codigo trata nulo como "herda tudo do fluxo", entao nenhuma automacao
muda de comportamento. Reversivel (drop_column) -> rollback trivial.

Revision ID: rte00ritmo0001
Revises: dno00dono0001
Create Date: 2026-09-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "rte00ritmo0001"
down_revision = "dno00dono0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # JSONB e nao colunas fixas porque o conjunto de chaves e o mesmo de
    # `CHAVES_DO_AGENTE`, que ja mudou uma vez e vai mudar de novo -- e porque um agente
    # so guarda aqui o que ele SOBREPOE: a ausencia da chave e a informacao "herda do
    # fluxo", que uma coluna fixa com default nao consegue expressar.
    op.add_column("agentes", sa.Column("configuracao", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("agentes", "configuracao")
