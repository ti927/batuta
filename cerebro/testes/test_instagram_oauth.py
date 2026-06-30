"""Testes do OAuth 'Conectar Instagram' (Business Login): módulo de troca de
token + as rotas iniciar/callback.

Nenhuma rede real: o `httpx` de `instagram_oauth` é interceptado e, nos testes de
rota, o próprio `instagram_oauth.conectar` é trocado por um dublê. O `state` é
gerado pelo cofre real (a COFRE_CHAVE_MESTRA vem do .env, como nos demais testes).
"""

import json

import pytest
from sqlalchemy import select

import cofre
import credenciais_cofre as cc
import instagram_oauth as io
from instrumentos.base import FalhaInstrumento
from modelos import Credencial


@pytest.fixture(autouse=True)
def _config_ig(monkeypatch):
    """Config do app da Meta presente em todos os testes (a menos que removida)."""
    monkeypatch.setenv("INSTAGRAM_APP_ID", "TESTID")
    monkeypatch.setenv("INSTAGRAM_APP_SECRET", "TESTSECRET")
    monkeypatch.setenv(
        "INSTAGRAM_REDIRECT_URI", "https://api.test/instagram/oauth/callback"
    )


# ───────────────────────── módulo: montar_url / configurado ─────────────────


def test_url_autorizacao_carrega_params_e_escopos():
    url = io.montar_url_autorizacao("OSTATE")
    assert url.startswith("https://www.instagram.com/oauth/authorize?")
    assert "client_id=TESTID" in url
    assert "response_type=code" in url
    assert "force_reauth=true" in url  # força escolher a conta (não reusa a sessão)
    assert "state=OSTATE" in url
    # os 4 escopos (sem DM), separados por vírgula (codificada %2C)
    assert "instagram_business_basic" in url
    assert "instagram_business_content_publish" in url
    assert "instagram_business_manage_comments" in url
    assert "instagram_business_manage_insights" in url
    assert "instagram_business_manage_messages" not in url  # DM fora


def test_configurado_reflete_ambiente(monkeypatch):
    assert io.configurado() is True
    monkeypatch.delenv("INSTAGRAM_APP_SECRET")
    assert io.configurado() is False


# ───────────────────────── módulo: conectar ─────────────────────────────────


def _mock_trocas(monkeypatch, *, post_status=200, get_status=200, post_corpo=None,
                 get_corpo=None):
    """Intercepta o POST (token curto) e o GET (token longo) de instagram_oauth."""
    cap: dict = {}

    class _Resp:
        def __init__(self, status, corpo):
            self.status_code = status
            self.is_success = 200 <= status < 300
            self._corpo = corpo

        def json(self):
            return self._corpo

        @property
        def text(self):
            return ""

    class _Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data=None):
            cap["post"] = {"url": url, "data": data or {}}
            return _Resp(
                post_status,
                post_corpo
                if post_corpo is not None
                else {"access_token": "CURTO1H", "user_id": "178414"},
            )

        def get(self, url, params=None):
            cap["get"] = {"url": url, "params": params or {}}
            return _Resp(
                get_status,
                get_corpo
                if get_corpo is not None
                else {
                    "access_token": "LONGO60DIAS9999",
                    "token_type": "bearer",
                    "expires_in": 5_000_000,
                },
            )

    monkeypatch.setattr("instagram_oauth.httpx.Client", _Cliente)
    return cap


def test_conectar_troca_code_por_token_longo(monkeypatch):
    cap = _mock_trocas(monkeypatch)
    monkeypatch.setattr(
        "instagram_tokens.validar",
        lambda token: {"ig_user_id": "178414", "username": "batuta"},
    )
    conta = io.conectar("OCODE")
    assert conta["token"] == "LONGO60DIAS9999"
    assert conta["ig_user_id"] == "178414"
    assert conta["username"] == "batuta"
    # o code e o client_secret foram ao POST do token curto
    assert cap["post"]["data"]["code"] == "OCODE"
    assert cap["post"]["data"]["grant_type"] == "authorization_code"
    assert cap["post"]["data"]["client_secret"] == "TESTSECRET"
    # a troca longa usa ig_exchange_token + o token curto
    assert cap["get"]["params"]["grant_type"] == "ig_exchange_token"
    assert cap["get"]["params"]["access_token"] == "CURTO1H"


def test_conectar_code_recusado_e_nao_retentavel(monkeypatch):
    _mock_trocas(monkeypatch, post_status=400,
                 post_corpo={"error": {"message": "invalid code"}})
    with pytest.raises(FalhaInstrumento) as exc:
        io.conectar("RUIM")
    assert exc.value.retentavel is False


def test_conectar_sem_token_curto_falha(monkeypatch):
    _mock_trocas(monkeypatch, post_corpo={"erro": "sem token"})
    with pytest.raises(FalhaInstrumento):
        io.conectar("OCODE")


