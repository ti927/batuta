"""Quem são os "admins da consultoria" (Fase 7.4, MIGRACAO Virada 5).

A chave-mãe da consultoria (o fallback usado quando o cliente não tem chave
própria) é gerida só por um grupo restrito: os admins da consultoria. Eles são
definidos por uma lista de e-mails no `.env` do cérebro (`CONSULTORIA_ADMINS`,
separados por vírgula) — solução leve e segura, que pode evoluir depois.

Fail-closed: se a variável não estiver no `.env`, a lista é vazia e NINGUÉM é
admin da consultoria — os endpoints da chave-mãe ficam inacessíveis até o maestro
preencher a linha. É o comportamento seguro por padrão.
"""

import os

from dotenv import load_dotenv
from fastapi import HTTPException, status

from modelos import Usuario

load_dotenv()


def admins_consultoria() -> set[str]:
    """O conjunto de e-mails (normalizados) com poder de admin da consultoria.
    Lido do ambiente a cada chamada — sem cache —, para refletir mudanças no
    `.env` sem reiniciar e para os testes poderem sobrescrever via monkeypatch."""
    bruto = os.environ.get("CONSULTORIA_ADMINS", "")
    return {e.strip().lower() for e in bruto.split(",") if e.strip()}


def eh_admin_consultoria(email: str | None) -> bool:
    return bool(email) and email.strip().lower() in admins_consultoria()


def exigir_admin_consultoria(usuario: Usuario) -> None:
    """Guarda das rotas da chave-mãe: 403 se o usuário não é admin da
    consultoria. Não revela a lista nem por que falhou além do necessário."""
    if not eh_admin_consultoria(usuario.email):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Esta ação é restrita aos admins da consultoria.",
        )
