"""Testes da camada de acesso (Fase 6): autenticação, matriz de papéis e
isolamento entre organizações. Exercitam endpoints representativos — o
enforcement é centralizado em auth.exigir_papel + os helpers *_acessivel, então
cobrir os representantes valida o mecanismo inteiro."""

import uuid

import auth

AGENTE = {
    "nome": "Ag",
    "papel": "agente",
    "agent_md": None,
    "skill_md": None,
    "tools_md": None,
    "soul_md": None,
    "modelo_ia": None,
}
TIME = {"nome": "T", "descricao": None}


# ── Autenticação ──────────────────────────────────────────────────


def test_sem_token_401(cliente):
    # `cliente` não sobrepõe usuario_atual: a dependência real exige o Bearer.
    assert cliente.get("/organizacoes").status_code == 401


def test_token_de_usuario_sem_cadastro_403(cliente, monkeypatch):
    monkeypatch.setattr(auth, "validar_token", lambda t: {"sub": str(uuid.uuid4())})
    r = cliente.get("/organizacoes", headers={"Authorization": "Bearer qualquer"})
    assert r.status_code == 403


# ── Matriz de papéis ──────────────────────────────────────────────


def test_observador_le_mas_nao_edita_org(cliente, entrar, dados):
    entrar(dados["observador"])
    org = dados["orgA"].id
    assert cliente.get(f"/organizacoes/{org}").status_code == 200
    assert cliente.put(f"/organizacoes/{org}", json={"nome": "X"}).status_code == 403
    assert cliente.delete(f"/organizacoes/{org}").status_code == 403


def test_criar_time_exige_admin(cliente, entrar, dados):
    org = dados["orgA"].id
    entrar(dados["observador"])
    assert cliente.post(f"/organizacoes/{org}/times", json=TIME).status_code == 403
    entrar(dados["operador"])
    assert cliente.post(f"/organizacoes/{org}/times", json=TIME).status_code == 403
    entrar(dados["admin"])
    assert cliente.post(f"/organizacoes/{org}/times", json=TIME).status_code == 201


def test_operador_edita_time_so_admin_apaga(cliente, entrar, dados):
    t = dados["timeA"].id
    entrar(dados["observador"])
    assert cliente.put(f"/times/{t}", json=TIME).status_code == 403
    entrar(dados["operador"])
    assert cliente.put(f"/times/{t}", json=TIME).status_code == 200
    assert cliente.delete(f"/times/{t}").status_code == 403  # operador não apaga
    entrar(dados["admin"])
    assert cliente.delete(f"/times/{t}").status_code == 204


def test_operador_cria_agente_observador_nao(cliente, entrar, dados):
    t = dados["timeA"].id
    entrar(dados["observador"])
    assert cliente.post(f"/times/{t}/agentes", json=AGENTE).status_code == 403
    entrar(dados["operador"])
    assert cliente.post(f"/times/{t}/agentes", json=AGENTE).status_code == 201


# ── Isolamento entre organizações ─────────────────────────────────


def test_isolamento_404(cliente, entrar, dados):
    entrar(dados["estranho"])  # membro só da Org B
    assert cliente.get(f"/organizacoes/{dados['orgA'].id}").status_code == 404
    assert cliente.get(f"/times/{dados['timeA'].id}").status_code == 404


def test_listar_organizacoes_filtra_por_membresia(cliente, entrar, dados):
    entrar(dados["observador"])
    r = cliente.get("/organizacoes")
    assert r.status_code == 200
    ids = {o["id"] for o in r.json()}
    assert str(dados["orgA"].id) in ids
    assert str(dados["orgB"].id) not in ids
