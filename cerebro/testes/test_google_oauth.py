"""Testes do OAuth 'Conectar Google': módulo de troca/renovação de token, o refresh
sob demanda (`garantir_token`) e as rotas iniciar/callback.

Nenhuma rede real: o `httpx` de `google_oauth` é interceptado e, nos testes de rota,
o próprio `google_oauth.conectar` é trocado por um dublê. O `state` é gerado pelo
cofre real (COFRE_CHAVE_MESTRA vem do .env, como nos demais testes)."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

import cofre
import credenciais_cofre as cc
import google_oauth as go
from instrumentos.base import FalhaInstrumento
from modelos import Credencial


@pytest.fixture(autouse=True)
def _config_google(monkeypatch):
    """Config do app do Google presente em todos os testes (a menos que removida)."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "TESTID")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "TESTSECRET")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://api.test/google/oauth/callback")


# ───────────────────────── módulo: montar_url / escopos / configurado ────────


def test_url_autorizacao_carrega_params_e_escopos():
    url = go.montar_url_autorizacao("OSTATE")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=TESTID" in url
    assert "response_type=code" in url
    # offline + consent garantem o refresh_token
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "state=OSTATE" in url


def test_escopos_padrao_cobre_os_servicos_do_lote():
    escopos = go.escopos_padrao()
    assert "https://www.googleapis.com/auth/webmasters.readonly" in escopos
    assert "https://www.googleapis.com/auth/gmail.readonly" in escopos
    assert "https://www.googleapis.com/auth/gmail.send" in escopos
    assert "https://www.googleapis.com/auth/calendar.events" in escopos
    assert "https://www.googleapis.com/auth/drive.file" in escopos
    # escopo restrito (drive full) NÃO entra — preferimos os estreitos
    assert "https://www.googleapis.com/auth/drive" not in escopos


def test_configurado_reflete_ambiente(monkeypatch):
    assert go.configurado() is True
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET")
    assert go.configurado() is False


# ───────────────────────── módulo: conectar / renovar ───────────────────────


def _mock_httpx(monkeypatch, *, token_status=200, token_corpo=None, userinfo_corpo=None):
    """Intercepta os POST (/token) e GET (/userinfo) de google_oauth."""
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
            cap.setdefault("posts", []).append({"url": url, "data": data or {}})
            corpo = token_corpo
            if corpo is None:
                if (data or {}).get("grant_type") == "refresh_token":
                    corpo = {"access_token": "NOVO_ACCESS", "expires_in": 3600}
                else:
                    corpo = {
                        "access_token": "ACCESS1H",
                        "refresh_token": "REFRESH_DURAVEL",
                        "expires_in": 3600,
                        "scope": "openid email",
                    }
            return _Resp(token_status, corpo)

        def get(self, url, headers=None):
            cap.setdefault("gets", []).append({"url": url, "headers": headers or {}})
            return _Resp(
                200, userinfo_corpo if userinfo_corpo is not None else {"email": "dono@empresa.com"}
            )

    monkeypatch.setattr("google_oauth.httpx.Client", _Cliente)
    return cap


def test_conectar_troca_code_por_tokens_e_email(monkeypatch):
    cap = _mock_httpx(monkeypatch)
    conta = go.conectar("OCODE")
    assert conta["access_token"] == "ACCESS1H"
    assert conta["refresh_token"] == "REFRESH_DURAVEL"
    assert conta["email"] == "dono@empresa.com"
    assert isinstance(conta["expira_em"], datetime)
    # o code + client_secret foram ao POST do token
    assert cap["posts"][0]["data"]["code"] == "OCODE"
    assert cap["posts"][0]["data"]["grant_type"] == "authorization_code"
    assert cap["posts"][0]["data"]["client_secret"] == "TESTSECRET"


def test_conectar_sem_refresh_token_falha(monkeypatch):
    _mock_httpx(monkeypatch, token_corpo={"access_token": "SO_ACCESS", "expires_in": 3600})
    with pytest.raises(FalhaInstrumento) as exc:
        go.conectar("OCODE")
    assert exc.value.retentavel is False


def test_conectar_code_recusado_e_nao_retentavel(monkeypatch):
    _mock_httpx(
        monkeypatch, token_status=400, token_corpo={"error": "invalid_grant"}
    )
    with pytest.raises(FalhaInstrumento) as exc:
        go.conectar("RUIM")
    assert exc.value.retentavel is False


def test_renovar_troca_refresh_por_access_novo(monkeypatch):
    _mock_httpx(monkeypatch)
    res = go.renovar("REFRESH_DURAVEL")
    assert res["access_token"] == "NOVO_ACCESS"
    assert isinstance(res["expira_em"], datetime)


# ───────────────────────── módulo: garantir_token ───────────────────────────


def _cred_google(access="ACCESS_ATUAL", refresh="REFRESH_DURAVEL", expira=None):
    cred = Credencial(nome="Google: dono@empresa.com", tipo="google")
    cc.gravar(cred, {"access_token": access, "refresh_token": refresh, "email": "d@e.com"})
    cred.expira_em = expira
    return cred


def test_garantir_token_valido_nao_renova(monkeypatch):
    """Token com folga → devolve o atual sem chamar renovar."""
    monkeypatch.setattr(
        "google_oauth.renovar",
        lambda r: (_ for _ in ()).throw(AssertionError("não deveria renovar")),
    )
    cred = _cred_google(expira=datetime.now(timezone.utc) + timedelta(hours=1))
    assert go.garantir_token(cred) == "ACCESS_ATUAL"


