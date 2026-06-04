"""Chamadas à Admin API do Supabase Auth (com a service role key).

Usada só pelo cérebro — NUNCA exposta à interface. Hoje serve para convidar um
email (cria a conta no Supabase e dispara o email de convite).
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

TIMEOUT_S = 20.0


def _base_e_headers() -> tuple[str, dict]:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    chave = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return url, {
        "apikey": chave,
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
    }


def convidar(email: str) -> dict:
    """Convida um email: cria a conta no Supabase Auth e dispara o email de
    convite (o convidado define a senha e cai logado). Levanta httpx.HTTPError
    em falha de transporte e HTTPStatusError em resposta de erro."""
    url, headers = _base_e_headers()
    r = httpx.post(
        f"{url}/auth/v1/invite", headers=headers, json={"email": email}, timeout=TIMEOUT_S
    )
    r.raise_for_status()
    return r.json()
