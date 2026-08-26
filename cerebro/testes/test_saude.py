"""O `/saude` responde pelos ÓRGÃOS, não só "estou no ar".

Motivo (2026-08-26): o app respondia normalmente enquanto a memória de conversa estava
caída havia três dias — um subsistema morto não derruba o HTTP, só faz o produto perder
capacidade em silêncio. A barra lateral usa este retorno para ficar âmbar.
"""

import agendador
import fila
import main
from orquestracao import memoria_conversa


def _saude(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200
    return r.json()


def test_saude_reporta_cada_subsistema(cliente):
    d = _saude(cliente)
    assert set(d["subsistemas"]) == {"memoria_conversa", "fila", "agendador"}
    assert "saudavel" in d and "degradados" in d
    # o que já existia continua (o selo da barra lateral depende disto)
    assert d["versao"] and d["iniciado_em"]


def test_saude_denuncia_subsistema_caido(cliente, monkeypatch):
    """Com a memória de conversa fora, `saudavel` vira False e o nome aparece em
    `degradados` — é o que faz o selo avisar em vez de mostrar tudo normal.
    (Nos testes o lifespan não sobe, então fila e agendador são fixados de pé para
    isolar a peça sob teste.)"""
    monkeypatch.setattr(memoria_conversa, "esta_saudavel", lambda: False)
    monkeypatch.setattr(fila, "esta_saudavel", lambda: True)
    monkeypatch.setattr(agendador, "esta_saudavel", lambda: True)
    d = _saude(cliente)
    assert d["saudavel"] is False
    assert d["degradados"] == ["memoria_conversa"]
    assert d["subsistemas"]["memoria_conversa"] is False


def test_saude_lista_todos_os_degradados(cliente, monkeypatch):
    monkeypatch.setattr(memoria_conversa, "esta_saudavel", lambda: False)
    monkeypatch.setattr(fila, "esta_saudavel", lambda: False)
    monkeypatch.setattr(agendador, "esta_saudavel", lambda: True)
    d = _saude(cliente)
    assert d["degradados"] == ["fila", "memoria_conversa"]  # ordenado, previsível


def test_saude_tudo_de_pe(cliente, monkeypatch):
    for modulo in (memoria_conversa, fila, agendador):
        monkeypatch.setattr(modulo, "esta_saudavel", lambda: True)
    d = _saude(cliente)
    assert d["saudavel"] is True and d["degradados"] == []


def test_esta_saudavel_sem_lifespan_diz_a_verdade():
    """Nos testes o lifespan não sobe (de propósito): as peças respondem `False`, e não
    um otimista `True`. Um retorno que mente seria pior que não ter o retorno."""
    assert memoria_conversa.esta_saudavel() is False
    assert fila.esta_saudavel() is False
    assert agendador.esta_saudavel() is False
    assert main is not None
