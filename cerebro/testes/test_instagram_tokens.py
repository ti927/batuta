"""Testes da fundação do Instagram (Fase 0): módulo de tokens + gravação da
credencial `instagram` no cofre + a rota traduzindo token recusado em 422.

Nenhuma chamada de rede real: o `httpx` de `instagram_tokens` é interceptado, e
nos testes de cofre/rota o `instagram_tokens.validar` é trocado por um dublê.
"""

from datetime import datetime, timedelta, timezone

import pytest

import credenciais_cofre as cc
import instagram_tokens as it
from instrumentos.base import FalhaInstrumento
from modelos import Credencial


# ───────────────────────── dublê de httpx ─────────────────────────


def _mock_get(monkeypatch, *, status, corpo=None, texto=None, erro=False):
    """Intercepta o GET de `instagram_tokens` e captura os params enviados."""
    capturado: dict = {}

    class _Resp:
        status_code = status
        is_success = 200 <= status < 300

        def json(self):
            if corpo is None:
                raise ValueError("sem json")
            return corpo

        @property
        def text(self):
            return texto or ""

    class _Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            if erro:
                raise it.httpx.HTTPError("rede caiu")
            capturado["url"] = url
            capturado["params"] = params or {}
            return _Resp()

    monkeypatch.setattr("instagram_tokens.httpx.Client", _Cliente)
    return capturado


# ───────────────────────── validar ─────────────────────────


def test_validar_devolve_ig_user_id_e_username(monkeypatch):
    cap = _mock_get(monkeypatch, status=200, corpo={"user_id": "178414", "username": "batuta"})
    assert it.validar("TOKEN") == {"ig_user_id": "178414", "username": "batuta"}
    assert cap["url"].endswith("/me")
    assert cap["params"]["access_token"] == "TOKEN"
    assert cap["params"]["fields"] == "user_id,username"


def test_validar_token_recusado_nao_retentavel(monkeypatch):
    _mock_get(monkeypatch, status=400, corpo={"error": {"message": "Invalid OAuth token"}})
    with pytest.raises(FalhaInstrumento) as exc:
        it.validar("RUIM")
    assert exc.value.retentavel is False
    assert "Invalid OAuth token" in str(exc.value)


def test_validar_rede_oscilando_retentavel(monkeypatch):
    _mock_get(monkeypatch, status=200, erro=True)
    with pytest.raises(FalhaInstrumento) as exc:
        it.validar("TOKEN")
    assert exc.value.retentavel is True


# ───────────────────────── renovar ─────────────────────────


def test_renovar_devolve_token_novo_e_expira_em(monkeypatch):
    _mock_get(
        monkeypatch, status=200,
        corpo={"access_token": "NOVO", "token_type": "bearer", "expires_in": 5_000_000},
    )
    res = it.renovar("VELHO")
    assert res["token"] == "NOVO"
    # expira_em ~ agora + 5_000_000s (no futuro, dentro da janela esperada)
    assert res["expira_em"] > datetime.now(timezone.utc) + timedelta(days=50)


def test_renovar_sem_token_na_resposta_falha(monkeypatch):
    _mock_get(monkeypatch, status=200, corpo={"token_type": "bearer"})
    with pytest.raises(FalhaInstrumento):
        it.renovar("VELHO")


def test_renovar_servidor_caido_retentavel(monkeypatch):
    _mock_get(monkeypatch, status=503, texto="upstream down")
    with pytest.raises(FalhaInstrumento) as exc:
        it.renovar("VELHO")
    assert exc.value.retentavel is True


# ─────────────── cofre: gravar_com_validacao_ig ───────────────


def test_gravar_ig_valida_preenche_id_e_fixa_expira_em(monkeypatch):
    monkeypatch.setattr(
        "instagram_tokens.validar",
        lambda token: {"ig_user_id": "999000", "username": "u"},
    )
    cred = Credencial(organizacao_id=None, nome="IG", tipo="instagram")
    cc.gravar_com_validacao_ig(cred, {"token": "IGAAlongtoken9999"})
    saco = cc.decifrar(cred)
    assert saco["ig_user_id"] == "999000"  # derivado, não colado
    assert saco["token"] == "IGAAlongtoken9999"
    assert cred.expira_em > datetime.now(timezone.utc) + timedelta(days=59)
    assert cred.resumo["token"]["ultimos4"] == "9999"  # segredo mascarado
    assert cred.resumo["ig_user_id"] == {"secreto": False, "valor": "999000"}


