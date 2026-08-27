"""O engine principal com as proteções de rede (incidente de 2026-08-27).

A rede até o pooler do Supabase congelou e, sem nenhum limite no engine, um turno
ficou 31 min pendurado numa consulta que não voltava. Estes testes garantem que a
blindagem não regride: validação ao emprestar, reciclagem, e teto de consulta já
aplicado em toda conexão nova (prova viva via `current_setting`).
"""

from sqlalchemy import text

import db


def test_pool_valida_e_recicla_conexoes():
    assert db.engine.pool._pre_ping is True
    assert db.engine.pool._recycle == 300


def test_conexao_nova_ja_vem_com_teto_de_consulta():
    with db.engine.connect() as conn:
        teto = conn.execute(
            text("select current_setting('statement_timeout')")
        ).scalar()
    assert teto == "1min"
