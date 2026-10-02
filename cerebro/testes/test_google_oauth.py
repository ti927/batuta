"""Testes do OAuth 'Conectar Google': módulo de troca/renovação de token, o refresh
sob demanda (`garantir_token`). As rotas iniciar/callback saíram em 2026-10-02
(a página de chaves ficou só com as chaves de IA).

Nenhuma rede real: o `httpx` de `google_oauth` é interceptado e, nos testes de rota,
o próprio `google_oauth.conectar` é trocado por um dublê. O `state` é gerado pelo
cofre real (COFRE_CHAVE_MESTRA vem do .env, como nos demais testes)."""

from datetime import datetime, timedelta, timezone

import pytest

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
    """2026-09-22: `gmail.readonly` saiu daqui. Ele é RESTRITO (auditoria CASA, anual e
    paga) e nenhum instrumento o usava — e derrubava a verificação do app inteiro.
    Enviar e-mail (`gmail.send`) continua."""
    escopos = go.escopos_padrao()
    assert "https://www.googleapis.com/auth/webmasters.readonly" in escopos
    assert "https://www.googleapis.com/auth/gmail.send" in escopos
    assert "https://www.googleapis.com/auth/calendar.events" in escopos
    assert "https://www.googleapis.com/auth/drive.file" in escopos
    # os restritos NÃO entram — preferimos os estreitos
    assert "https://www.googleapis.com/auth/drive" not in escopos
    assert "https://www.googleapis.com/auth/gmail.readonly" not in escopos


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


def _espiar_eventos(monkeypatch) -> list[dict]:
    """Captura o que iria para o banco de logs, sem tocar no banco."""
    vistos: list[dict] = []
    monkeypatch.setattr(
        "observabilidade.escritor.registrar_evento",
        lambda **kw: vistos.append(kw),
    )
    return vistos


def test_renovacao_que_falha_NAO_e_muda(monkeypatch):
    """A regressão de 2026-09-21: a renovação quebrou em 20/07 e o `except` devolveu o
    token vencido CALADO. Resultado: 26 execuções verdes, dois meses sem ninguém saber.
    Agora toda falha de renovação deixa evento `error` no banco de logs, com a conta e
    o que fazer."""
    monkeypatch.setattr(
        "google_oauth.renovar",
        lambda r: (_ for _ in ()).throw(
            FalhaInstrumento("invalid_grant: Token has been expired or revoked.")
        ),
    )
    monkeypatch.setattr("google_oauth._persistir_token", lambda *a, **k: None)
    eventos = _espiar_eventos(monkeypatch)

    cred = _cred_google(access="VELHO", expira=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert go.garantir_token(cred) == "VELHO"  # segue sem derrubar o cinto…

    assert len(eventos) == 1, "a falha de renovação voltou a ser muda"
    ev = eventos[0]
    assert ev["nivel"] == "error"
    assert ev["acao"] == "google.renovacao_falhou"
    assert "invalid_grant" in str(ev["erro"])
    # o recado tem que dizer O QUE FAZER, não só que quebrou
    assert "Chaves" in ev["detalhe"]["o_que_fazer"]
    assert ev["detalhe"]["conta"] == "Google: dono@empresa.com"


def test_sem_refresh_token_tambem_avisa(monkeypatch):
    """Credencial sem token de renovação nunca mais volta sozinha — e antes saía
    calada pelo mesmo caminho."""
    eventos = _espiar_eventos(monkeypatch)
    cred = _cred_google(access="VELHO", refresh="", expira=None)
    go.garantir_token(cred)
    assert [e["acao"] for e in eventos] == ["google.renovacao_falhou"]


def test_token_com_folga_nao_alarma(monkeypatch):
    """O alarme só vale se ficar quieto quando está tudo bem."""
    eventos = _espiar_eventos(monkeypatch)
    cred = _cred_google(expira=datetime.now(timezone.utc) + timedelta(hours=1))
    assert go.garantir_token(cred) == "ACCESS_ATUAL"
    assert eventos == []


# ── Nenhum escopo RESTRITO (2026-09-22) ────────────────────────────────────────
# Escopo restrito exige auditoria de segurança externa (CASA), anual e paga. Dois
# deles eram pedidos por antecipação — `gmail.readonly` e `drive.readonly` — sem
# nenhum instrumento usá-los, e faziam o Google mostrar "app não verificado" e
# reaplicar o limite de 100 usuários, travando junto o que JÁ estava aprovado.


def test_nenhum_escopo_restrito_e_pedido():
    """Se este teste cair, alguém readicionou um escopo restrito — e a conexão de
    TODA organização vai quebrar com um sintoma que não diz a causa."""
    pedidos = set(go.escopos_padrao())
    proibidos = pedidos & set(go.ESCOPOS_RESTRITOS)
    assert not proibidos, (
        f"escopo restrito pedido: {proibidos}. Ele exige auditoria CASA (anual, paga) "
        "e derruba a verificação do app inteiro."
    )


def test_o_que_sobrou_cobre_o_uso_real():
    pedidos = set(go.escopos_padrao())
    assert "https://www.googleapis.com/auth/webmasters.readonly" in pedidos
    assert "https://www.googleapis.com/auth/calendar.events" in pedidos
    assert "https://www.googleapis.com/auth/gmail.send" in pedidos
    assert "https://www.googleapis.com/auth/drive.file" in pedidos


def test_escopos_por_servico_pede_so_o_escolhido():
    """Pedir tudo de uma vez é o que faz a pessoa ver 'ler suas mensagens de e-mail'
    quando ela só queria o Search Console."""
    so_sc = go.escopos_dos_servicos(["search_console"])
    assert "https://www.googleapis.com/auth/webmasters.readonly" in so_sc
    assert not any("gmail" in e or "drive" in e for e in so_sc)
    # a identidade vem sempre (é como se descobre a conta conectada)
    assert "openid" in so_sc