def test_gravar_ig_id_colado_e_ignorado(monkeypatch):
    monkeypatch.setattr(
        "instagram_tokens.validar",
        lambda token: {"ig_user_id": "DERIVADO", "username": "u"},
    )
    cred = Credencial(organizacao_id=None, nome="IG", tipo="instagram")
    cc.gravar_com_validacao_ig(cred, {"token": "tok12345", "ig_user_id": "CHUTE"})
    assert cc.decifrar(cred)["ig_user_id"] == "DERIVADO"


def test_gravar_ig_edicao_sem_recolar_preserva_e_nao_valida(monkeypatch):
    monkeypatch.setattr(
        "instagram_tokens.validar",
        lambda token: {"ig_user_id": "111", "username": "u"},
    )
    cred = Credencial(organizacao_id=None, nome="IG", tipo="instagram")
    cc.gravar_com_validacao_ig(cred, {"token": "tokABCD"})
    expira_inicial = cred.expira_em
    # Edição sem recolar o token: NÃO pode chamar validar nem mexer em expira_em.
    def _boom(token):
        raise AssertionError("validar não deve ser chamado sem token novo")

    monkeypatch.setattr("instagram_tokens.validar", _boom)
    cc.gravar_com_validacao_ig(cred, {"token": ""})
    assert cc.decifrar(cred)["token"] == "tokABCD"  # preservado
    assert cred.expira_em == expira_inicial


def test_gravar_validacao_ig_nao_toca_outros_tipos(monkeypatch):
    # Para tipos != instagram, é o gravar normal: não chama validar (sem rede).
    def _boom(token):
        raise AssertionError("validar não deve ser chamado para tipo != instagram")

    monkeypatch.setattr("instagram_tokens.validar", _boom)
    cred = Credencial(organizacao_id=None, nome="TG", tipo="telegram_bot")
    cc.gravar_com_validacao_ig(cred, {"token_bot": "bot12345"})
    assert cc.decifrar(cred) == {"token_bot": "bot12345"}


# ─────────────── cofre: gravar_token_renovado (escrita pelo sistema) ───────────────


def test_gravar_token_renovado_troca_token_e_preserva_id(monkeypatch):
    monkeypatch.setattr(
        "instagram_tokens.validar",
        lambda token: {"ig_user_id": "555", "username": "u"},
    )
    cred = Credencial(organizacao_id=None, nome="IG", tipo="instagram")
    cc.gravar_com_validacao_ig(cred, {"token": "tokANTIGO1"})
    nova_data = datetime.now(timezone.utc) + timedelta(days=60)
    cc.gravar_token_renovado(cred, "tokNOVO2", nova_data)
    saco = cc.decifrar(cred)
    assert saco["token"] == "tokNOVO2"
    assert saco["ig_user_id"] == "555"  # preservado
    assert cred.expira_em == nova_data


# ─────────────── rota: criar credencial instagram + 422 ───────────────


def test_rota_cria_credencial_instagram_e_mascara(cliente, entrar, dados, monkeypatch):
    monkeypatch.setattr(
        "instagram_tokens.validar",
        lambda token: {"ig_user_id": "178414", "username": "batuta"},
    )
    entrar(dados["operador"])
    org = dados["orgA"].id
    r = cliente.post(
        f"/organizacoes/{org}/credenciais",
        json={"nome": "IG Loja", "tipo": "instagram",
              "dados": {"token": "IGAAtokenlongo9999"}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["resumo"]["ig_user_id"] == {"secreto": False, "valor": "178414"}
    assert body["resumo"]["token"]["ultimos4"] == "9999"
    assert "IGAAtokenlongo9999" not in r.text  # token pleno nunca volta


def test_rota_token_recusado_vira_422(cliente, entrar, dados, monkeypatch):
    def _recusa(token):
        raise FalhaInstrumento("o Instagram recusou o token (HTTP 400).", retentavel=False)

    monkeypatch.setattr("instagram_tokens.validar", _recusa)
    entrar(dados["operador"])
    org = dados["orgA"].id
    r = cliente.post(
        f"/organizacoes/{org}/credenciais",
        json={"nome": "IG Ruim", "tipo": "instagram", "dados": {"token": "ruim"}},
    )
    assert r.status_code == 422, r.text
    assert "Instagram" in r.json()["detail"]
