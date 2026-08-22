"""Testes do instrumento Banco de dados direto (SQL) — Fase adicional.

O caminho feliz é exercitado contra o BANCO REAL do cérebro (Supabase), usando
os componentes de conexão do próprio engine — prova de ponta a ponta. Também
cobre erro de SQL (volta como dado) e conexão recusada (falha do instrumento).
"""

import pytest

import instrumentos as encaixe
from db import SSLMODE
from db import engine as cerebro_engine
from instrumentos.base import FalhaInstrumento
from instrumentos.sql import ArgsSQL, BancoSQL, ConfigSQL, eh_leitura


def _config_real(**over) -> ConfigSQL:
    # O `ssl` vem do próprio cérebro (`db.SSLMODE`), como o resto dos componentes
    # de conexão: `require` quando o banco é o da nuvem, `disable` quando é o
    # Postgres local dos testes (que não serve TLS). Fixar `require` aqui
    # quebraria o caminho feliz no banco local.
    u = cerebro_engine.url
    base = dict(
        host=u.host, porta=u.port, banco=u.database,
        usuario=u.username, senha=u.password, ssl=SSLMODE,
    )
    base.update(over)
    return ConfigSQL(**base)


def test_sql_registrado_com_senha_secreta():
    t = encaixe.obter_tipo("banco_sql")
    assert t is not None and t.campos_secretos == ("senha",)
    assert "banco_sql" in [x.tipo for x in encaixe.tipos_disponiveis()]


def test_select_devolve_linhas():
    r = BancoSQL().executar(
        _config_real(), ArgsSQL(sql="SELECT 1 AS um, 'x' AS letra")
    )
    assert r["ok"] is True and r["linhas"] == [{"um": 1, "letra": "x"}]


def test_parametros_nomeados_evitam_injecao():
    r = BancoSQL().executar(
        _config_real(), ArgsSQL(sql="SELECT :v AS eco", parametros={"v": 42})
    )
    assert r["linhas"] == [{"eco": 42}]


def test_escrita_devolve_linhas_afetadas():
    # TEMP table: existe só nesta conexão, sem efeito persistente no banco.
    r = BancoSQL().executar(
        _config_real(), ArgsSQL(sql="CREATE TEMP TABLE _t_teste_sql (x int)")
    )
    assert r["ok"] is True and "linhas_afetadas" in r


def test_erro_de_sql_volta_como_dado():
    r = BancoSQL().executar(
        _config_real(),
        ArgsSQL(sql="SELECT * FROM tabela_que_nao_existe_xyz_123"),
    )
    assert r["ok"] is False and "erro" in r


def test_conexao_recusada_e_falha_instrumento():
    cfg = _config_real(host="127.0.0.1", porta=1, ssl="disable")
    with pytest.raises(FalhaInstrumento):
        BancoSQL().executar(cfg, ArgsSQL(sql="SELECT 1"))


# ───────────────── modo somente leitura (trava) ─────────────────

def test_eh_leitura_classifica():
    assert eh_leitura("SELECT * FROM x")
    assert eh_leitura("  -- comentário\n SELECT 1")
    assert eh_leitura("WITH t AS (SELECT 1) SELECT * FROM t")
    assert not eh_leitura("INSERT INTO x VALUES (1)")
    assert not eh_leitura("UPDATE x SET a=1")
    assert not eh_leitura("DELETE FROM x")
    assert not eh_leitura("DROP TABLE x")
    assert not eh_leitura("WITH t AS (SELECT 1) DELETE FROM x")  # CTE de escrita
    assert not eh_leitura("SELECT 1; DROP TABLE x")  # múltiplas instruções
    assert not eh_leitura("")


def test_somente_leitura_recusa_escrita_sem_tocar_no_banco():
    # host inválido de propósito: se a trava NÃO existisse, tentaria conectar e
    # levantaria FalhaInstrumento; como recusa ANTES, devolve erro como dado.
    cfg = ConfigSQL(host="127.0.0.1", porta=1, banco="b", usuario="u", somente_leitura=True)
    r = BancoSQL().executar(cfg, ArgsSQL(sql="DELETE FROM x"))
    assert r["ok"] is False and "leitura" in r["erro"].lower()


def test_somente_leitura_permite_select():
    r = BancoSQL().executar(
        _config_real(somente_leitura=True), ArgsSQL(sql="SELECT 1 AS um")
    )
    assert r["ok"] is True and r["linhas"] == [{"um": 1}]
