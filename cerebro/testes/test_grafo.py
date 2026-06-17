"""Testes do normalizador de grafo (orquestracao/grafo.py) — puro, sem banco.

Cobrem: conversão do formato antigo (dict-por-agente) para a forma canônica
(lista de nós tipados), normalização de um grafo simplificado da IA, idempotência
e o índice de travessia usado pelo motor.
"""

from orquestracao import grafo


def _ids(cadeia):
    return {n["id"] for n in cadeia["nos"]}


def _tipos(cadeia):
    return {n["id"]: n["tipo"] for n in cadeia["nos"]}


def test_vazia_vira_rascunho():
    assert grafo.normalizar(None) == {}
    assert grafo.normalizar({}) == {}
    assert grafo.normalizar({"nos": []}) == {}
    assert grafo.normalizar({"nos": {}, "inicio": None}) == {}


def test_converte_formato_antigo_linear():
    antiga = {
        "inicio": "a1",
        "nos": {
            "a1": {"saidas": [{"rotulo": "ok", "quando": "sempre", "destino": "a2"}]},
            "a2": {"pausa_humano": True, "saidas": [{"rotulo": "pub", "destino": None}]},
        },
    }
    g = grafo.normalizar(antiga)

    assert g["inicial"] == "a1"
    tipos = _tipos(g)
    # nós-agente preservados + gatilho e fim criados
    assert tipos["a1"] == "agente" and tipos["a2"] == "agente"
    assert grafo.ID_GATILHO in tipos and tipos[grafo.ID_GATILHO] == "gatilho"
    assert grafo.ID_FIM in tipos and tipos[grafo.ID_FIM] == "fim"

    nos = {n["id"]: n for n in g["nos"]}
    # ref do agente preservado; pausa_humano -> gate
    assert nos["a1"]["ref"] == "a1"
    assert nos["a2"]["gate"] is True
    assert nos["a1"]["gate"] is False
    # destino sentinela (None) -> nó fim
    assert nos["a2"]["saidas"][0]["destino"] == grafo.ID_FIM
    # gatilho aponta para o inicial
    assert nos[grafo.ID_GATILHO]["saidas"][0]["destino"] == "a1"
    # 'quando' preservado para o roteador
    assert nos["a1"]["saidas"][0]["quando"] == "sempre"
    # inicial marcado no nó
    assert nos["a1"]["inicial"] is True


def test_normaliza_grafo_simplificado_da_ia():
    # A IA manda só nós-agente + saídas + qual é o inicial; o resto é preenchido.
    simplificado = {
        "inicial": "cacador",
        "nos": [
            {"id": "cacador", "tipo": "agente", "ref": "ag-1",
             "saidas": [{"rotulo": "tema", "destino": "validador"}]},
            {"id": "validador", "tipo": "agente", "ref": "ag-2", "gate": True,
             "saidas": [
                 {"rotulo": "ok", "destino": "fim", "tone": "ok"},
                 {"rotulo": "refazer", "destino": "cacador", "tone": "loop"},
             ]},
        ],
    }
    g = grafo.normalizar(simplificado)
    nos = {n["id"]: n for n in g["nos"]}

    assert g["inicial"] == "cacador"
    assert "gatilho" in nos and "fim" in nos
    # ids de saída preenchidos; tone default normal quando ausente
    assert nos["cacador"]["saidas"][0]["id"]
    assert nos["cacador"]["saidas"][0]["tone"] == "normal"
    assert nos["validador"]["saidas"][0]["tone"] == "ok"
    # destino "fim" textual vira o id do nó fim (que aqui é "fim")
    assert nos["validador"]["saidas"][0]["destino"] == "fim"
    # loop preservado (destino é um nó anterior)
    assert nos["validador"]["saidas"][1]["destino"] == "cacador"
    # posições preenchidas (cosméticas)
    assert all("x" in n and "y" in n for n in g["nos"])


def test_idempotente():
    antiga = {
        "inicio": "a1",
        "nos": {
            "a1": {"saidas": [{"rotulo": "ok", "destino": "a2"}]},
            "a2": {"pausa_humano": True, "saidas": [{"rotulo": "fim", "destino": None}]},
        },
    }
    uma = grafo.normalizar(antiga)
    duas = grafo.normalizar(uma)
    assert uma == duas


def test_preserva_posicoes_do_usuario():
    cadeia = {
        "inicial": "a1",
        "nos": [
            {"id": "a1", "tipo": "agente", "ref": "a1", "x": 999, "y": 111,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
        ],
    }
    g = grafo.normalizar(cadeia)
    a1 = next(n for n in g["nos"] if n["id"] == "a1")
    assert a1["x"] == 999 and a1["y"] == 111


def test_ids_de_no_unicos_quando_repetidos():
    cadeia = {
        "inicial": "x",
        "nos": [
            {"id": "x", "tipo": "agente", "ref": "ag", "saidas": []},
            {"id": "x", "tipo": "agente", "ref": "ag", "saidas": []},
        ],
    }
    g = grafo.normalizar(cadeia)
    ids = [n["id"] for n in g["nos"]]
    assert len(ids) == len(set(ids))  # sem duplicatas


def test_gatilho_solto_e_ligado_ao_inicial():
    # grafo recém-montado: gatilho sem saída + um agente; normalizar liga o gatilho.
    cadeia = {
        "inicial": "a1",
        "nos": [
            {"id": "gatilho", "tipo": "gatilho", "gatilho": "manual", "saidas": []},
            {"id": "a1", "tipo": "agente", "ref": "ag", "saidas": [{"rotulo": "ok", "destino": "fim"}]},
        ],
    }
    g = grafo.normalizar(cadeia)
    nos = {n["id"]: n for n in g["nos"]}
    assert nos["gatilho"]["saidas"][0]["destino"] == "a1"


def test_inicial_invalido_recuperado_e_gatilho_religado():
    # inicial aponta p/ id inexistente e o gatilho tem destino "velho": normalizar
    # recupera o inicial p/ o 1º agente E re-aponta o gatilho a ele. (É o cenário do
    # bug recorrente: a TELA precisa fazer o MESMO via normalizarCadeia.)
    cadeia = {
        "inicial": "fantasma",
        "nos": [
            {"id": "gatilho", "tipo": "gatilho", "gatilho": "manual",
             "saidas": [{"rotulo": "x", "destino": "fantasma"}]},
            {"id": "a1", "tipo": "agente", "ref": "ag-1",
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    g = grafo.normalizar(cadeia)
    nos = {n["id"]: n for n in g["nos"]}
    assert g["inicial"] == "a1"
    assert nos["gatilho"]["saidas"][0]["destino"] == "a1"  # gatilho religado
    assert nos["a1"]["inicial"] is True
    # idempotente mesmo partindo de inicial inválido
    assert grafo.normalizar(g) == g


def test_indexar_e_eh_fim():
    g = grafo.normalizar(
        {
            "inicio": "a1",
            "nos": {"a1": {"saidas": [{"rotulo": "ok", "destino": None}]}},
        }
    )
    idx = grafo.indexar(g)
    assert idx.inicial == "a1"
    assert idx.no("a1")["tipo"] == "agente"
    # destino do a1 aponta para o nó fim → eh_fim True
    destino = idx.saidas("a1")[0]["destino"]
    assert idx.eh_fim(destino) is True
    # sentinelas antigas continuam sendo fim
    assert idx.eh_fim(None) is True
    assert idx.eh_fim("fim") is True
    assert idx.eh_fim("a1") is False
