"""Fundação bancária, Fatia A — o cofre guarda o certificado digital (mTLS).

Cobre a leitura/normalização do certificado (`certificados.normalizar`) e a
gravação cifrada no cofre (`credenciais_cofre.gravar_com_certificado`), offline —
sem banco nem rede. Gera certificados de teste em memória (auto-assinados)."""

import base64
import datetime
import json
import os

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from cryptography.fernet import Fernet

# Chave-mestra do cofre para os testes (o cofre a lê preguiçosamente em _fernet()).
os.environ.setdefault("COFRE_CHAVE_MESTRA", Fernet.generate_key().decode())

import certificados
import credenciais_cofre as cofre_cred
import tipos_credencial  # noqa: F401 — registra o tipo certificado_mtls
from modelos import Credencial

CN = "EMPRESA TESTE LTDA:12345678000199"


def _gerar_par(cn: str = CN):
    """Um par (chave EC, certificado auto-assinado) para os testes. EC é rápido."""
    chave = ec.generate_private_key(ec.SECP256R1())
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    agora = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - datetime.timedelta(days=1))
        .not_valid_after(agora + datetime.timedelta(days=365))
        .sign(chave, hashes.SHA256())
    )
    return chave, cert


def _pfx_b64(senha: bytes | None = None) -> str:
    chave, cert = _gerar_par()
    cripto = (
        serialization.BestAvailableEncryption(senha)
        if senha
        else serialization.NoEncryption()
    )
    bruto = pkcs12.serialize_key_and_certificates(
        name=b"teste", key=chave, cert=cert, cas=None, encryption_algorithm=cripto
    )
    return base64.b64encode(bruto).decode()


def _pem_b64(com_chave: bool = True):
    """Devolve (cert_ou_bundle_b64, chave_b64|None). Com `com_chave`, o cert e a
    chave vão no MESMO arquivo (bundle); senão, em arquivos separados."""
    chave, cert = _gerar_par()
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    chave_pem = chave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    if com_chave:
        return base64.b64encode(cert_pem + chave_pem).decode(), None
    return base64.b64encode(cert_pem).decode(), base64.b64encode(chave_pem).decode()


# ─────────────────────────── certificados.normalizar ──────────────────────────


def test_normaliza_pfx_com_senha():
    cert_pem, chave_pem, titular, expira = certificados.normalizar(
        _pfx_b64(b"segredo123"), senha="segredo123"
    )
    assert "BEGIN CERTIFICATE" in cert_pem
    assert "BEGIN PRIVATE KEY" in chave_pem
    assert "12345678000199" in titular
    assert expira > datetime.datetime.now(datetime.timezone.utc)


def test_normaliza_pfx_sem_senha():
    cert_pem, chave_pem, titular, _ = certificados.normalizar(_pfx_b64(None))
    assert "BEGIN CERTIFICATE" in cert_pem
    assert "BEGIN PRIVATE KEY" in chave_pem


def test_normaliza_pem_bundle():
    arquivo, _ = _pem_b64(com_chave=True)
    cert_pem, chave_pem, titular, _ = certificados.normalizar(arquivo)
    assert "BEGIN CERTIFICATE" in cert_pem
    assert "BEGIN PRIVATE KEY" in chave_pem
    assert "EMPRESA TESTE" in titular


def test_normaliza_pem_chave_separada():
    cert_b64, chave_b64 = _pem_b64(com_chave=False)
    cert_pem, chave_pem, _, _ = certificados.normalizar(cert_b64, chave_b64=chave_b64)
    assert "BEGIN CERTIFICATE" in cert_pem
    assert "BEGIN PRIVATE KEY" in chave_pem


def test_senha_errada_no_pfx():
    with pytest.raises(certificados.CertificadoInvalido):
        certificados.normalizar(_pfx_b64(b"certa"), senha="errada")


def test_arquivo_lixo():
    with pytest.raises(certificados.CertificadoInvalido):
        certificados.normalizar(base64.b64encode(b"isto nao e um certificado").decode())


def test_arquivo_vazio():
    with pytest.raises(certificados.CertificadoInvalido):
        certificados.normalizar("")


# ──────────────────── credenciais_cofre.gravar_com_certificado ─────────────────


