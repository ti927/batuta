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
    # A porta de saída (`http_saida.cliente`) é por onde o REST chama desde a queda
    # para IPv4 — é ela que o teste intercepta.
    monkeypatch.setattr(rest.http_saida, "cliente", lambda **k: _ClienteFake(payload))


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


# ---------------- caminhos (2026-10-02): lista com outro nome e campo aninhado ----------------

ZERNIO = {
    "posts": [
        {"_id": "p1", "content": "texto longo" * 50, "analytics": {"views": 10, "likes": 2, "extra": "x"},
         "platforms": [{"platform": "instagram", "status": "published", "raw": {"muito": "dado"}}]},
        {"_id": "p2", "content": "outro", "analytics": {"views": 5, "likes": 0, "extra": "y"},
         "platforms": [{"platform": "instagram", "status": "failed", "raw": {}}]},
    ],
    "pagination": {"page": 1, "total": 2},
}


def test_caminho_com_lista_de_outro_nome_e_campo_aninhado():
    out = _projetar_registros(
        ZERNIO, ["posts[]._id", "posts[].analytics.views", "posts[].platforms[].status"]
    )
    assert out == {"posts": [
        {"_id": "p1", "analytics": {"views": 10}, "platforms": [{"status": "published"}]},
        {"_id": "p2", "analytics": {"views": 5}, "platforms": [{"status": "failed"}]},
    ]}


def test_ponto_dentro_do_registro_reconhecido_sozinho():
    corpo = {"data": [{"id": 1, "stats": {"a": 1, "b": 2}}, {"id": 2, "stats": {"a": 3, "b": 4}}]}
    assert _projetar_registros(corpo, ["id", "stats.a"]) == {
        "data": [{"id": 1, "stats": {"a": 1}}, {"id": 2, "stats": {"a": 3}}]
    }


def test_nome_com_ponto_do_bubble_continua_valendo_inteiro():
    corpo = {"response": {"results": [{"_id": "1", "cpo.NomeCliente": "Ana", "outro": 1}]}}
    assert _projetar_registros(corpo, ["cpo.NomeCliente"]) == {
        "response": {"results": [{"cpo.NomeCliente": "Ana"}]}
    }


def test_caminho_que_nao_casa_devolve_intacto():
    assert _projetar_registros(ZERNIO, ["itens[].id"]) == ZERNIO


def test_aviso_do_construtor_entende_caminho():
    from instrumentos.rest import campos_resposta_nao_casam

    assert campos_resposta_nao_casam(ZERNIO, ["itens[].id"]) is True
    assert campos_resposta_nao_casam(ZERNIO, ["posts[]._id"]) is False
