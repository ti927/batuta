"""Motor de cadeia no formato de GRAFO (lista de nós tipados).

Cobre o `executar_cadeia` adaptado: linear, bifurcação (segue o ramo certo),
loop com guarda de passos, portão (gate) que pausa, nó roteador (classifica sem
rodar agente), nó fim como destino e o mesmo agente em dois nós (no_id distingue).

`executar_agente` e `_escolher_saida` são mockados — o motor não chama LLM aqui.
"""

import uuid

import pytest

from modelos import Agente
from orquestracao import cadeia as motor
from orquestracao.cadeia import validar_cadeia


@pytest.fixture
def ag(sessao, dados):
    """Fábrica de agentes reais no time de teste (transação revertida)."""
    def criar(nome):
        a = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
        sessao.add(a)
        sessao.flush()
        return a
    return criar


def _mock_agentes(monkeypatch, saidas_por_nome, ramos_por_nome=None):
    """Mocka `executar_agente`: devolve a saída (e, opcionalmente, o ramo declarado)
    configurada por nome do agente. Aceita `saidas`/`gate` (kwargs do motor)."""
    ramos_por_nome = ramos_por_nome or {}
    def fake(agente, cinto, entrada, **kwargs):
        return {
            "saida": saidas_por_nome.get(agente.nome, "ok"),
            "instrumentos_acionados": [],
            "uso": [],
            "ramo_escolhido": ramos_por_nome.get(agente.nome),
        }
    monkeypatch.setattr(motor, "executar_agente", fake)


def _mock_roteador(monkeypatch):
    """Mocka `_escolher_saida`: escolhe a saída cujo rótulo == texto (senão a 1ª)."""
    def fake(saida_texto, saidas):
        alvo = (saida_texto or "").strip()
        por_rotulo = {s["rotulo"]: s for s in saidas}
        uso = {"modelo": "x", "tokens_entrada": 0, "tokens_saida": 0}
        return por_rotulo.get(alvo, saidas[0]), uso
    monkeypatch.setattr(motor, "_escolher_saida", fake)


def test_linear_conclui(sessao, dados, ag, monkeypatch):
    a = ag("Solo")
    _mock_agentes(monkeypatch, {"Solo": "feito"})
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    assert r["resultado"] == "feito"
    # cada passo registra o id do nó
    assert r["passos"][0]["no_id"] == "n1"