def test_grava_certificado_cifra_e_mascara():
    cred = Credencial(tipo="certificado_mtls", nome="Itaú Pix")
    cofre_cred.gravar_com_certificado(
        cred,
        {
            "arquivo": _pfx_b64(b"s3nha"),
            "senha_certificado": "s3nha",
            "client_id": "cli-123",
            "client_secret": "seg-abc-9999",
        },
    )
    # O saco decifrado tem o PEM e o OAuth; a senha do .pfx NÃO é guardada.
    saco = cofre_cred.decifrar(cred)
    assert "BEGIN CERTIFICATE" in saco["certificado"]
    assert "BEGIN PRIVATE KEY" in saco["chave_privada"]
    assert saco["client_id"] == "cli-123"
    assert saco["client_secret"] == "seg-abc-9999"
    assert "senha_certificado" not in saco
    assert "12345678000199" in saco["titular"]
    # Resumo: segredos mascarados; identidade visível.
    r = cred.resumo
    assert r["certificado"]["secreto"] is True
    assert r["chave_privada"]["secreto"] is True
    assert r["client_secret"]["secreto"] is True and r["client_secret"]["ultimos4"] == "9999"
    assert r["client_id"]["valor"] == "cli-123"
    assert "12345678000199" in r["titular"]["valor"]
    assert r["validade"]["valor"]  # dd/mm/aaaa
    # expira_em derivado do certificado.
    assert cred.expira_em is not None


def test_edicao_sem_arquivo_preserva_certificado():
    cred = Credencial(tipo="certificado_mtls", nome="Inter boleto")
    cofre_cred.gravar_com_certificado(
        cred, {"arquivo": _pfx_b64(None), "client_secret": "antigo-0001"}
    )
    cert_antes = cofre_cred.decifrar(cred)["certificado"]
    # Edição só do client_secret, sem reenviar o arquivo.
    cofre_cred.gravar_com_certificado(cred, {"client_secret": "novo-0002"})
    saco = cofre_cred.decifrar(cred)
    assert saco["certificado"] == cert_antes  # preservado
    assert saco["client_secret"] == "novo-0002"  # atualizado


def test_criar_sem_arquivo_recusa():
    cred = Credencial(tipo="certificado_mtls", nome="sem cert")
    with pytest.raises(certificados.CertificadoInvalido):
        cofre_cred.gravar_com_certificado(cred, {"client_id": "x"})


# ═══════════════ Fatia B — apresentar o certificado na conexão ════════════════
# O par PEM sai do cofre e é apresentado no aperto de mão TLS. Cobre o
# materializador (arquivos temporários que morrem no fim) e os DOIS caminhos de
# saída HTTP do Batuta: o "Chamar API REST" e o Conector.

import instrumentos.conector as conector_mod  # noqa: E402
import instrumentos.rest as rest  # noqa: E402
from instrumentos.conector import (  # noqa: E402
    CampoOperacao,
    ConfigConector,
    OperacaoConector,
    _executar_operacao,
)
from instrumentos.rest import ChamarApiRest, ConfigRest  # noqa: E402

CERT_PEM = "-----BEGIN CERTIFICATE-----\nfalso\n-----END CERTIFICATE-----\n"
CHAVE_PEM = "-----BEGIN PRIVATE KEY-----\nfalsa\n-----END PRIVATE KEY-----\n"


def test_material_mtls_escreve_o_par_e_apaga_depois():
    with certificados.material_mtls(CERT_PEM, CHAVE_PEM) as par:
        assert par is not None
        caminho_cert, caminho_chave = par
        # Durante a chamada, os dois arquivos existem com o conteúdo exato.
        with open(caminho_cert) as a:
            assert a.read() == CERT_PEM
        with open(caminho_chave) as a:
            assert a.read() == CHAVE_PEM
    # Ao sair, nada fica para trás.
    assert not os.path.exists(caminho_cert)
    assert not os.path.exists(caminho_chave)


def test_material_mtls_sem_certificado_devolve_none():
    # Sem par (ou só metade dele), a chamada sai como sempre saiu: sem certificado.
    with certificados.material_mtls("", "") as par:
        assert par is None
    with certificados.material_mtls(CERT_PEM, "   ") as par:
        assert par is None


def test_material_mtls_apaga_ate_se_a_chamada_explodir():
    caminhos = []
    with pytest.raises(RuntimeError):
        with certificados.material_mtls(CERT_PEM, CHAVE_PEM) as par:
            caminhos = list(par)
            raise RuntimeError("a API caiu no meio")
    assert caminhos and not any(os.path.exists(c) for c in caminhos)


