"""Testes da duplicação de automação (POST /automacoes/{id}/duplicar).

Cobre: cópia bem-sucedida (id/datas novos, mesmo time, design preservado),
a cópia nascendo SEMPRE inativa (proteção contra disparo em dobro de gatilho
agendado), o deep-copy que isola a cópia da original, a matriz de acesso
(operador cria; observador 403; estranho 404) e a validação da cadeia (ref de
agente órfão → 422). Roda na transação revertida do conftest.
"""

import uuid

import pytest

import agendador
from modelos import Agente, Automacao


@pytest.fixture
def auto_pronta(sessao, dados):
    """Uma automação manual válida no time A, com um agente real na cadeia.
    A cadeia é gravada SEM as flags derivadas (ex.: `n1.inicial`) de propósito —
    assim o teste de deep-copy consegue detectar se a normalização da cópia
    vazou para a original."""
    ag = Agente(time_id=dados["timeA"].id, nome="Solo", papel="agente")
    sessao.add(ag)
    sessao.flush()
    cadeia = {
        "inicial": "n1",
        "nos": [
            {
                "id": "gatilho", "tipo": "gatilho", "gatilho": "manual",
                "saidas": [{"rotulo": "inicia o fluxo", "destino": "n1"}],
            },
            {
                "id": "n1", "tipo": "agente", "ref": str(ag.id),
                "saidas": [{"rotulo": "ok", "destino": "fim"}],
            },
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Original",
        tipo_gatilho="manual", configuracao_gatilho={}, cadeia=cadeia, ativa=False,
    )
    sessao.add(auto)
    sessao.flush()
    return {"auto": auto, "agente": ag}


def test_duplicar_sucesso(cliente, entrar, dados, auto_pronta):
    entrar(dados["operador"])
    original = auto_pronta["auto"]
    r = cliente.post(f"/automacoes/{original.id}/duplicar", json={"nome": "Minha cópia"})
    assert r.status_code == 201
    copia = r.json()
    assert copia["id"] != str(original.id)            # id novo
    assert copia["nome"] == "Minha cópia"
    assert copia["time_id"] == str(original.time_id)  # mesmo time
    assert copia["ativa"] is False                    # nasce pausada
    assert copia["tipo_gatilho"] == "manual"
    assert copia["configuracao_gatilho"] == {}
    # o design da cadeia foi preservado (nó-agente aponta para o mesmo agente)
    assert copia["cadeia"]["inicial"] == "n1"
    n1 = next(n for n in copia["cadeia"]["nos"] if n["id"] == "n1")
    assert n1["ref"] == str(auto_pronta["agente"].id)


def test_duplicar_preserva_gatilho_mas_nasce_inativa(
    cliente, entrar, dados, sessao, monkeypatch
):
    """Duplicar uma automação AGENDADA e ATIVA: a cópia preserva o tipo de gatilho
    e a config, mas nasce inativa — é o que impede o disparo em dobro (o agendador
    só cria job para automações ativas)."""
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Relatório diário",
        tipo_gatilho="agendamento",
        configuracao_gatilho={"frequencia": "diaria", "hora": 8, "minuto": 0,
                              "entrada": "rode"},
        cadeia={}, ativa=True,
    )
    sessao.add(auto)
    sessao.flush()

    # captura o que é entregue ao agendador, sem depender do estado do APScheduler
    recebido = {}
    monkeypatch.setattr(
        agendador, "sincronizar", lambda a: recebido.update(ativa=a.ativa, tipo=a.tipo_gatilho)
    )

    entrar(dados["operador"])
    r = cliente.post(f"/automacoes/{auto.id}/duplicar", json={"nome": "Cópia agendada"})
    assert r.status_code == 201
    copia = r.json()
    assert copia["ativa"] is False                           # nasce pausada
    assert copia["tipo_gatilho"] == "agendamento"            # gatilho preservado
    assert copia["configuracao_gatilho"]["hora"] == 8        # config preservada
    # o agendador recebeu a cópia INATIVA → não vira job (sem disparo em dobro)
    assert recebido == {"ativa": False, "tipo": "agendamento"}


def test_duplicar_deep_copy_nao_mexe_na_original(cliente, entrar, dados, auto_pronta):
    """A normalização da cópia não pode vazar para a original (deep-copy). Como o
    endpoint lê a original pela MESMA sessão (identity map), `original.cadeia` aqui
    é o mesmo objeto em memória que o endpoint usou: se faltasse o deepcopy, a
    normalização da cópia teria injetado a flag `inicial` nos nós da original."""
    entrar(dados["operador"])
    original = auto_pronta["auto"]
    n1_antes = next(n for n in original.cadeia["nos"] if n["id"] == "n1")
    assert "inicial" not in n1_antes  # ainda cru, sem flag derivada

    r = cliente.post(f"/automacoes/{original.id}/duplicar", json={"nome": "Cópia"})
    assert r.status_code == 201

    n1_depois = next(n for n in original.cadeia["nos"] if n["id"] == "n1")
    assert "inicial" not in n1_depois  # original intacta — deepcopy funcionou


def test_duplicar_nome_em_branco_422(cliente, entrar, dados, auto_pronta):
    entrar(dados["operador"])
    r = cliente.post(
        f"/automacoes/{auto_pronta['auto'].id}/duplicar", json={"nome": "   "}
    )
    assert r.status_code == 422


def test_duplicar_observador_403(cliente, entrar, dados, auto_pronta):
    entrar(dados["observador"])  # membro, mas sem papel de operador
    r = cliente.post(
        f"/automacoes/{auto_pronta['auto'].id}/duplicar", json={"nome": "Cópia"}
    )
    assert r.status_code == 403


def test_duplicar_estranho_404(cliente, entrar, dados, auto_pronta):
    entrar(dados["estranho"])  # de outra organização → nem enxerga
    r = cliente.post(
        f"/automacoes/{auto_pronta['auto'].id}/duplicar", json={"nome": "Cópia"}
    )
    assert r.status_code == 404


def test_duplicar_cadeia_com_ref_orfao_422(cliente, entrar, dados, sessao):
    """Se a cadeia da original referencia um agente que não existe mais, a cópia
    é barrada com 422 (mesma validação do criar/editar)."""
    fantasma = str(uuid.uuid4())
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Quebrada", tipo_gatilho="manual",
        configuracao_gatilho={},
        cadeia={
            "inicial": "n1",
            "nos": [
                {"id": "n1", "tipo": "agente", "ref": fantasma,
                 "saidas": [{"rotulo": "ok", "destino": "fim"}]},
                {"id": "fim", "tipo": "fim", "saidas": []},
            ],
        },
        ativa=False,
    )
    sessao.add(auto)
    sessao.flush()

    entrar(dados["operador"])
    r = cliente.post(f"/automacoes/{auto.id}/duplicar", json={"nome": "Cópia"})
    assert r.status_code == 422
