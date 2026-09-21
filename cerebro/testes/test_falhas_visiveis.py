"""Os buracos menores do catálogo de falhas (§4.7 de `docs/FALHAS-DO-MOTOR.md`).

Todos do mesmo tipo: o motor JÁ fazia a coisa certa, mas fazia calado — ou dizia algo
que não ajudava quem estava tentando entender o que houve.

- C2: instrumento que responde `ok: false` e o agente narra sucesso
- D6: teto de passos que dizia "possível laço infinito" sem dizer ONDE
- D7: seta apontando para um passo que não existe mais
- B7: execução enfileirada que ninguém chegou a pegar
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

import fila
from modelos import Agente, Automacao, Execucao
from orquestracao import cadeia as motor


@pytest.fixture
def ag(sessao, dados):
    def criar(nome):
        a = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
        sessao.add(a)
        sessao.flush()
        return a
    return criar


def _mock_agente(monkeypatch, saida="ok", erros=None, ramos=None):
    def fake(agente, cinto, entrada, **kwargs):
        return {
            "saida": saida,
            "instrumentos_acionados": [],
            "uso": [],
            "erros_instrumentos": erros or [],
            "ramos_escolhidos": list(ramos or []),
        }
    monkeypatch.setattr(motor, "executar_agente", fake)


# ───────── C2 — falha devolvida como dado também é falha ─────────

def test_instrumento_que_respondeu_falha_deixa_aviso_no_passo(sessao, dados, ag, monkeypatch):
    """Um instrumento que responde `ok: false` não levanta exceção: o agente decide
    sozinho como seguir e com frequência NARRA SUCESSO. O rastro guardava o erro cru,
    mas na timeline e no resultado isso era mudo — e a execução terminava "concluída"."""
    a = ag("Publicador")
    _mock_agente(
        monkeypatch,
        saida="Publiquei tudo com sucesso!",
        erros=[{"ferramenta": "Publicar no Insta", "erro": "resposta com ok=false"}],
    )
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }

    r = motor.executar_cadeia(sessao, cadeia, "vai")

    assert r["estado"] == "concluida"  # o CAMINHO não muda: o agente pode ter conseguido
    assert any("Publicar no Insta" in a_ for a_ in r["avisos"])
    assert any("não é prova" in a_ for a_ in r["avisos"])
    assert "Publicar no Insta" in (r["passos"][0]["aviso"] or "")


def test_passo_sem_falha_de_instrumento_nao_ganha_aviso(sessao, dados, ag, monkeypatch):
    """Aviso que aparece à toa é aviso que ninguém lê."""
    a = ag("Publicador")
    _mock_agente(monkeypatch, saida="feito")
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["avisos"] == []
    assert not r["passos"][0].get("aviso")


# ───────── D6 — o teto de passos diz QUAL nó está girando ─────────

def test_teto_de_passos_nomeia_o_no_em_laco(sessao, dados, ag, monkeypatch):
    """"Possível laço infinito" não dizia onde olhar — e quem lê isso está justamente
    procurando o nó que gira."""
    a = ag("Eterno")
    _mock_agente(monkeypatch, saida="de novo")
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "loop", "destino": "n1"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(RuntimeError) as e:
        motor.executar_cadeia(sessao, cadeia, "vai", max_passos=3)
    msg = str(e.value)
    assert "Eterno" in msg          # QUAL nó
    assert "3 vez" in msg           # quantas voltas deu
    assert "Limites da execução" in msg  # e o que fazer a respeito


# ───────── D7 — seta apontando para um passo que não existe ─────────

def test_destino_quebrado_explica_em_vez_de_despejar_um_id(sessao, dados, ag, monkeypatch):
    """Salvar pelo construtor já barra isto, mas um desenho antigo — ou escrito por
    fora, pelo MCP — chega ao motor. Quem lê não sabe o que é "nó da cadeia"."""
    a = ag("Solo")
    _mock_agente(monkeypatch, saida="ok")
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "ok", "destino": "fantasma"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(ValueError) as e:
        motor.executar_cadeia(sessao, cadeia, "vai")
    msg = str(e.value)
    assert "não existe mais" in msg
    assert "fantasma" in msg
    assert "construtor" in msg  # diz o que fazer


def test_destino_quebrado_e_barrado_ao_salvar(sessao, dados, ag):
    """A defesa de verdade é no salvamento: ali o consultor está com a tela aberta e
    conserta em dois cliques, em vez de descobrir no meio de uma execução."""
    a = ag("Solo")
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "ok", "quando": "sempre", "destino": "fantasma"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(ValueError, match="Destino inválido"):
        motor.validar_cadeia(cadeia, {str(a.id)})


# ───────── B7 — a execução que ninguém chegou a pegar ─────────

def _automacao(sessao, dados):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    return auto


def test_fila_parada_vira_alarme(sessao, dados, monkeypatch):
    """`aguardando` não era varrido por ninguém. Se o pool morre, o `/saude` acusa — mas
    um pool VIVO que mesmo assim não pega a execução deixava o disparo simplesmente não
    acontecer, em silêncio. É o disparo que não aconteceu, por outra porta."""
    auto = _automacao(sessao, dados)
    velha = Execucao(automacao_id=auto.id, estado="aguardando", entrada={"texto": "x"})
    sessao.add(velha)
    sessao.flush()
    velha.criado_em = datetime.now(timezone.utc) - timedelta(
        minutes=fila.TETO_ESPERA_NA_FILA_MIN + 5
    )
    sessao.flush()
    eventos = []
    monkeypatch.setattr(fila, "registrar_evento", lambda **kw: eventos.append(kw))

    assert fila.alertar_fila_parada(sessao) == 1

    alarme = [e for e in eventos if e.get("acao") == "fila.parada"]
    assert len(alarme) == 1 and alarme[0]["nivel"] == "error"
    assert str(velha.id) in alarme[0]["detalhe"]["execucoes"]
    # E NÃO muda o estado: o trabalho ainda pode rodar, e matá-lo seria pior que o atraso.
    sessao.refresh(velha)
    assert velha.estado == "aguardando"


def test_fila_recente_nao_alarma(sessao, dados, monkeypatch):
    auto = _automacao(sessao, dados)
    sessao.add(Execucao(automacao_id=auto.id, estado="aguardando", entrada={"texto": "x"}))
    sessao.flush()
    monkeypatch.setattr(fila, "registrar_evento", lambda **kw: None)
    assert fila.alertar_fila_parada(sessao) == 0


def test_retomada_na_fila_nao_conta_como_fila_parada(sessao, dados, monkeypatch):
    """O relógio de uma retomada começa no CLIQUE, não na criação: uma execução criada
    ontem e aprovada agora não é uma fila parada."""
    auto = _automacao(sessao, dados)
    ex = Execucao(
        automacao_id=auto.id, estado="aguardando", entrada={"texto": "x"},
        retomada_resposta="aprovado",
    )
    sessao.add(ex)
    sessao.flush()
    ex.criado_em = datetime.now(timezone.utc) - timedelta(days=1)
    sessao.flush()
    monkeypatch.setattr(fila, "registrar_evento", lambda **kw: None)
    assert fila.alertar_fila_parada(sessao) == 0