class _RespFake:
    status_code = 200
    is_success = True
    text = "{}"

    def json(self):
        return {"ok": True}


class _ClienteFake:
    """Captura o `cert=` que o instrumento passou ao httpx e confere que os
    arquivos ainda EXISTEM na hora da requisição (morrem só depois)."""

    def __init__(self, capturado, **kwargs):
        self.capturado = capturado
        capturado["cert"] = kwargs.get("cert")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def request(self, *a, **k):
        par = self.capturado.get("cert")
        self.capturado["existiam_na_hora"] = bool(par) and all(
            os.path.exists(c) for c in par
        )
        self.capturado["cabecalhos"] = k.get("headers") or {}
        return _RespFake()


def _espionar_httpx(monkeypatch, modulo):
    capturado: dict = {}
    monkeypatch.setattr(
        modulo.httpx, "Client", lambda **k: _ClienteFake(capturado, **k)
    )
    if modulo is rest:  # o log TEMP de diagnóstico escreve no banco — silencia
        monkeypatch.setattr(rest, "registrar_evento", lambda **k: None)
    return capturado


def test_rest_apresenta_o_certificado(monkeypatch):
    capturado = _espionar_httpx(monkeypatch, rest)
    ChamarApiRest().executar(
        ConfigRest(
            url="https://api.banco.exemplo/pix", metodo="GET",
            certificado=CERT_PEM, chave_privada=CHAVE_PEM,
        ),
        rest.ArgsRest(),
    )
    par = capturado["cert"]
    assert par is not None and len(par) == 2
    assert capturado["existiam_na_hora"] is True   # vivos durante a requisição
    assert not any(os.path.exists(c) for c in par)  # e apagados ao fim


def test_rest_sem_certificado_segue_como_antes(monkeypatch):
    capturado = _espionar_httpx(monkeypatch, rest)
    ChamarApiRest().executar(
        ConfigRest(url="https://api.exemplo/x", metodo="GET"), rest.ArgsRest()
    )
    assert capturado["cert"] is None


def _op() -> OperacaoConector:
    return OperacaoConector(
        nome="Consultar saldo", metodo="GET",
        url="https://api.banco.exemplo/saldo",
        campos=[CampoOperacao(nome="conta", papel="fixo", valor="1", destino="query")],
    )


def test_conector_apresenta_o_certificado(monkeypatch):
    capturado = _espionar_httpx(monkeypatch, conector_mod)
    _executar_operacao(
        ConfigConector(certificado=CERT_PEM, chave_privada=CHAVE_PEM), _op(), {}
    )
    par = capturado["cert"]
    assert par is not None and len(par) == 2
    assert capturado["existiam_na_hora"] is True
    assert not any(os.path.exists(c) for c in par)


def test_conector_sem_certificado_segue_como_antes(monkeypatch):
    capturado = _espionar_httpx(monkeypatch, conector_mod)
    _executar_operacao(ConfigConector(), _op(), {})
    assert capturado["cert"] is None


# ═══════════ Fatia C — o token OAuth obtido COM o certificado ════════════════
# Um banco de verdade exige certificado E um access_token de vida curta. Quem o
# obtém e renova é a BORDA (o agente não teria como carregar um token de uma
# chamada para a outra). Espelha o que já se faz com o Google.

import oauth_mtls  # noqa: E402
from instrumentos.base import FalhaInstrumento  # noqa: E402


class _RespToken:
    def __init__(self, payload, status=200, texto=None):
        self._payload = payload
        self.status_code = status
        self.text = texto if texto is not None else json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("não é JSON")
        return self._payload


class _ClienteToken:
    """Cliente falso que registra o que foi postado e com qual certificado."""

    def __init__(self, registro, resposta, **kwargs):
        self.registro = registro
        self.resposta = resposta
        registro["cert"] = kwargs.get("cert")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, data=None, **k):
        self.registro["url"] = url
        self.registro["corpo"] = data
        par = self.registro.get("cert")
        self.registro["cert_existia"] = bool(par) and all(
            os.path.exists(c) for c in par
        )
        return self.resposta


