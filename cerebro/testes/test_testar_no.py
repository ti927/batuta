"""Onda 4, fatia 5 — "Testar este nó" (lacuna 26).

Para experimentar UM agente — ver se o markdown está bom, se o instrumento responde —
era preciso rodar a automação INTEIRA, pagando todos os passos anteriores e acionando
tudo o que vem depois. Quem desenhava um fluxo de 6 passos para ajustar o 4º pagava os
3 primeiros a cada tentativa.

O teste é uma execução DE VERDADE: custa e aciona os instrumentos REAIS do agente
(testar um passo que publica, publica mesmo). O que muda é só onde ela para. Aqui
provamos que ela para no primeiro passo, que não segue as setas, que uma aprovação
pedida no teste não deixa o fluxo pendurado, e que ela NÃO conta para o disjuntor —
um teste que falha nunca pode desligar a automação de alguém.
"""

import pytest

from modelos import Agente, Automacao, Execucao
from orquestracao import circuito, disparo, grafo
from orquestracao.cadeia import AVISO_TESTE_PEDIU_APROVACAO, executar_cadeia

NO_1, NO_2 = "n1", "n2"


def _cadeia(ag_id: str) -> dict:
    return grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": NO_2}]},
            {"id": NO_2, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })


@pytest.fixture
def cenario(sessao, dados, monkeypatch):
    ag = Agente(time_id=dados["timeA"].id, nome="Redator", papel="agente")
    sessao.add(ag)
    sessao.flush()
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Post", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=_cadeia(str(ag.id)), ativa=True,
        configuracao={},
    )
    sessao.add(auto)
    sessao.commit()

    def _fake(*a, **k):
        return {
            "saida": "escrevi", "instrumentos_acionados": [], "erros_instrumentos": [],
            "uso": [], "mensagens_enviadas": {}, "ramos_escolhidos": ["ok"],
            "pausado": False, "anotacoes": {},
        }

    monkeypatch.setattr("orquestracao.cadeia.executar_agente", _fake)
    return ag, auto


# ───────────────────────── o motor para no primeiro ─────────────────────────


def test_so_um_passo_roda_um_no_e_para(sessao, cenario):
    ag, auto = cenario

    r = executar_cadeia(sessao, auto.cadeia, "entrada de mentira", so_um_passo=True)

    assert r["estado"] == "concluida"
    assert len(r["passos"]) == 1  # não seguiu a seta para o n2
    assert r["passos"][0]["no_id"] == NO_1
    assert r["resultado"] == "escrevi"


def test_sem_a_bandeira_o_fluxo_segue_normal(sessao, cenario):
    """A bandeira é aditiva: desligada, o caminho é o de sempre."""
    _, auto = cenario

    r = executar_cadeia(sessao, auto.cadeia, "vai", so_um_passo=False)

    assert r["estado"] == "concluida"
    assert len(r["passos"]) == 2


def test_pode_testar_um_no_do_MEIO_do_fluxo(sessao, cenario):
    """O ponto da fatia: ajustar o 4º passo sem pagar os 3 primeiros."""
    _, auto = cenario

    r = executar_cadeia(sessao, auto.cadeia, "vai", no_inicial=NO_2, so_um_passo=True)

    assert len(r["passos"]) == 1
    assert r["passos"][0]["no_id"] == NO_2


def test_aprovacao_pedida_no_teste_nao_deixa_o_fluxo_pendurado(
    sessao, dados, monkeypatch
):
    """O pedido REALMENTE foi enviado (o instrumento é real), mas deixar uma aprovação
    pendente nascida de um teste seria pedir ao aprovador que decidisse sobre algo que
    não vai a lugar nenhum. O teste termina e o rastro conta as duas coisas."""
    ag = Agente(time_id=dados["timeA"].id, nome="Revisor", papel="agente")
    sessao.add(ag)
    sessao.flush()
    cadeia = _cadeia(str(ag.id))

    def _pede_aprovacao(*a, **k):
        return {
            "saida": "Posso publicar?", "instrumentos_acionados": ["pedir_aprovacao"],
            "erros_instrumentos": [], "uso": [], "mensagens_enviadas": {},
            "ramos_escolhidos": [], "pausado": True,
            "aprovacao": {"canal_instrumento_id": None}, "anotacoes": {},
        }

    monkeypatch.setattr("orquestracao.cadeia.executar_agente", _pede_aprovacao)

    r = executar_cadeia(sessao, cadeia, "texto", so_um_passo=True)

    assert r["estado"] == "concluida"  # e NÃO aguardando_humano
    assert AVISO_TESTE_PEDIU_APROVACAO in r["avisos"]
    assert "enviado de verdade" in AVISO_TESTE_PEDIU_APROVACAO


# ───────────────────────────── a rota ─────────────────────────────


def test_rota_cria_execucao_de_teste_marcada(cliente, entrar, sessao, dados, cenario):
    _, auto = cenario
    entrar(dados["operador"])

    r = cliente.post(
        f"/automacoes/{auto.id}/testar-no",
        json={"no_id": NO_2, "entrada": "um texto qualquer"},
    )

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["teste_de_no"] is True
    assert corpo["no_inicial"] == NO_2
    assert corpo["entrada"]["texto"] == "um texto qualquer"
    ex = sessao.get(Execucao, __import__("uuid").UUID(corpo["id"]))
    assert ex.origem == "teste"


def test_rota_recusa_no_inexistente(cliente, entrar, dados, cenario):
    _, auto = cenario
    entrar(dados["operador"])

    r = cliente.post(
        f"/automacoes/{auto.id}/testar-no", json={"no_id": "nao-existe", "entrada": "x"}
    )

    assert r.status_code == 422
    assert "não existe" in r.json()["detail"]


def test_rota_recusa_no_estrutural(cliente, entrar, dados, cenario):
    """Início, fim e "Para cada item" não executam nada — testar não faria sentido."""
    _, auto = cenario
    entrar(dados["operador"])

    r = cliente.post(
        f"/automacoes/{auto.id}/testar-no", json={"no_id": "fim", "entrada": "x"}
    )

    assert r.status_code == 422
    assert "não executa nada" in r.json()["detail"]


def test_observador_nao_testa(cliente, entrar, dados, cenario):
    """Testar gasta dinheiro e pode publicar: é ação de operador para cima."""
    _, auto = cenario
    entrar(dados["observador"])

    r = cliente.post(
        f"/automacoes/{auto.id}/testar-no", json={"no_id": NO_1, "entrada": "x"}
    )

    assert r.status_code == 403


# ────────────────── a fronteira com o disjuntor (fatia 3) ──────────────────


def test_teste_que_falha_nunca_desliga_a_automacao(sessao, dados, cenario, monkeypatch):
    """`origem="teste"` fica fora de `ORIGENS_SOZINHA`, então três testes que falham
    NÃO desligam a automação de ninguém. Testar tem de ser seguro."""
    monkeypatch.setattr("mensageria.aviso.avisar_falha", lambda *a, **k: None)
    _, auto = cenario
    assert "teste" not in circuito.ORIGENS_SOZINHA

    for _ in range(3):
        ex = disparo.criar_execucao(
            sessao, auto, "x", origem="teste", no_inicial=NO_1, teste_de_no=True
        )
        ex.estado = "falhou"
        ex.resultado = {"erro": "quebrou"}
        sessao.commit()

    assert circuito.falhas_seguidas(sessao, auto) == 0
    assert circuito.apos_falha(sessao, ex, "quebrou") is False
    sessao.refresh(auto)
    assert auto.ativa is True
