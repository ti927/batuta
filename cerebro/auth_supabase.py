"""Validação do token de acesso (JWT) do Supabase Auth — Tarefa 6.2 (Fase 6).

O Supabase deste projeto assina os tokens com chaves ASSIMÉTRICAS (ES256,
confirmado na Tarefa 6.1). O cérebro busca a chave pública no endpoint JWKS do
projeto e valida o token LOCALMENTE — sem segredo no `.env` e sem bater no
Supabase a cada requisição (as chaves públicas são cacheadas pelo PyJWKClient,
que ainda lida com rotação de chave buscando pelo `kid` do token).

Este módulo só valida o token cru (assinatura, validade, audiência, emissor) e
devolve os claims. Quem amarra esses claims a um `Usuario` do banco é `auth.py`.
"""

import os

import jwt
from dotenv import load_dotenv
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

load_dotenv()

# Algoritmos assimétricos aceitos. NUNCA incluir HS256 aqui: aceitar um algoritmo
# simétrico ao lado de chaves públicas abre a porta para o ataque de confusão de
# algoritmo. O projeto usa ES256; RS256 fica como folga para rotação futura.
ALGORITMOS = ["ES256", "RS256"]
AUDIENCIA = "authenticated"

_SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
EMISSOR = f"{_SUPABASE_URL}/auth/v1"
_JWKS_URL = f"{EMISSOR}/.well-known/jwks.json"

# Cliente JWKS único, reusado entre requisições: cacheia as chaves públicas e as
# busca pelo `kid` do token (resolve rotação de chave sem reiniciar o cérebro).
_cliente_jwks = PyJWKClient(_JWKS_URL)


class TokenInvalido(Exception):
    """O token de acesso é ausente, malformado, expirado ou não confiável."""


def validar_token(token: str) -> dict:
    """Valida assinatura, validade (`exp`), audiência e emissor de um token de
    acesso do Supabase. Devolve os claims (com `sub` = id do usuário no Supabase)
    ou levanta `TokenInvalido`."""
    if not token:
        raise TokenInvalido("token ausente")
    try:
        chave = _cliente_jwks.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            chave,
            algorithms=ALGORITMOS,
            audience=AUDIENCIA,
            issuer=EMISSOR,
        )
    except (InvalidTokenError, PyJWKClientError) as e:
        raise TokenInvalido(str(e)) from e