def _mock_token(monkeypatch, resposta):
    registro: dict = {}
    monkeypatch.setattr(
        oauth_mtls.httpx, "Client",
        lambda **k: _ClienteToken(registro, resposta, **k),
    )
    return registro


def test_obter_token_manda_client_credentials_com_o_certificado(monkeypatch):
    registro = _mock_token(
        monkeypatch, _RespToken({"access_token": "tok-123", "expires_in": 3600})
    )
    antes = datetime.datetime.now(datetime.timezone.utc)
    token, expira = oauth_mtls.obter_token(
        url_token="https://banco.exemplo/oauth/token",
        client_id="cli", client_secret="seg", escopo="pix.read",
        certificado=CERT_PEM, chave_privada=CHAVE_PEM,
    )
    assert token == "tok-123"
    assert registro["url"] == "https://banco.exemplo/oauth/token"
    assert registro["corpo"] == {
        "grant_type": "client_credentials",
        "client_id": "cli",
        "client_secret": "seg",
        "scope": "pix.read",
    }
    # O certificado é apresentado TAMBÉM na busca do token (o banco exige mTLS lá).
    assert registro["cert_existia"] is True
    # ~1h a partir de agora (a folga cobre o tempo da própria chamada).
    assert 3500 < (expira - antes).total_seconds() < 3700


def test_obter_token_sem_escopo_nao_manda_scope(monkeypatch):
    registro = _mock_token(monkeypatch, _RespToken({"access_token": "t"}))
    oauth_mtls.obter_token(
        url_token="https://b/token", client_id="c", client_secret="s"
    )
    assert "scope" not in registro["corpo"]


def test_obter_token_credencial_recusada_vira_erro_humano(monkeypatch):
    _mock_token(monkeypatch, _RespToken({"error": "invalid_client"}, status=401))
    with pytest.raises(FalhaInstrumento) as e:
        oauth_mtls.obter_token(
            url_token="https://b/token", client_id="c", client_secret="errado"
        )
    assert "recusou as credenciais" in str(e.value)


def test_obter_token_resposta_estranha_vira_erro_humano(monkeypatch):
    _mock_token(monkeypatch, _RespToken(None, texto="<html>página de login</html>"))
    with pytest.raises(FalhaInstrumento) as e:
        oauth_mtls.obter_token(url_token="https://b/errada", client_id="c", client_secret="s")
    assert "não é JSON" in str(e.value) or "URL do token" in str(e.value)


def test_obter_token_sem_access_token_vira_erro_humano(monkeypatch):
    _mock_token(monkeypatch, _RespToken({"outra_coisa": 1}))
    with pytest.raises(FalhaInstrumento):
        oauth_mtls.obter_token(url_token="https://b/token", client_id="c", client_secret="s")


def _cred_com_oauth(**extra) -> Credencial:
    cred = Credencial(tipo="certificado_mtls", nome="Banco")
    cofre_cred.gravar_com_certificado(
        cred,
        {
            "arquivo": _pfx_b64(None),
            "client_id": "cli", "client_secret": "seg",
            "url_token": "https://banco.exemplo/oauth/token",
            **extra,
        },
    )
    return cred


def test_garantir_token_sem_oauth_configurado_devolve_vazio():
    """Certificado sem OAuth é cenário legítimo (a conexão usa só o certificado):
    não pode explodir nem inventar chamada de rede."""
    cred = Credencial(tipo="certificado_mtls", nome="Só certificado")
    cofre_cred.gravar_com_certificado(cred, {"arquivo": _pfx_b64(None)})
    assert oauth_mtls.garantir_token(cred) == ""


def test_garantir_token_reusa_o_cacheado_enquanto_vale(monkeypatch):
    cred = _cred_com_oauth()
    futuro = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    cofre_cred.gravar(
        cred, {"access_token": "cacheado", "token_expira_em": futuro.isoformat()}
    )

    def _nao_chama(**k):
        raise AssertionError("não deveria buscar token novo com o cache válido")

    monkeypatch.setattr(oauth_mtls, "obter_token", _nao_chama)
    assert oauth_mtls.garantir_token(cred) == "cacheado"


def test_garantir_token_renova_o_vencido(monkeypatch):
    cred = _cred_com_oauth()
    passado = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    cofre_cred.gravar(
        cred, {"access_token": "velho", "token_expira_em": passado.isoformat()}
    )
    monkeypatch.setattr(
        oauth_mtls, "obter_token",
        lambda **k: ("novo", datetime.datetime.now(datetime.timezone.utc)
                     + datetime.timedelta(hours=1)),
    )
    monkeypatch.setattr(oauth_mtls, "_persistir_token", lambda *a, **k: None)
    assert oauth_mtls.garantir_token(cred) == "novo"


