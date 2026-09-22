"""Conta de serviço do Google — a autenticação sem consentimento.

Nasceu do incidente de 2026-09-21: a conta conectada por OAuth parou de renovar e o
Search Console ficou dois meses em 401. Publicar o app OAuth do Batuta exigiria
verificação completa com auditoria anual (escopos restritos: Gmail, Drive), e em
*Testing* o token de renovação morre a cada 7 dias. A conta de serviço pula tudo isso.

Nenhuma rede real: a troca da chave assinada por um token é dublada. O que se prova
aqui é o que dói quando falta — recado humano em cada recusa, escopo obrigatório, e a
chave nunca virando chave de cache.
"""

import json

import pytest

import google_conta_servico as gcs
from instrumentos.base import FalhaInstrumento

CHAVE = json.dumps(
    {
        "type": "service_account",
        "client_email": "batuta@projeto.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\nfalsa\n-----END PRIVATE KEY-----\n",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
)
ESCOPO = "https://www.googleapis.com/auth/webmasters.readonly"


@pytest.fixture(autouse=True)
def _cache_limpo():
    gcs._CACHE.clear()
    yield
    gcs._CACHE.clear()


def _dublar(monkeypatch, token="TOKEN_FRESCO", validade_s=3600, contador=None):
    """Troca a assinatura real (RS256 + ida ao Google) por um dublê que devolve token."""
    from datetime import datetime, timedelta

    from google.oauth2 import service_account

    class _Cred:
        def __init__(self, scopes):
            self.token = None
            self.expiry = None
            self.scopes = scopes

        def refresh(self, _req):
            if contador is not None:
                contador.append(self.scopes)
            self.token = f"{token}:{','.join(self.scopes)}"
            # google-auth devolve datetime NAIVE em UTC
            self.expiry = datetime.utcnow() + timedelta(seconds=validade_s)

    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_info",
        staticmethod(lambda info, scopes: _Cred(scopes)),
    )


def test_sem_chave_o_recado_diz_onde_baixar():
    """Quem lê a falha é o consultor na tela, não um dev lendo stack trace."""
    with pytest.raises(FalhaInstrumento) as e:
        gcs.token("", ESCOPO)
    assert "Google Cloud" in str(e.value)
    assert e.value.retentavel is False


def test_sem_escopo_recusa_em_vez_de_pedir_acesso_amplo():
    """`cloud-platform` resolveria e daria acesso a tudo. Recusar é a escolha certa:
    a conta de serviço só deve poder o que o instrumento usa."""
    with pytest.raises(FalhaInstrumento) as e:
        gcs.token(CHAVE, "")
    assert "escopo" in str(e.value).lower()
    assert "webmasters.readonly" in str(e.value)


def test_json_quebrado_diz_o_que_colar():
    with pytest.raises(FalhaInstrumento) as e:
        gcs.token("{isso nao e json", ESCOPO)
    assert "JSON" in str(e.value)


def test_credencial_de_oauth_no_lugar_da_conta_de_servico():
    """Erro fácil de cometer: baixar as credenciais de OAuth em vez da chave da conta
    de serviço. Os dois são JSON do Google Cloud e só um funciona."""
    oauth = json.dumps({"installed": {"client_id": "x", "client_secret": "y"}})
    with pytest.raises(FalhaInstrumento) as e:
        gcs.token(oauth, ESCOPO)
    assert "service_account" in str(e.value)


def test_token_e_reaproveitado_enquanto_vale(monkeypatch):
    """O token dura ~1h e assinar custa: duas chamadas seguidas não assinam duas vezes."""
    idas: list = []
    _dublar(monkeypatch, contador=idas)
    primeiro = gcs.token(CHAVE, ESCOPO)
    assert gcs.token(CHAVE, ESCOPO) == primeiro
    assert len(idas) == 1, "assinou duas vezes para o mesmo escopo"


def test_escopo_diferente_nao_reusa_o_token(monkeypatch):
    """Token é POR escopo: reusar o de outro escopo daria 403 no meio do trabalho."""
    idas: list = []
    _dublar(monkeypatch, contador=idas)
    a = gcs.token(CHAVE, ESCOPO)
    b = gcs.token(CHAVE, "https://www.googleapis.com/auth/drive.readonly")
    assert a != b
    assert len(idas) == 2, "reusou o token de outro escopo"


def test_a_chave_privada_nunca_vira_chave_de_cache():
    """Chave de dicionário aparece em dump de memória e em depuração. Só o hash."""
    k = gcs._chave_cache(CHAVE, (ESCOPO,))
    assert "PRIVATE KEY" not in k and "falsa" not in k
    assert len(k) == 64  # sha256 em hex


def test_email_da_chave_para_a_tela_dizer_quem_autorizar():
    """No Search Console, quem precisa virar usuário da propriedade é o e-mail da
    conta de serviço — a tela só consegue dizer isso se souber lê-lo."""
    assert gcs.email_da_chave(CHAVE) == "batuta@projeto.iam.gserviceaccount.com"
    assert gcs.email_da_chave("lixo") == ""


def test_conector_aceita_o_tipo_novo():
    from instrumentos.conector import ConfigConector

    c = ConfigConector(auth_tipo="google_conta_servico", auth_segredo=CHAVE, escopo=ESCOPO)
    assert c.auth_tipo == "google_conta_servico"
    # o JSON é segredo: entra pelo mesmo campo cifrado dos outros segredos
    from instrumentos import obter_tipo

    assert "auth_segredo" in obter_tipo("conector").campos_secretos
