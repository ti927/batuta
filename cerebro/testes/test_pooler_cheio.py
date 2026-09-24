"""Pooler do Supabase cheio (EMAXCONNSESSION, 2026-09-24): a conexão espera e tenta de
novo em vez de virar erro 500 na primeira recusa; qualquer outro erro sobe na hora; e
toda espera deixa aviso (para aparecer no banco de logs, não só como 500 genérico)."""

import pytest

import db

ERRO_CHEIO = (
    "connection failed: FATAL:  (EMAXCONNSESSION) max clients reached in session mode - "
    "max clients are limited to pool_size: 15"
)


class _Falha(Exception):
    pass


def _conectar_que_falha(vezes: int, erro: str = ERRO_CHEIO):
    estado = {"n": 0}

    def conectar():
        estado["n"] += 1
        if estado["n"] <= vezes:
            raise _Falha(erro)
        return "conexao"

    return conectar, estado


def test_espera_e_consegue_quando_o_pooler_libera():
    conectar, estado = _conectar_que_falha(2)
    esperas, avisos = [], []
    r = db.conectar_com_paciencia(conectar, dormir=esperas.append, avisar=lambda n, ok: avisos.append((n, ok)))
    assert r == "conexao" and estado["n"] == 3
    assert esperas == [0.5, 1.0]
    assert avisos == [(3, True)]


def test_desiste_depois_das_esperas_e_avisa_a_falha():
    conectar, estado = _conectar_que_falha(99)
    esperas, avisos = [], []
    with pytest.raises(_Falha):
        db.conectar_com_paciencia(conectar, dormir=esperas.append, avisar=lambda n, ok: avisos.append((n, ok)))
    assert esperas == list(db.ESPERAS_POOLER_CHEIO)
    assert avisos == [(len(db.ESPERAS_POOLER_CHEIO) + 1, False)]


def test_outro_erro_de_conexao_sobe_na_hora():
    conectar, estado = _conectar_que_falha(1, erro="password authentication failed")
    esperas, avisos = [], []
    with pytest.raises(_Falha):
        db.conectar_com_paciencia(conectar, dormir=esperas.append, avisar=lambda n, ok: avisos.append((n, ok)))
    assert estado["n"] == 1 and esperas == [] and avisos == []


def test_sem_espera_nao_avisa():
    conectar, _ = _conectar_que_falha(0)
    avisos = []
    assert db.conectar_com_paciencia(conectar, dormir=lambda s: None, avisar=lambda n, ok: avisos.append(n)) == "conexao"
    assert avisos == []


def test_orcamento_explicito_no_engine():
    pool = db.engine.pool
    assert pool.size() == db.POOL_SIZE
    assert pool._max_overflow == db.MAX_OVERFLOW
    assert db.POOL_SIZE + db.MAX_OVERFLOW <= 15  # cabe no pooler mesmo no limite antigo


def test_engine_conecta_de_verdade_pelo_gancho():
    # O gancho `do_connect` devolve a conexão do driver; o engine segue funcionando.
    from sqlalchemy import text

    with db.engine.connect() as c:
        assert c.execute(text("select 1")).scalar() == 1