def test_garantir_token_nunca_derruba_o_cinto(monkeypatch):
    """Se a renovação falhar, devolve o token atual — o instrumento trata o 401
    com recado claro. Uma credencial ruim não pode impedir o agente de carregar."""
    cred = _cred_com_oauth()
    passado = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    cofre_cred.gravar(
        cred, {"access_token": "velho", "token_expira_em": passado.isoformat()}
    )

    def _explode(**k):
        raise FalhaInstrumento("banco fora do ar", retentavel=True)

    monkeypatch.setattr(oauth_mtls, "obter_token", _explode)
    assert oauth_mtls.garantir_token(cred) == "velho"


def test_trocar_o_oauth_invalida_o_token_cacheado():
    """Trocar client_id/segredo/URL (ou o próprio certificado) não pode deixar o
    agente seguir usando o token da conta antiga."""
    cred = _cred_com_oauth()
    cofre_cred.gravar(cred, {"access_token": "da-conta-antiga"})
    assert cofre_cred.decifrar(cred)["access_token"] == "da-conta-antiga"
    cofre_cred.gravar_com_certificado(cred, {"client_id": "outra-conta"})
    saco = cofre_cred.decifrar(cred)
    assert "access_token" not in saco
    assert "token_expira_em" not in saco


def test_rest_usa_o_token_obtido_pela_borda(monkeypatch):
    capturado = _espionar_httpx(monkeypatch, rest)
    ChamarApiRest().executar(
        ConfigRest(url="https://banco/pix", metodo="GET", access_token="tok-borda"),
        rest.ArgsRest(),
    )
    assert capturado["cabecalhos"]["Authorization"] == "Bearer tok-borda"


def test_rest_token_colado_a_mao_tem_precedencia(monkeypatch):
    capturado = _espionar_httpx(monkeypatch, rest)
    ChamarApiRest().executar(
        ConfigRest(
            url="https://x", metodo="GET",
            token_bearer="colado", access_token="da-borda",
        ),
        rest.ArgsRest(),
    )
    assert capturado["cabecalhos"]["Authorization"] == "Bearer colado"


def test_conector_usa_o_token_obtido_pela_borda(monkeypatch):
    capturado = _espionar_httpx(monkeypatch, conector_mod)
    _executar_operacao(ConfigConector(access_token="tok-borda"), _op(), {})
    assert capturado["cabecalhos"]["Authorization"] == "Bearer tok-borda"


def test_conector_auth_declarada_tem_precedencia(monkeypatch):
    capturado = _espionar_httpx(monkeypatch, conector_mod)
    _executar_operacao(
        ConfigConector(auth_tipo="bearer", auth_segredo="declarado", access_token="borda"),
        _op(), {},
    )
    assert capturado["cabecalhos"]["Authorization"] == "Bearer declarado"


def test_certificado_vazio_nao_vira_segredo_pendente():
    """O material de mTLS é OPCIONAL: só APIs bancárias o exigem. Um REST ou um
    conector sem certificado não pode aparecer como 'faltando segredo' — senão
    todo instrumento de integração nasceria cobrando um certificado que ninguém
    precisa (alarme falso na tela e na IA criadora)."""
    import segredos_instrumento as si

    for tipo in ("chamar_api_rest", "conector"):
        faltando = si.pendentes(tipo, guardados=set())
        assert "certificado" not in faltando
        assert "chave_privada" not in faltando
        assert "client_secret" not in faltando


def test_os_dois_caminhos_de_saida_aceitam_a_credencial_do_cofre():
    # A capacidade vale nos DOIS instrumentos que fazem chamada externa — e por
    # REFERÊNCIA ao cofre (o segredo não é digitado no instrumento).
    assert "certificado_mtls" in ChamarApiRest.tipos_credencial_aceitos
    assert "certificado_mtls" in conector_mod.Conector.tipos_credencial_aceitos
    for tipo in (ChamarApiRest, conector_mod.Conector):
        assert "certificado" in tipo.campos_secretos
        assert "chave_privada" in tipo.campos_secretos
