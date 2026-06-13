"""Testes dos endpoints de canais e identidades (Passo 3).

Cobrem papéis (admin gere canal; operador gere identidade; observador só vê),
isolamento entre organizações, o segredo (token) NUNCA reexibido, a preservação
do token na edição, e o cascade ao remover o canal.
"""

from sqlalchemy import select

from modelos import IdentidadeCanal, SegredoCanal


def _criar_canal(cliente, org_id, token="123456:ABCdefToken9999", nome="Telegram Lure"):
    return cliente.post(
        f"/organizacoes/{org_id}/canais",
        json={"tipo": "telegram", "nome": nome, "config": {"token": token}},
    )


# ──────────────────────────────── Canais ─────────────────────────────────────


def test_admin_cria_canal_telegram(cliente, entrar, dados):
    entrar(dados["admin"])
    r = _criar_canal(cliente, dados["orgA"].id)
    assert r.status_code == 201
    corpo = r.json()
    # O token NUNCA volta; nem em config, nem em campo próprio. Só os 4 últimos.
    assert "token" not in (corpo["config"] or {})
    assert corpo["segredos"] == {"token": "9999"}
    assert corpo["tipo"] == "telegram" and corpo["nome"] == "Telegram Lure"
    assert corpo["ativo"] is True


def test_operador_nao_cria_canal(cliente, entrar, dados):
    entrar(dados["operador"])
    assert _criar_canal(cliente, dados["orgA"].id).status_code == 403


def test_observador_lista_canais(cliente, entrar, dados):
    entrar(dados["admin"])
    _criar_canal(cliente, dados["orgA"].id)
    entrar(dados["observador"])
    r = cliente.get(f"/organizacoes/{dados['orgA'].id}/canais")
    assert r.status_code == 200 and len(r.json()) == 1


def test_isolamento_entre_organizacoes(cliente, entrar, dados):
    # 'estranho' é admin só da Org B → não enxerga a Org A (404, não 403).
    entrar(dados["estranho"])
    assert _criar_canal(cliente, dados["orgA"].id).status_code == 404


def test_tipo_desconhecido_recusado(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/canais",
        json={"tipo": "fax", "nome": "X", "config": {}},
    )
    assert r.status_code == 422


def test_editar_canal_preserva_token_em_branco(cliente, entrar, dados):
    entrar(dados["admin"])
    canal_id = _criar_canal(cliente, dados["orgA"].id).json()["id"]
    # Edita o nome SEM reenviar o token → segredo preservado.
    r = cliente.put(
        f"/organizacoes/{dados['orgA'].id}/canais/{canal_id}",
        json={"nome": "Telegram interno", "config": {}, "ativo": False},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["nome"] == "Telegram interno" and corpo["ativo"] is False
    assert corpo["segredos"] == {"token": "9999"}  # token continua lá


def test_editar_canal_troca_token(cliente, entrar, dados):
    entrar(dados["admin"])
    canal_id = _criar_canal(cliente, dados["orgA"].id).json()["id"]
    r = cliente.put(
        f"/organizacoes/{dados['orgA'].id}/canais/{canal_id}",
        json={"nome": "Telegram Lure", "config": {"token": "999:novoToken4321"}, "ativo": True},
    )
    assert r.status_code == 200 and r.json()["segredos"] == {"token": "4321"}


def test_remover_canal_cascateia(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    canal_id = _criar_canal(cliente, dados["orgA"].id).json()["id"]
    cliente.post(
        f"/organizacoes/{dados['orgA'].id}/canais/{canal_id}/identidades",
        json={"identificador_externo": "111", "rotulo": "João"},
    )
    assert (
        cliente.delete(
            f"/organizacoes/{dados['orgA'].id}/canais/{canal_id}"
        ).status_code
        == 204
    )
    # FK CASCADE limpou identidades e segredos do canal.
    assert sessao.scalars(
        select(IdentidadeCanal).where(IdentidadeCanal.canal_id == canal_id)
    ).first() is None
    assert sessao.scalars(
        select(SegredoCanal).where(SegredoCanal.canal_id == canal_id)
    ).first() is None


# ────────────────────────────── Identidades ──────────────────────────────────


def test_operador_cria_identidade(cliente, entrar, dados):
    entrar(dados["admin"])
    canal_id = _criar_canal(cliente, dados["orgA"].id).json()["id"]
    entrar(dados["operador"])
    r = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/canais/{canal_id}/identidades",
        json={"identificador_externo": "987654", "rotulo": "Maria, cliente X"},
    )
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["identificador_externo"] == "987654"
    assert corpo["rotulo"] == "Maria, cliente X"
    assert corpo["canal_id"] == canal_id


def test_observador_nao_cria_identidade(cliente, entrar, dados):
    entrar(dados["admin"])
    canal_id = _criar_canal(cliente, dados["orgA"].id).json()["id"]
    entrar(dados["observador"])
    r = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/canais/{canal_id}/identidades",
        json={"identificador_externo": "1", "rotulo": "x"},
    )
    assert r.status_code == 403


def test_identidade_duplicada_recusada(cliente, entrar, dados):
    entrar(dados["admin"])
    canal_id = _criar_canal(cliente, dados["orgA"].id).json()["id"]
    url = f"/organizacoes/{dados['orgA'].id}/canais/{canal_id}/identidades"
    assert cliente.post(url, json={"identificador_externo": "55", "rotulo": "a"}).status_code == 201
    assert cliente.post(url, json={"identificador_externo": "55", "rotulo": "b"}).status_code == 409


def test_editar_e_remover_identidade(cliente, entrar, dados):
    entrar(dados["admin"])
    canal_id = _criar_canal(cliente, dados["orgA"].id).json()["id"]
    url = f"/organizacoes/{dados['orgA'].id}/canais/{canal_id}/identidades"
    ident_id = cliente.post(url, json={"identificador_externo": "77", "rotulo": "antigo"}).json()["id"]
    r = cliente.put(f"{url}/{ident_id}", json={"rotulo": "novo"})
    assert r.status_code == 200 and r.json()["rotulo"] == "novo"
    assert cliente.delete(f"{url}/{ident_id}").status_code == 204
    assert cliente.get(url).json() == []
