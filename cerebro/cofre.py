"""Cofre de criptografia das chaves de API (Fase 7, PRODUTO §26).

As chaves de API (executora/criadora/companheira; por organização ou da
consultoria) nunca são guardadas em claro. Este módulo cifra antes de gravar no
banco e decifra na hora de usar, com criptografia simétrica autenticada
(Fernet: AES-128 em CBC + HMAC-SHA256, com timestamp).

A CHAVE-MESTRA do cofre vive só no .env do cérebro (COFRE_CHAVE_MESTRA), nunca no
banco nem na interface (CLAUDE §8). É o segredo que protege todos os outros: se
for perdida, as chaves cifradas no banco tornam-se irrecuperáveis.
"""

import os

from cryptography.fernet import Fernet


class CofreNaoConfigurado(RuntimeError):
    """A COFRE_CHAVE_MESTRA não está no ambiente. O cofre não opera sem ela."""


def _fernet() -> Fernet:
    chave = os.environ.get("COFRE_CHAVE_MESTRA")
    if not chave:
        raise CofreNaoConfigurado(
            "COFRE_CHAVE_MESTRA ausente no .env do cérebro. "
            "Gere uma com: uv run python scripts/gerar_chave_mestra.py"
        )
    return Fernet(chave.encode())


def cifrar(segredo: str) -> str:
    """Cifra um segredo (ex.: uma chave de API). Devolve o token cifrado (str)."""
    return _fernet().encrypt(segredo.encode()).decode()


def decifrar(token: str) -> str:
    """Decifra um token produzido por cifrar(). Levanta cryptography.fernet.
    InvalidToken se o token foi adulterado ou se a chave-mestra mudou."""
    return _fernet().decrypt(token.encode()).decode()


def ultimos4(segredo: str) -> str:
    """Os últimos 4 caracteres de um segredo, para exibição segura na interface
    (PRODUTO §26: a chave inteira nunca é reexibida depois de salva)."""
    return segredo[-4:] if len(segredo) >= 4 else segredo
