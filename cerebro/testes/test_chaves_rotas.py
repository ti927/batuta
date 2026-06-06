"""Testes dos endpoints do cofre de chaves (Fase 7.4).

Cobrem permissão por papel (admin da org gere a chave da org; só admin da
consultoria gere a chave-mãe), isolamento entre organizações, o valor NUNCA
reexibido, o upsert (troca), e a costura com a resolução da 7.3 (a chave salva
é de fato a que o motor passa a resolver).
"""

import uuid

from sqlalchemy import select

from chaves import resolver_chave
from modelos import ChaveApi


def _payload(valor="sk-ant-teste-1234", **extra):
    return {"valor": valor, **extra}


# ─────────────────────────── Chaves da organização ──────────────────────────


def test_admin_cadastra_chave_da_org(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.put(
        f"/organizacoes/{dados['orgA'].id}/chaves", json=_payload("sk-ant-abcd9999")
    )
    assert r.status_code == 200
    corpo = r.json()
    # O valor NUNCA volta; só os últimos 4 dígitos e os metadados.
    assert "valor" not in corpo and "valor_cifrado" not in corpo
    assert corpo["ultimos4"] == "9999"
    assert corpo["tipo_ia"] == "executora" and corpo["provedor"] == "anthropic"
    assert corpo["ativa"] is True


def test_operador_nao_cadastra_chave(cliente, entrar, dados):
    entrar(dados["operador"])
    r = cliente.put(f"/organizacoes/{dados['orgA'].id}/chaves", json=_payload())
    assert r.status_code == 403


def test_observador_nao_lista_chaves(cliente, entrar, dados):
    entrar(dados["observador"])
    assert cliente.get(f"/organizacoes/{dados['orgA'].id}/chaves").status_code == 403


def test_isolamento_entre_organizacoes(cliente, entrar, dados):
    # 'estranho' é admin só da Org B; não enxerga a Org A (404, não 403).
    entrar(dados["estranho"])
    assert (
        cliente.put(
            f"/organizacoes/{dados['orgA'].id}/chaves", json=_payload()
        ).status_code
        == 404
    )


def test_upsert_troca_a_chave_sem_duplicar(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    url = f"/organizacoes/{dados['orgA'].id}/chaves"
    cliente.put(url, json=_payload("sk-ant-aaaa1111"))
    r2 = cliente.put(url, json=_payload("sk-ant-bbbb2222"))
    assert r2.status_code == 200 and r2.json()["ultimos4"] == "2222"
    linhas = sessao.scalars(
        select(ChaveApi).where(ChaveApi.organizacao_id == dados["orgA"].id)
    ).all()
    assert len(linhas) == 1  # trocou, não duplicou


def test_remover_chave_da_org(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    url = f"/organizacoes/{dados['orgA'].id}/chaves"
    chave_id = cliente.put(url, json=_payload()).json()["id"]
    assert cliente.delete(f"{url}/{chave_id}").status_code == 204
    assert (
        sessao.scalars(
            select(ChaveApi).where(ChaveApi.organizacao_id == dados["orgA"].id)
        ).first()
        is None
    )


def test_provedor_nao_suportado_recusado(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.put(
        f"/organizacoes/{dados['orgA'].id}/chaves",
        json=_payload(provedor="openai"),
    )
    assert r.status_code == 422


def test_chave_salva_e_resolvida_pelo_motor(cliente, entrar, dados, sessao):
    """Liga 7.4 ↔ 7.3: o que o admin cadastra é o que o motor passa a usar."""
    entrar(dados["admin"])
    cliente.put(
        f"/organizacoes/{dados['orgA'].id}/chaves", json=_payload("sk-ant-zzzz0000")
    )
    assert resolver_chave(sessao, dados["orgA"].id) == "sk-ant-zzzz0000"


# ──────────────────────── Chave-mãe da consultoria ──────────────────────────


def test_chave_mae_bloqueada_sem_lista(cliente, entrar, dados, monkeypatch):
    """Fail-closed: sem CONSULTORIA_ADMINS, nem o admin da org acessa a chave-mãe."""
    monkeypatch.setenv("CONSULTORIA_ADMINS", "")
    entrar(dados["admin"])
    assert cliente.get("/chaves-consultoria").status_code == 403
    assert cliente.put("/chaves-consultoria", json=_payload()).status_code == 403


def test_admin_consultoria_gere_chave_mae(cliente, entrar, dados, monkeypatch, sessao):
    monkeypatch.setenv("CONSULTORIA_ADMINS", f"  {dados['admin'].email.upper()} ")
    entrar(dados["admin"])
    r = cliente.put("/chaves-consultoria", json=_payload("sk-ant-mae-5678"))
    assert r.status_code == 200
    assert r.json()["organizacao_id"] is None and r.json()["ultimos4"] == "5678"
    # É a chave-mãe (organizacao_id nulo) e o motor a usa como fallback.
    assert resolver_chave(sessao, uuid.uuid4()) == "sk-ant-mae-5678"


def test_usuario_comum_nao_e_admin_consultoria(cliente, entrar, dados, monkeypatch):
    # A lista tem o e-mail do admin, mas quem chama é o operador → 403.
    monkeypatch.setenv("CONSULTORIA_ADMINS", dados["admin"].email)
    entrar(dados["operador"])
    assert cliente.put("/chaves-consultoria", json=_payload()).status_code == 403


def test_eu_expoe_admin_consultoria(cliente, entrar, dados, monkeypatch):
    """A UI (7.5) usa /eu.admin_consultoria para mostrar o link da chave-mãe."""
    monkeypatch.setenv("CONSULTORIA_ADMINS", dados["admin"].email)
    entrar(dados["admin"])
    assert cliente.get("/eu").json()["admin_consultoria"] is True
    entrar(dados["operador"])
    assert cliente.get("/eu").json()["admin_consultoria"] is False
