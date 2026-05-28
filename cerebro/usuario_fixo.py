"""Usuário fixo de testes — SOMENTE Etapa 1.

Enquanto não há login real, toda operação do cérebro assume este usuário como
o usuário atual. Na Etapa 2 (Supabase Auth), este módulo é o ÚNICO ponto a
substituir: usuario_atual_id() passará a ler o usuário autenticado da requisição.
"""

import uuid

USUARIO_FIXO_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
USUARIO_FIXO_NOME = "Usuário de Testes"
USUARIO_FIXO_EMAIL = "teste@batuta.local"


def usuario_atual_id() -> uuid.UUID:
    """O usuário atual de toda operação na Etapa 1. Substituir na Etapa 2."""
    return USUARIO_FIXO_ID
