"""A porta INTERNA serviço-a-serviço (`rotas/interno.py`).

Ela existe para a IA poder TESTAR um conector sem nunca ver o segredo dele: o MCP roda
sem a chave-mestra do cofre (decisão: a IA nunca recebe segredo), então pede ao cérebro
que rode o teste e recebe só a resposta da API.

Uma porta serviço-a-serviço é exatamente o tipo de coisa que, feita mal, vira a maior
falha de segurança do sistema. Os testes aqui são sobre o que a protege:

1. sem a variável de ambiente, a porta NÃO EXISTE (404);
2. o segredo certo NÃO autoriza sozinho — o papel do usuário continua valendo;
3. ela faz UMA coisa e não devolve segredo.
"""

import uuid

import pytest


@pytest.fixture
def ligada(monkeypatch):
    monkeypatch.setenv("BATUTA_INTERNO_SECRET", "segredo-interno-de-teste")


CAMINHO = "/interno/conector/testar-operacao"


def _corpo(usuario_id, instrumento_id, operacao="consultar", valores=None):
    return {
        "usuario_id": str(usuario_id),
        "instrumento_id": str(instrumento_id),
        "operacao": operacao,
        "valores": valores or {},
    }


def _conector(cliente, entrar, dados):
    """Um conector de verdade, criado pela rota normal (sem segredo: o teste não
    depende do cofre)."""
    entrar(dados["operador"])
    r = cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={
            "nome": "Conector interno",
            "tipo": "conector",
            "configuracao": {
                "auth_tipo": "nenhuma",
                "operacoes": [{
                    "nome": "consultar", "metodo": "GET",
                    "url": "https://exemplo.invalido/x", "campos": [],
                }],
            },
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


# ── 1. Sem a variável, a porta não existe ────────────────────────────────────


def test_sem_variavel_a_porta_nao_existe(cliente, entrar, dados, monkeypatch):
    """Nada fica aberto por omissão. E responde 404, não 403: um ambiente que não usa
    esta ponte nem anuncia que ela poderia existir."""
    monkeypatch.delenv("BATUTA_INTERNO_SECRET", raising=False)
    cid = _conector(cliente, entrar, dados)
    r = cliente.post(
        CAMINHO,
        json=_corpo(dados["operador"].id, cid),
        headers={"X-Batuta-Interno": "qualquer"},
    )
    assert r.status_code == 404


# ── 2. O segredo prova QUEM CHAMA; quem AUTORIZA é o papel ───────────────────


def test_sem_cabecalho_recusa(cliente, entrar, dados, ligada):
    cid = _conector(cliente, entrar, dados)
    r = cliente.post(CAMINHO, json=_corpo(dados["operador"].id, cid))
    assert r.status_code == 403


def test_segredo_errado_recusa(cliente, entrar, dados, ligada):
    cid = _conector(cliente, entrar, dados)
    r = cliente.post(
        CAMINHO,
        json=_corpo(dados["operador"].id, cid),
        headers={"X-Batuta-Interno": "quase-certo"},
    )
    assert r.status_code == 403


def test_segredo_certo_NAO_burla_o_papel(cliente, entrar, dados, ligada):
    """O ponto central. Com o segredo interno na mão, um pedido em nome de quem NÃO
    pode operar aquele instrumento continua sendo recusado — os guardas de sempre
    valem. Se este teste cair, a porta virou um atalho de permissão."""
    cid = _conector(cliente, entrar, dados)
    r = cliente.post(
        CAMINHO,
        json=_corpo(dados["observador"].id, cid),
        headers={"X-Batuta-Interno": "segredo-interno-de-teste"},
    )
    assert r.status_code == 403, r.text


def test_usuario_de_fora_nao_alcanca_o_instrumento(cliente, entrar, dados, ligada):
    """Usuário real, mas de outra organização: o guarda de acesso barra igual."""
    cid = _conector(cliente, entrar, dados)
    r = cliente.post(
        CAMINHO,
        json=_corpo(dados["estranho"].id, cid),
        headers={"X-Batuta-Interno": "segredo-interno-de-teste"},
    )
    assert r.status_code in (403, 404), r.text


def test_usuario_inexistente(cliente, entrar, dados, ligada):
    cid = _conector(cliente, entrar, dados)
    r = cliente.post(
        CAMINHO,
        json=_corpo(uuid.uuid4(), cid),
        headers={"X-Batuta-Interno": "segredo-interno-de-teste"},
    )
    assert r.status_code == 404


# ── 3. Escopo mínimo ─────────────────────────────────────────────────────────


def test_so_conector(cliente, entrar, dados, ligada):
    """Não é proxy genérico: só conector tem operações para testar."""
    entrar(dados["operador"])
    r = cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={"nome": "Não é conector", "tipo": "busca_web", "configuracao": {}},
    )
    iid = r.json()["id"]
    r2 = cliente.post(
        CAMINHO,
        json=_corpo(dados["operador"].id, iid),
        headers={"X-Batuta-Interno": "segredo-interno-de-teste"},
    )
    assert r2.status_code == 422


def test_operacao_inexistente_volta_erro_claro(cliente, entrar, dados, ligada):
    cid = _conector(cliente, entrar, dados)
    r = cliente.post(
        CAMINHO,
        json=_corpo(dados["operador"].id, cid, operacao="nao-existe"),
        headers={"X-Batuta-Interno": "segredo-interno-de-teste"},
    )
    assert r.status_code == 422
    assert "nao-existe" in r.text


def test_caminho_feliz_devolve_o_resultado_e_nenhum_segredo(
    cliente, entrar, dados, ligada, monkeypatch
):
    """Roda a operação e devolve o MESMO formato da tela — e nada além dele."""
    import instrumentos.conector as mod

    monkeypatch.setattr(
        mod,
        "_executar_operacao",
        lambda *a, **k: {"ok": True, "status": 200, "corpo": {"rows": [{"a": 1}]}},
    )
    cid = _conector(cliente, entrar, dados)
    r = cliente.post(
        CAMINHO,
        json=_corpo(dados["operador"].id, cid),
        headers={"X-Batuta-Interno": "segredo-interno-de-teste"},
    )
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["ok"] is True
    assert corpo["corpo"] == {"rows": [{"a": 1}]}
    assert "campos_detectados" in corpo
    # nada de configuração nem de segredo atravessa
    texto = r.text
    assert "auth_segredo" not in texto and "auth_tipo" not in texto