def test_garantir_token_vencido_renova(monkeypatch):
    """Token vencido → usa o refresh_token e devolve o novo (persistência mockada)."""
    monkeypatch.setattr(
        "google_oauth.renovar",
        lambda r: {"access_token": "ACCESS_FRESCO", "expira_em": datetime.now(timezone.utc) + timedelta(hours=1)},
    )
    monkeypatch.setattr("google_oauth._persistir_token", lambda *a, **k: None)
    cred = _cred_google(expira=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert go.garantir_token(cred) == "ACCESS_FRESCO"


def test_garantir_token_renovacao_falha_devolve_atual(monkeypatch):
    """Se a renovação falhar, devolve o token atual (o instrumento trata o 401)."""
    def _explode(r):
        raise FalhaInstrumento("google fora do ar", retentavel=True)

    monkeypatch.setattr("google_oauth.renovar", _explode)
    monkeypatch.setattr("google_oauth._persistir_token", lambda *a, **k: None)
    cred = _cred_google(access="VELHO", expira=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert go.garantir_token(cred) == "VELHO"


# ───────────────────────── rota: iniciar ────────────────────────────────────


def test_iniciar_operador_recebe_url(cliente, entrar, dados):
    entrar(dados["operador"])
    org = dados["orgA"].id
    r = cliente.post(f"/organizacoes/{org}/google/iniciar")
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert "accounts.google.com/o/oauth2" in url
    assert "state=" in url


def test_iniciar_observador_negado(cliente, entrar, dados):
    entrar(dados["observador"])
    org = dados["orgA"].id
    r = cliente.post(f"/organizacoes/{org}/google/iniciar")
    assert r.status_code == 403, r.text


def test_iniciar_estranho_nao_ve_org(cliente, entrar, dados):
    entrar(dados["estranho"])
    org = dados["orgA"].id
    r = cliente.post(f"/organizacoes/{org}/google/iniciar")
    assert r.status_code == 404, r.text


def test_iniciar_sem_config_responde_503(cliente, entrar, dados, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    entrar(dados["operador"])
    org = dados["orgA"].id
    r = cliente.post(f"/organizacoes/{org}/google/iniciar")
    assert r.status_code == 503, r.text


# ───────────────────────── rota: callback ───────────────────────────────────


def _state(org_id, usuario_id) -> str:
    return cofre.cifrar(json.dumps({"org": str(org_id), "usuario": str(usuario_id)}))


def _mock_conectar(monkeypatch, *, email="dono@empresa.com", access="ACCESS9999",
                   refresh="REFRESH1234"):
    monkeypatch.setattr(
        "google_oauth.conectar",
        lambda code: {
            "access_token": access,
            "refresh_token": refresh,
            "email": email,
            "escopos": "openid email",
            "expira_em": datetime.now(timezone.utc) + timedelta(hours=1),
        },
    )


def _google_da_org(sessao, org_id):
    return list(
        sessao.scalars(
            select(Credencial).where(
                Credencial.organizacao_id == org_id, Credencial.tipo == "google"
            )
        ).all()
    )


def test_callback_cria_credencial_e_redireciona(cliente, dados, sessao, monkeypatch):
    _mock_conectar(monkeypatch)
    org = dados["orgA"].id
    state = _state(org, dados["operador"].id)
    r = cliente.get(
        "/google/oauth/callback",
        params={"code": "OCODE", "state": state},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    destino = r.headers["location"]
    assert f"/organizacoes/{org}/chaves" in destino
    assert "google=ok" in destino

    creds = _google_da_org(sessao, org)
    assert len(creds) == 1
    c = creds[0]
    assert c.nome == "Google: dono@empresa.com"
    assert c.resumo["email"] == {"secreto": False, "valor": "dono@empresa.com"}
    assert c.resumo["access_token"]["ultimos4"] == "9999"
    assert "ACCESS9999" not in r.text  # token pleno nunca aparece


def test_callback_reconexao_mesma_conta_nao_duplica(cliente, dados, sessao, monkeypatch):
    org = dados["orgA"].id
    _mock_conectar(monkeypatch, access="ACCESS_ANTIGO1111", refresh="REFRESH_A")
    cliente.get("/google/oauth/callback",
                params={"code": "C1", "state": _state(org, dados["operador"].id)},
                follow_redirects=False)
    _mock_conectar(monkeypatch, access="ACCESS_NOVO2222", refresh="REFRESH_B")
    cliente.get("/google/oauth/callback",
                params={"code": "C2", "state": _state(org, dados["operador"].id)},
                follow_redirects=False)
    creds = _google_da_org(sessao, org)
    assert len(creds) == 1  # atualizou, não duplicou
    saco = cc.decifrar(creds[0])
    assert saco["access_token"] == "ACCESS_NOVO2222"
    assert saco["refresh_token"] == "REFRESH_B"


def test_callback_state_invalido_da_400(cliente, dados, monkeypatch):
    _mock_conectar(monkeypatch)
    r = cliente.get(
        "/google/oauth/callback",
        params={"code": "OCODE", "state": "lixo-nao-cifrado"},
        follow_redirects=False,
    )
    assert r.status_code == 400, r.text


def test_callback_usuario_sem_permissao_redireciona_erro(cliente, dados, monkeypatch):
    _mock_conectar(monkeypatch)
    org = dados["orgA"].id
    state = _state(org, dados["observador"].id)
    r = cliente.get(
        "/google/oauth/callback",
        params={"code": "OCODE", "state": state},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "google=erro" in r.headers["location"]


def test_callback_erro_do_google_redireciona_com_motivo(cliente, dados, monkeypatch):
    org = dados["orgA"].id
    state = _state(org, dados["operador"].id)
    r = cliente.get(
        "/google/oauth/callback",
        params={"state": state, "error": "access_denied", "error_description": "usuário recusou"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "google=erro" in r.headers["location"]
