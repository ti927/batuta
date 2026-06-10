"""Testes do logo da organização (data URI no banco): criar/editar com logo,
remover o logo, e a validação do campo (só data URI de imagem, com teto)."""

LOGO_OK = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAA=="


def test_criar_organizacao_com_logo(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.post("/organizacoes", json={"nome": "Com Logo", "logo_url": LOGO_OK})
    assert r.status_code == 201
    assert r.json()["logo_url"] == LOGO_OK


def test_criar_sem_logo_fica_nulo(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.post("/organizacoes", json={"nome": "Sem Logo"})
    assert r.status_code == 201 and r.json()["logo_url"] is None


def test_editar_define_e_remove_logo(cliente, entrar, dados):
    entrar(dados["admin"])
    org = dados["orgA"].id
    # Define o logo.
    r = cliente.put(f"/organizacoes/{org}", json={"nome": "Org A", "logo_url": LOGO_OK})
    assert r.status_code == 200 and r.json()["logo_url"] == LOGO_OK
    # Remove o logo (envia null) — volta a sem logo.
    r2 = cliente.put(f"/organizacoes/{org}", json={"nome": "Org A", "logo_url": None})
    assert r2.status_code == 200 and r2.json()["logo_url"] is None


def test_logo_nao_imagem_recusado(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.post("/organizacoes", json={"nome": "X", "logo_url": "não é imagem"})
    assert r.status_code == 422


def test_logo_grande_demais_recusado(cliente, entrar, dados):
    entrar(dados["admin"])
    enorme = "data:image/png;base64," + ("A" * 1_000_001)
    r = cliente.post("/organizacoes", json={"nome": "X", "logo_url": enorme})
    assert r.status_code == 422