def test_bifurcacao_segue_ramo_certo(sessao, dados, ag, monkeypatch):
    cacador = ag("Cacador")
    validador = ag("Validador")
    publicador = ag("Publicador")
    _mock_roteador(monkeypatch)

    cadeia = {
        "inicial": "cacador",
        "nos": [
            {"id": "cacador", "tipo": "agente", "ref": str(cacador.id),
             "saidas": [{"rotulo": "tema", "destino": "validador"}]},
            {"id": "validador", "tipo": "agente", "ref": str(validador.id),
             "saidas": [
                 {"rotulo": "ok", "destino": "publicador"},
                 {"rotulo": "refazer", "destino": "cacador"},
             ]},
            {"id": "publicador", "tipo": "agente", "ref": str(publicador.id),
             "saidas": [{"rotulo": "pub", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }

    # validador diz "ok" → segue para publicador (ramo ok)
    _mock_agentes(monkeypatch, {"Cacador": "tema", "Validador": "ok", "Publicador": "publicado"})
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    nos_visitados = [p["no_id"] for p in r["passos"]]
    assert nos_visitados == ["cacador", "validador", "publicador"]


def _mock_roteador_explode(monkeypatch):
    """`_escolher_saida` que estoura se for chamado — prova que o agente declarou e
    o roteador-adivinhador NÃO foi acionado."""
    def fake(saida_texto, saidas):
        raise AssertionError("o roteador não devia ser chamado: o agente declarou")
    monkeypatch.setattr(motor, "_escolher_saida", fake)


def test_ramo_declarado_pelo_agente_dispensa_o_roteador(sessao, dados, ag, monkeypatch):
    val = ag("Validador")
    pub = ag("Publicador")
    _mock_roteador_explode(monkeypatch)  # se chamado, falha
    _mock_agentes(
        monkeypatch,
        {"Validador": "texto qualquer", "Publicador": "pub"},
        ramos_por_nome={"Validador": "refazer"},  # agente declara "refazer"
    )
    cadeia = {
        "inicial": "validador",
        "nos": [
            {"id": "validador", "tipo": "agente", "ref": str(val.id),
             "saidas": [
                 {"rotulo": "ok", "destino": "publicador"},
                 {"rotulo": "refazer", "destino": "fim"},
             ]},
            {"id": "publicador", "tipo": "agente", "ref": str(pub.id),
             "saidas": [{"rotulo": "pub", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"  # "refazer" → fim
    assert [p["no_id"] for p in r["passos"]] == ["validador"]
    assert r["passos"][-1]["saida_escolhida"] == "refazer"


def test_rotulo_inexistente_cai_no_roteador(sessao, dados, ag, monkeypatch):
    val = ag("Validador")
    _mock_roteador(monkeypatch)  # fallback ativo
    _mock_agentes(
        monkeypatch,
        {"Validador": "ok"},
        ramos_por_nome={"Validador": "fantasma"},  # rótulo que não existe no nó
    )
    cadeia = {
        "inicial": "validador",
        "nos": [
            {"id": "validador", "tipo": "agente", "ref": str(val.id),
             "saidas": [
                 {"rotulo": "ok", "destino": "fim"},
                 {"rotulo": "refazer", "destino": "validador"},
             ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    # roteador (mock: rótulo == texto "ok") escolhe "ok" → conclui
    assert r["estado"] == "concluida"
    assert r["passos"][-1]["saida_escolhida"] == "ok"


def test_sem_declaracao_usa_o_roteador(sessao, dados, ag, monkeypatch):
    val = ag("Validador")
    _mock_roteador(monkeypatch)
    _mock_agentes(monkeypatch, {"Validador": "ok"})  # não declara ramo
    cadeia = {
        "inicial": "validador",
        "nos": [
            {"id": "validador", "tipo": "agente", "ref": str(val.id),
             "saidas": [
                 {"rotulo": "ok", "destino": "fim"},
                 {"rotulo": "refazer", "destino": "validador"},
             ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    assert r["passos"][-1]["saida_escolhida"] == "ok"


def test_loop_com_guarda_de_passos(sessao, dados, ag, monkeypatch):
    a = ag("Eterno")
    _mock_agentes(monkeypatch, {"Eterno": "de novo"})
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "loop", "destino": "n1"}]},  # volta para si mesmo
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(RuntimeError, match="Máximo de passos"):
        motor.executar_cadeia(sessao, cadeia, "vai", max_passos=3)


def test_gate_pausa(sessao, dados, ag, monkeypatch):
    revisor = ag("Revisor")
    _mock_agentes(monkeypatch, {"Revisor": "Artigo pronto para aprovação"})
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(revisor.id), "gate": True,
             "saidas": [
                 {"rotulo": "aprovado", "destino": "fim"},
                 {"rotulo": "reprovado", "destino": "rev"},
             ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "aguardando_humano"
    assert r["pergunta"] == "Artigo pronto para aprovação"
    # o nó com gate NÃO roteia sozinho (a resposta do humano decide depois)
    assert r["passos"][-1]["saida_escolhida"] is None
    assert r["passos"][-1]["no_id"] == "rev"


def test_no_roteador_classifica_sem_agente(sessao, dados, ag, monkeypatch):
    destino_a = ag("CaminhoA")
    _mock_agentes(monkeypatch, {"CaminhoA": "cheguei em A"})
    _mock_roteador(monkeypatch)
    cadeia = {
        "inicial": "rot",
        "nos": [
            {"id": "rot", "tipo": "roteador", "nome": "Triagem",
             "saidas": [
                 {"rotulo": "A", "destino": "na"},
                 {"rotulo": "B", "destino": "fim"},
             ]},
            {"id": "na", "tipo": "agente", "ref": str(destino_a.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    # entrada "A" → o roteador (mock) escolhe a saída de rótulo "A" → vai p/ o agente
    r = motor.executar_cadeia(sessao, cadeia, "A")
    assert r["estado"] == "concluida"
    assert r["resultado"] == "cheguei em A"
    primeiro = r["passos"][0]
    assert primeiro["no_id"] == "rot"
    assert primeiro["agente_id"] is None  # roteador não roda agente
    assert primeiro["saida_escolhida"] == "A"


def test_mesmo_agente_em_dois_nos(sessao, dados, ag, monkeypatch):
    a = ag("Reaproveitado")
    _mock_agentes(monkeypatch, {"Reaproveitado": "ok"})
    _mock_roteador(monkeypatch)
    cadeia = {
        "inicial": "p1",
        "nos": [
            {"id": "p1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "segue", "destino": "p2"}]},
            {"id": "p2", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "fim", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    nos = [p["no_id"] for p in r["passos"]]
    agentes = [p["agente_id"] for p in r["passos"]]
    assert nos == ["p1", "p2"]               # dois nós distintos
    assert agentes == [str(a.id), str(a.id)]  # o mesmo agente nos dois


def test_validar_rascunho_so_gatilho_e_fim_nao_levanta():
    # rascunho permitido: nada para rodar ainda (sem agente/roteador) → não exige início
    cadeia = {
        "inicial": None,
        "nos": [
            {"id": "gatilho", "tipo": "gatilho", "gatilho": "manual", "saidas": []},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    validar_cadeia(cadeia, set())  # não levanta


def test_validar_executavel_sem_inicio_erro_acionavel():
    # há um nó executável (roteador) mas nenhum início escolhido → erro H1 claro
    cadeia = {
        "nos": [
            {"id": "gatilho", "tipo": "gatilho", "gatilho": "manual", "saidas": []},
            {"id": "rot", "tipo": "roteador", "nome": "T",
             "saidas": [{"rotulo": "a", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(ValueError, match="início que possa rodar"):
        validar_cadeia(cadeia, set())


def test_ref_para_agente_inexistente_erro_cita_o_no(sessao, dados):
    # nó cujo `ref` aponta para um agente que não existe mais → erro claro com o no_id
    fantasma = str(uuid.uuid4())
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": fantasma,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(ValueError) as exc:
        motor.executar_cadeia(sessao, cadeia, "vai")
    assert "n1" in str(exc.value)
    assert "não existe mais" in str(exc.value)


def test_retomada_por_no_inicial(sessao, dados, ag, monkeypatch):
    """Retomada começa de um nó específico (como faz a `retoma`)."""
    pub = ag("Publi")
    _mock_agentes(monkeypatch, {"Publi": "publicado"})
    _mock_roteador(monkeypatch)
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(pub.id), "gate": True,
             "saidas": [{"rotulo": "ok", "destino": "pub"}]},
            {"id": "pub", "tipo": "agente", "ref": str(pub.id),
             "saidas": [{"rotulo": "fim", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "feedback", no_inicial="pub")
    assert r["estado"] == "concluida"
    assert [p["no_id"] for p in r["passos"]] == ["pub"]
