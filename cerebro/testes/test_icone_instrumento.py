"""Ícone por instrumento: o usuário escolhe um ícone (id do catálogo da UI, ex.
"fab:telegram"); NULL = sem escolha (a interface mostra o genérico). É só
metadado de apresentação — guardamos como veio e devolvemos no InstrumentoLer."""


def _criar(cliente, dados, icone=None):
    corpo = {"nome": "Busca", "tipo": "busca_web", "configuracao": {}}
    if icone is not None:
        corpo["icone"] = icone
    return cliente.post(f"/times/{dados['timeA'].id}/instrumentos", json=corpo)


def test_criar_com_icone_devolve_icone(cliente, entrar, dados):
    entrar(dados["admin"])
    r = _criar(cliente, dados, icone="fab:telegram")
    assert r.status_code == 201
    assert r.json()["icone"] == "fab:telegram"


def test_criar_sem_icone_fica_nulo(cliente, entrar, dados):
    entrar(dados["admin"])
    r = _criar(cliente, dados)
    assert r.status_code == 201
    assert r.json()["icone"] is None


def test_editar_troca_e_limpa_o_icone(cliente, entrar, dados):
    entrar(dados["admin"])
    inst_id = _criar(cliente, dados, icone="fab:telegram").json()["id"]

    # troca o ícone
    r = cliente.put(
        f"/instrumentos/{inst_id}",
        json={"nome": "Busca", "configuracao": {}, "icone": "fas:database"},
    )
    assert r.status_code == 200
    assert r.json()["icone"] == "fas:database"

    # omitir/limpar o ícone (None) → volta ao genérico
    r2 = cliente.put(
        f"/instrumentos/{inst_id}",
        json={"nome": "Busca", "configuracao": {}},
    )
    assert r2.status_code == 200
    assert r2.json()["icone"] is None
