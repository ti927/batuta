"""Gestão de acesso (Fase 6, Tarefa 6.7): membros, papéis, aceite de convite.
A criação de convite (que chama o Supabase) é exercitada manualmente; aqui
cobrimos a lógica de papéis, o aceite e as guardas."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import rotas.membros as membros_mod
from modelos import Convite, Membro, Usuario


def test_listar_membros_qualquer_membro(cliente, entrar, dados):
    entrar(dados["observador"])
    r = cliente.get(f"/organizacoes/{dados['orgA'].id}/membros")
    assert r.status_code == 200
    assert len(r.json()) == 3  # admin, operador, observador


def test_listar_membros_isolado_404(cliente, entrar, dados):
    entrar(dados["estranho"])  # membro só da Org B
    assert cliente.get(f"/organizacoes/{dados['orgA'].id}/membros").status_code == 404


def test_admin_altera_papel(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/membros/{dados['observador'].id}/papel",
        json={"papel": "operador"},
    )
    assert r.status_code == 200
    assert r.json()["papel"] == "operador"


def test_nao_admin_nao_altera_papel(cliente, entrar, dados):
    entrar(dados["operador"])
    r = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/membros/{dados['observador'].id}/papel",
        json={"papel": "admin"},
    )
    assert r.status_code == 403


def test_nao_remove_ultimo_admin(cliente, entrar, dados):
    entrar(dados["admin"])  # único admin da Org A
    r = cliente.delete(
        f"/organizacoes/{dados['orgA'].id}/membros/{dados['admin'].id}"
    )
    assert r.status_code == 409


def test_aceitar_convite_cria_usuario_e_membro(cliente, dados, sessao, monkeypatch):
    email = f"novo-{uuid.uuid4().hex[:6]}@x.com"
    sub = uuid.uuid4()
    sessao.add(
        Convite(
            email=email, organizacao_id=dados["orgA"].id, papel="operador",
            status="pendente",
        )
    )
    sessao.flush()
    monkeypatch.setattr(
        membros_mod, "validar_token", lambda t: {"sub": str(sub), "email": email}
    )
    r = cliente.post("/convites/aceitar", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    u = sessao.scalars(select(Usuario).where(Usuario.auth_id == sub)).first()
    assert u is not None and u.ativo
    m = sessao.scalars(
        select(Membro).where(
            Membro.usuario_id == u.id, Membro.organizacao_id == dados["orgA"].id
        )
    ).first()
    assert m is not None and m.papel == "operador"


def test_aceitar_sem_convite_404(cliente, sessao, monkeypatch):
    monkeypatch.setattr(
        membros_mod, "validar_token",
        lambda t: {"sub": str(uuid.uuid4()), "email": "ninguem@x.com"},
    )
    r = cliente.post("/convites/aceitar", headers={"Authorization": "Bearer x"})
    assert r.status_code == 404


def test_eu_retorna_papeis(cliente, entrar, dados):
    entrar(dados["operador"])
    r = cliente.get("/eu")
    assert r.status_code == 200
    assert r.json()["papeis"][str(dados["orgA"].id)] == "operador"


# ── Convites pendentes (banner de aviso na home) ──


def test_convites_pendentes_lista_com_nome_org(cliente, dados, sessao, monkeypatch):
    email = f"pend-{uuid.uuid4().hex[:6]}@x.com"
    sessao.add(
        Convite(
            email=email, organizacao_id=dados["orgA"].id, papel="operador",
            status="pendente",
        )
    )
    sessao.flush()
    monkeypatch.setattr(
        membros_mod, "validar_token",
        lambda t: {"sub": str(uuid.uuid4()), "email": email},
    )
    r = cliente.get("/convites/pendentes", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    corpo = r.json()
    assert len(corpo) == 1
    assert corpo[0]["organizacao_nome"] == "Org A"
    assert corpo[0]["papel"] == "operador"
    assert corpo[0]["organizacao_id"] == str(dados["orgA"].id)


def test_convites_pendentes_isolado_por_email(cliente, dados, monkeypatch):
    # E-mail sem nenhum convite → lista vazia (não vaza convites de outros).
    monkeypatch.setattr(
        membros_mod, "validar_token",
        lambda t: {"sub": str(uuid.uuid4()), "email": "ninguem@x.com"},
    )
    r = cliente.get("/convites/pendentes", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    assert r.json() == []


def test_convites_pendentes_ignora_expirado(cliente, dados, sessao, monkeypatch):
    email = f"exp-{uuid.uuid4().hex[:6]}@x.com"
    sessao.add(
        Convite(
            email=email, organizacao_id=dados["orgA"].id, papel="operador",
            status="pendente",
            expira_em=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    sessao.flush()
    monkeypatch.setattr(
        membros_mod, "validar_token",
        lambda t: {"sub": str(uuid.uuid4()), "email": email},
    )
    r = cliente.get("/convites/pendentes", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    assert r.json() == []  # convite expirado não aparece no banner
