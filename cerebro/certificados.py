"""Leitura e validação de certificados digitais de cliente (mTLS) — fundação das
integrações bancárias (Pix, boleto) e de qualquer API que exija certificado.

Um certificado de cliente (tipo A1 — arquivo, não token físico A3) chega em um de
dois formatos:
  - `.pfx`/`.p12` (PKCS#12): um único arquivo BINÁRIO protegido por senha, que
    embrulha o certificado + a chave privada. É o formato mais comum do
    "certificado digital" brasileiro (e-CNPJ/e-CPF, ICP-Brasil A1);
  - `.pem`/`.crt` + `.key` (PEM): texto — o certificado e a chave em arquivos
    separados (ou no mesmo). É o que o Banco Inter entrega, por exemplo.

Este módulo NORMALIZA os dois para o mesmo par PEM (certificado + chave em claro),
que é o formato que a chamada mTLS materializa na hora de conectar (fatia B). A
senha só é usada AQUI, para abrir o arquivo; ela NÃO é guardada — o par PEM
resultante é protegido pelo cofre (Fernet) como todo segredo do Batuta.

Nada de rede nem de banco aqui: é só leitura de bytes. A gravação cifrada é do
`credenciais_cofre`; a apresentação do certificado na conexão é da fatia B.
"""

import base64
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


class CertificadoInvalido(ValueError):
    """O arquivo não é um certificado legível, ou a senha está errada. A mensagem
    é humana (Lei §12-A) — a rota a devolve como 422 direto ao usuário."""


def _b64(dado: str) -> bytes:
    """Decodifica base64 (o front envia o arquivo assim). Erro vira mensagem clara."""
    try:
        return base64.b64decode(dado, validate=False)
    except (ValueError, TypeError) as e:
        raise CertificadoInvalido(f"não consegui ler o arquivo enviado ({e}).")


def _titular(cert: x509.Certificate) -> str:
    """O nome do titular do certificado (Common Name), para exibição. Nos
    certificados ICP-Brasil vem como 'NOME DA EMPRESA:CNPJ' — bom o bastante para
    o usuário reconhecer qual certificado é."""
    try:
        atributos = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if atributos:
            return str(atributos[0].value)
    except Exception:  # noqa: BLE001 — nome é cosmético, nunca derruba a leitura
        pass
    try:
        return cert.subject.rfc4514_string()
    except Exception:  # noqa: BLE001
        return "certificado"


def _expira_em(cert: x509.Certificate) -> datetime:
    """Data de expiração do certificado (sempre em UTC, timezone-aware)."""
    quando = getattr(cert, "not_valid_after_utc", None)
    if quando is None:  # compat com versões antigas do cryptography
        quando = cert.not_valid_after.replace(tzinfo=timezone.utc)
    return quando


def _cert_pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def _chave_pem(chave) -> str:
    """Serializa a chave privada como PEM PKCS#8 SEM senha — o cofre é quem a
    protege (Fernet). A senha do arquivo original não é guardada."""
    return chave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def _abrir_pfx(dados: bytes, senha: bytes | None):
    try:
        chave, cert, _ = pkcs12.load_key_and_certificates(dados, senha)
    except (ValueError, TypeError):
        raise CertificadoInvalido(
            "não consegui abrir o certificado (.pfx/.p12). A senha pode estar "
            "errada, ou o arquivo não é um certificado válido."
        )
    if cert is None:
        raise CertificadoInvalido("o arquivo não contém um certificado.")
    if chave is None:
        raise CertificadoInvalido(
            "o arquivo não contém a chave privada — envie o certificado completo "
            "(com a chave), não só a parte pública."
        )
    return chave, cert


def _abrir_pem(cert_bytes: bytes, chave_bytes: bytes, senha: bytes | None):
    try:
        cert = x509.load_pem_x509_certificate(cert_bytes)
    except ValueError:
        raise CertificadoInvalido(
            "não consegui ler o certificado (.pem/.crt). Confira se enviou o "
            "arquivo certo."
        )
    try:
        chave = serialization.load_pem_private_key(chave_bytes, senha)
    except (ValueError, TypeError):
        raise CertificadoInvalido(
            "não consegui ler a chave privada. Se a chave tem senha, informe-a; "
            "se a chave está num arquivo separado (.key), envie-o também."
        )
    return chave, cert


def normalizar(
    arquivo_b64: str, senha: str = "", chave_b64: str = ""
) -> tuple[str, str, str, datetime]:
    """Lê o certificado enviado (base64) e devolve
    `(certificado_pem, chave_privada_pem, titular, expira_em)`.

    Aceita `.pfx`/`.p12` (binário, com senha) OU `.pem`/`.crt` (texto), com a chave
    no mesmo arquivo ou num `.key` separado (`chave_b64`). `senha` é opcional
    (para abrir o `.pfx` ou uma chave PEM cifrada) e nunca é guardada.

    Levanta `CertificadoInvalido` (mensagem humana) para qualquer arquivo ilegível
    ou senha errada."""
    if not arquivo_b64 or not arquivo_b64.strip():
        raise CertificadoInvalido(
            "envie o arquivo do certificado (.pfx/.p12 ou .pem/.crt)."
        )
    dados = _b64(arquivo_b64)
    senha_bytes = senha.encode() if senha else None

    if b"-----BEGIN" in dados:
        # PEM: a chave pode estar no mesmo arquivo ou num .key separado.
        chave_bytes = _b64(chave_b64) if chave_b64 and chave_b64.strip() else dados
        chave, cert = _abrir_pem(dados, chave_bytes, senha_bytes)
    else:
        # PFX/P12 (binário DER).
        chave, cert = _abrir_pfx(dados, senha_bytes)

    return _cert_pem(cert), _chave_pem(chave), _titular(cert), _expira_em(cert)
