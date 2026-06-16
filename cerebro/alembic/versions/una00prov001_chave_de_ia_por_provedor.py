"""chave de IA por provedor (remove a dimensao tipo_ia)

Passo 1 da FASE Chave de IA por provedor (docs/CHAVE-POR-PROVEDOR-ESTUDO.md).
A chave deixa de ser por (organizacao, tipo_ia, provedor) e passa a ser por
(organizacao, provedor): some o cadastro em dobro (executora x criadora) e a
"pegadinha da imagem". A escolha de QUAL IA roda continua no modelo (da conversa
e de cada agente), nao na chave.

Passos do upgrade:
  1. CONSOLIDA as linhas por (organizacao_id, provedor): quando ha mais de um
     papel para o mesmo (org, provedor), mantem UMA linha (regra deterministica:
     executora > criadora > companheira; entre essas, ativa antes de inativa; e a
     mais recente). As perdedoras sao apagadas (em producao 2026-06-15 ha apenas
     1 caso: a Anthropic da consultoria, com a MESMA chave nos dois papeis -> zero
     perda). Os ids descartados sao logados via RAISE NOTICE.
  2. troca o indice unico (organizacao_id, tipo_ia, provedor) ->
     (organizacao_id, provedor);
  3. dropa a coluna `tipo_ia`.

Reversibilidade: o downgrade recria a coluna (default 'executora') e o indice
antigo, mas o papel original das linhas consolidadas nao volta (informacao
perdida no merge). Como o dado real nao tem conflito, o risco pratico e nulo.

Revision ID: una00prov001
Revises: crd00cofre001
Create Date: 2026-06-15 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'una00prov001'
down_revision: Union[str, Sequence[str], None] = 'crd00cofre001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Consolida: mantem a melhor linha por (organizacao_id, provedor) e apaga
    #    as demais. NULLS NOT DISTINCT no PARTITION agrupa as linhas da
    #    consultoria (organizacao_id nulo) numa unica particao, como desejado.
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                descartado RECORD;
            BEGIN
                FOR descartado IN
                    SELECT id, organizacao_id, tipo_ia, provedor, ultimos4
                    FROM (
                        SELECT id, organizacao_id, tipo_ia, provedor, ultimos4,
                            ROW_NUMBER() OVER (
                                PARTITION BY organizacao_id, provedor
                                ORDER BY
                                    CASE tipo_ia
                                        WHEN 'executora' THEN 0
                                        WHEN 'criadora' THEN 1
                                        ELSE 2
                                    END,
                                    ativa DESC,
                                    atualizado_em DESC
                            ) AS rn
                        FROM chaves_api
                    ) ranked
                    WHERE rn > 1
                LOOP
                    RAISE NOTICE 'chave_api descartada na consolidacao: id=% org=% tipo_ia=% provedor=% ultimos4=%',
                        descartado.id, descartado.organizacao_id, descartado.tipo_ia,
                        descartado.provedor, descartado.ultimos4;
                    DELETE FROM chaves_api WHERE id = descartado.id;
                END LOOP;
            END $$;
            """
        )
    )

    # 2. Troca o indice unico: (org, tipo_ia, provedor) -> (org, provedor).
    op.drop_index('uq_chave_org_tipo_provedor', table_name='chaves_api')

    # 3. Dropa a coluna de papel.
    op.drop_column('chaves_api', 'tipo_ia')

    op.create_index(
        'uq_chave_org_provedor', 'chaves_api', ['organizacao_id', 'provedor'],
        unique=True, postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_chave_org_provedor', table_name='chaves_api')
    op.add_column(
        'chaves_api',
        sa.Column(
            'tipo_ia', sa.String(length=20), nullable=False,
            server_default='executora',
        ),
    )
    # Remove o default para espelhar o schema original (a coluna nao tinha default).
    op.alter_column('chaves_api', 'tipo_ia', server_default=None)
    op.create_index(
        'uq_chave_org_tipo_provedor', 'chaves_api',
        ['organizacao_id', 'tipo_ia', 'provedor'],
        unique=True, postgresql_nulls_not_distinct=True,
    )