# ───────────────────────── rota: iniciar ────────────────────────────────────


def test_iniciar_operador_recebe_url(cliente, entrar, dados):
    entrar(dados["operador"])
    org = dados["orgA"].id
    r = cliente.post(f"/organizacoes/{org}/instagram/iniciar")
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert "instagram.com/oauth/authorize" in url
    assert "state=" in url


def test_iniciar_observador_negado(cliente, entrar, dados):
    entrar(dados["observador"])
    org = dados["orgA"].id
    r = cliente.post(f"/organizacoes/{org}/instagram/iniciar")
    assert r.status_code == 403, r.text


def test_iniciar_estranho_nao_ve_org(cliente, entrar, dados):
    entrar(dados["estranho"])  # admin da org B, não membro da A
    org = dados["orgA"].id
    r = cliente.post(f"/organizacoes/{org}/instagram/iniciar")
    assert r.status_code == 404, r.text


def test_iniciar_sem_config_responde_503(cliente, entrar, dados, monkeypatch):
    monkeypatch.delenv("INSTAGRAM_APP_ID")
    entrar(dados["operador"])
    org = dados["orgA"].id
    r = cliente.post(f"/organizacoes/{org}/instagram/iniciar")
    assert r.status_code == 503, r.text


# ───────────────────────── rota: callback ───────────────────────────────────


def _state(org_id, usuario_id) -> str:
    return cofre.cifrar(json.dumps({"org": str(org_id), "usuario": str(usuario_id)}))


def _mock_conectar(monkeypatch, *, token="IGLONGO9999", ig="178414",
                   username="batuta"):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(
        "instagram_oauth.conectar",
        lambda code: {
            "token": token,
            "ig_user_id": ig,
            "username": username,
            "expira_em": datetime.now(timezone.utc) + timedelta(days=60),
        },
    )


def _instagram_da_org(sessao, org_id):
    return list(
        sessao.scalars(
            select(Credencial).where(
                Credencial.organizacao_id == org_id,
                Credencial.tipo == "instagram",
            )
        ).all()
    )


def test_callback_cria_credencial_e_redireciona(cliente, dados, sessao, monkeypatch):
    _mock_conectar(monkeypatch)
    org = dados["orgA"].id
    state = _state(org, dados["operador"].id)
    r = cliente.get(
        "/instagram/oauth/callback",
        params={"code": "OCODE", "state": state},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    destino = r.headers["location"]
    assert f"/organizacoes/{org}/chaves" in destino
    assert "instagram=ok" in destino

    creds = _instagram_da_org(sessao, org)
    assert len(creds) == 1
    c = creds[0]
    assert c.nome == "Instagram: @batuta"
    assert c.resumo["ig_user_id"] == {"secreto": False, "valor": "178414"}
    assert c.resumo["token"]["ultimos4"] == "9999"
    assert "IGLONGO9999" not in r.text  # token pleno nunca aparece


def test_callback_reconexao_mesma_conta_nao_duplica(cliente, dados, sessao, monkeypatch):
    org = dados["orgA"].id
    state = _state(org, dados["operador"].id)
    _mock_conectar(monkeypatch, token="TOKEN_ANTIGO1111")
    cliente.get("/instagram/oauth/callback",
                params={"code": "C1", "state": state}, follow_redirects=False)
    # reconecta a MESMA conta (mesmo ig_user_id), token novo
    _mock_conectar(monkeypatch, token="TOKEN_NOVO2222")
    cliente.get("/instagram/oauth/callback",
                params={"code": "C2", "state": _state(org, dados["operador"].id)},
                follow_redirects=False)
    creds = _instagram_da_org(sessao, org)
    assert len(creds) == 1  # atualizou, não duplicou
    assert cc.decifrar(creds[0])["token"] == "TOKEN_NOVO2222"


def test_callback_state_invalido_da_400(cliente, dados, monkeypatch):
    _mock_conectar(monkeypatch)
    r = cliente.get(
        "/instagram/oauth/callback",
        params={"code": "OCODE", "state": "lixo-nao-cifrado"},
        follow_redirects=False,
    )
    assert r.status_code == 400, r.text


def test_callback_usuario_sem_permissao_redireciona_erro(cliente, dados, monkeypatch):
    _mock_conectar(monkeypatch)
    org = dados["orgA"].id
    state = _state(org, dados["observador"].id)  # observador não pode conectar
    r = cliente.get(
        "/instagram/oauth/callback",
        params={"code": "OCODE", "state": state},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "instagram=erro" in r.headers["location"]


def test_callback_erro_da_meta_redireciona_com_motivo(cliente, dados, monkeypatch):
    org = dados["orgA"].id
    state = _state(org, dados["operador"].id)
    r = cliente.get(
        "/instagram/oauth/callback",
        params={
            "state": state,
            "error": "access_denied",
            "error_description": "usuário recusou",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "instagram=erro" in r.headers["location"]
