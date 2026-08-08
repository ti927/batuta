"""Filtro de campos do instrumento REST (corte de custo): `campos_resposta` enxuga
cada registro da resposta aos campos escolhidos. Cobre a função pura `_projetar_registros`
(formatos Bubble/lista/results/desconhecido) e o `executar` de ponta a ponta (com e sem
filtro → retrocompatível). Sem rede: o httpx é trocado por um cliente falso."""

import json

import instrumentos.rest as rest
from instrumentos.rest import ChamarApiRest, ConfigRest, _projetar_registros


# ---------------- função pura: _projetar_registros ----------------

def test_projeta_formato_bubble_response_results():
    corpo = {"response": {"results": [
        {"_id": "1", "cpo.NomeCliente": "ACME", "cpo.Interno": "x", "outro": 9},
        {"_id": "2", "cpo.NomeCliente": "Beta", "cpo.Interno": "y", "outro": 8},
    ], "remaining": 5}}
    out = _projetar_registros(corpo, ["_id", "cpo.NomeCliente"])
    assert out["response"]["results"] == [
        {"_id": "1", "cpo.NomeCliente": "ACME"},
        {"_id": "2", "cpo.NomeCliente": "Beta"},
    ]
    assert out["response"]["remaining"] == 5  # o resto do envelope é preservado


def test_projeta_lista_no_topo():
    corpo = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    assert _projetar_registros(corpo, ["a"]) == [{"a": 1}, {"a": 3}]


def test_projeta_results_no_topo():
    corpo = {"results": [{"a": 1, "b": 2}], "count": 1}
    out = _projetar_registros(corpo, ["a"])
    assert out == {"results": [{"a": 1}], "count": 1}


def test_formato_desconhecido_volta_intacto():
    # Sem lista de registros reconhecível → não mexe (nunca descarta dado por engano).
    corpo = {"chave": "valor", "aninhado": {"x": 1}}
    assert _projetar_registros(corpo, ["x"]) == corpo
    assert _projetar_registros("texto puro", ["x"]) == "texto puro"


def test_registro_nao_dict_e_campo_ausente():
    corpo = {"response": {"results": [{"a": 1}, "sou string", {"z": 9}]}}
    out = _projetar_registros(corpo, ["a"])
    # dict enxugado; não-dict intacto; registro sem o campo vira dict vazio (não quebra)
    assert out["response"]["results"] == [{"a": 1}, "sou string", {}]


# ---------------- executar de ponta a ponta (httpx falso) ----------------

class _RespFake:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.is_success = True
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _ClienteFake:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def request(self, *a, **k):
        return _RespFake(self._payload)


def _mock_httpx(monkeypatch, payload):
    monkeypatch.setattr(rest.httpx, "Client", lambda **k: _ClienteFake(payload))
    # o log de diagnóstico TEMP escreve no banco — silencia no teste
    monkeypatch.setattr(rest, "registrar_evento", lambda **k: None)


def test_executar_com_filtro_enxuga_a_resposta(monkeypatch):
    payload = {"response": {"results": [
        {"_id": "1", "cpo.NomeCliente": "ACME", "lixo": "x" * 500},
    ]}}
    _mock_httpx(monkeypatch, payload)
    inst = ChamarApiRest()
    cfg = ConfigRest(url="https://x", metodo="GET",
                     campos_resposta=["_id", "cpo.NomeCliente"])
    r = inst.executar(cfg, rest.ArgsRest())
    assert r["corpo"]["response"]["results"] == [{"_id": "1", "cpo.NomeCliente": "ACME"}]


def test_executar_sem_filtro_devolve_tudo(monkeypatch):
    payload = {"response": {"results": [{"_id": "1", "cpo.NomeCliente": "ACME", "extra": 7}]}}
    _mock_httpx(monkeypatch, payload)
    inst = ChamarApiRest()
    cfg = ConfigRest(url="https://x", metodo="GET")  # campos_resposta vazio (padrão)
    r = inst.executar(cfg, rest.ArgsRest())
    assert r["corpo"] == payload  # retrocompatível: nada é removido


def test_config_default_vazio():
    assert ConfigRest(url="https://x").campos_resposta == []
