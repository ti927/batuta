"""Certificado do cliente (mTLS) no instrumento MCP (Fase 3, 2026-09-29) contra um
servidor MCP HTTPS DE VERDADE que EXIGE certificado do cliente. A autoridade, o
certificado do servidor e o do cliente são gerados aqui mesmo.
"""

import base64
import datetime
import ipaddress
import ssl
import threading
import time

import pytest

import instrumentos as encaixe
import instrumentos.mcp as mcp_mod
from instrumentos import mcp_conexao
from instrumentos.base import FalhaInstrumento
from instrumentos.mcp import ArgsMCP, ConectarMCP, ConfigMCP
from mcp_servidor_falso import _mcp, _porta_livre


def _gerar(tmp):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    agora = datetime.datetime.now(datetime.timezone.utc)

    def nome(cn):
        return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])

    def pem_chave(k):
        return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                               serialization.NoEncryption()).decode()

    ca_k = ec.generate_private_key(ec.SECP256R1())
    ca = (x509.CertificateBuilder().subject_name(nome("CA teste")).issuer_name(nome("CA teste"))
          .public_key(ca_k.public_key()).serial_number(1)
          .not_valid_before(agora - datetime.timedelta(days=1))
          .not_valid_after(agora + datetime.timedelta(days=2))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_k.public_key()), critical=False)
          .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                       key_encipherment=False, data_encipherment=False,
                                       key_agreement=False, key_cert_sign=True, crl_sign=True,
                                       encipher_only=False, decipher_only=False), critical=True)
          .sign(ca_k, hashes.SHA256()))

    def emitir(cn, serial, san=None):
        k = ec.generate_private_key(ec.SECP256R1())
        b = (x509.CertificateBuilder().subject_name(nome(cn)).issuer_name(ca.subject)
             .public_key(k.public_key()).serial_number(serial)
             .not_valid_before(agora - datetime.timedelta(days=1))
             .not_valid_after(agora + datetime.timedelta(days=2))
             # O Python 3.13 verifica em modo estrito: exige estes identificadores.
             .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_k.public_key()), critical=False)
             .add_extension(x509.SubjectKeyIdentifier.from_public_key(k.public_key()), critical=False))
        if san:
            b = b.add_extension(x509.SubjectAlternativeName(san), critical=False)
        return b.sign(ca_k, hashes.SHA256()).public_bytes(serialization.Encoding.PEM).decode(), pem_chave(k)

    srv_cert, srv_chave = emitir("127.0.0.1", 2, [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))])
    cli_cert, cli_chave = emitir("cliente Batuta", 3)
    ca_pem = ca.public_bytes(serialization.Encoding.PEM).decode()
    arquivos = {}
    for n, c in {"ca": ca_pem, "srv_cert": srv_cert, "srv_chave": srv_chave}.items():
        p = tmp / f"{n}.pem"
        p.write_text(c)
        arquivos[n] = str(p)
    return arquivos, cli_cert, cli_chave


@pytest.fixture(scope="module")
def tls(tmp_path_factory):
    import uvicorn

    arquivos, cli_cert, cli_chave = _gerar(tmp_path_factory.mktemp("mtls"))
    porta = _porta_livre()
    servidor = uvicorn.Server(uvicorn.Config(
        _mcp("falso-mtls").streamable_http_app(), host="127.0.0.1", port=porta, log_level="error",
        ssl_certfile=arquivos["srv_cert"], ssl_keyfile=arquivos["srv_chave"],
        ssl_ca_certs=arquivos["ca"], ssl_cert_reqs=ssl.CERT_REQUIRED,
    ))
    threading.Thread(target=servidor.run, daemon=True).start()
    limite = time.monotonic() + 15
    while not servidor.started:
        assert time.monotonic() < limite, "o servidor TLS não subiu"
        time.sleep(0.05)
    yield {"url": f"https://127.0.0.1:{porta}/mcp", "ca": arquivos["ca"],
           "cert": cli_cert, "chave": cli_chave}
    servidor.should_exit = True


@pytest.fixture(autouse=True)
def _confia_na_ca_de_teste(tls, monkeypatch):
    monkeypatch.setattr(mcp_conexao, "_contexto_base",
                        lambda: ssl.create_default_context(cafile=tls["ca"]))
    mcp_mod._CACHE.clear()
    yield
    mcp_mod._CACHE.clear()


def test_conecta_apresentando_o_certificado(tls):
    c = ConfigMCP(url=tls["url"], auth_modo="nenhuma", certificado=tls["cert"], chave_privada=tls["chave"])
    r = ConectarMCP().executar(c, ArgsMCP())
    assert r["ok"] and r["servidor"]["nome"] == "falso-mtls"


def test_ferramenta_do_cinto_tambem_apresenta(tls):
    c = ConfigMCP.model_validate({
        "url": tls["url"], "auth_modo": "nenhuma", "certificado": tls["cert"],
        "chave_privada": tls["chave"], "transport": "streamable_http",
        "ferramentas": [{"nome": "ler", "usar": True, "irreversivel": False}],
    })
    [f] = ConectarMCP().expandir_ferramentas(c)
    assert "lido z" in str(f.invoke({"texto": "z"}))


def test_sem_certificado_a_falha_diz_o_que_fazer(tls):
    with pytest.raises(FalhaInstrumento) as e:
        ConectarMCP().executar(ConfigMCP(url=tls["url"], auth_modo="nenhuma"), ArgsMCP())
    # O servidor derruba a conexão sem responder: o Batuta não tem como saber se foi o
    # certificado ou uma queda, e diz as duas coisas.
    assert e.value.codigo in ("mcp.conexao_encerrada", "mcp.certificado_recusado")
    assert "certificado" in str(e.value)


def test_arquivo_enviado_vira_par_pem_no_cofre_e_senha_nao_fica(tls):
    arquivo = base64.b64encode((tls["cert"] + tls["chave"]).encode()).decode()
    publica, secretos = encaixe.preparar_config("conectar_mcp", {
        "auth_modo": "nenhuma", "url": tls["url"], "arquivo": arquivo, "senha_certificado": "",
    })
    assert "BEGIN CERTIFICATE" in secretos["certificado"]
    assert "PRIVATE KEY" in secretos["chave_privada"]
    assert "arquivo" not in secretos and "senha_certificado" not in secretos
    assert not any(k in publica for k in ("arquivo", "certificado", "chave_privada"))


def test_arquivo_invalido_recusa_ao_salvar():
    with pytest.raises(ValueError) as e:
        encaixe.preparar_config("conectar_mcp", {"url": "https://x", "arquivo": base64.b64encode(b"lixo").decode()})
    assert "Certificado" in str(e.value)


def test_certificado_guardado_corrompido(tls):
    with pytest.raises(FalhaInstrumento) as e:
        mcp_conexao.montar_destino(ConfigMCP(url=tls["url"], certificado="lixo", chave_privada="lixo"))
    assert e.value.codigo == "mcp.certificado_invalido"
