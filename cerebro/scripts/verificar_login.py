"""Verifica que um login de teste realmente autentica.

Tenta o fluxo real de senha (precisa da anon key). Se ela não estiver no ambiente
do cérebro, cai para a Admin API e confirma que a conta existe e está confirmada.

Uso (da pasta cerebro/):  uv run python scripts/verificar_login.py <email> <senha>
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(RAIZ, ".env"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main() -> None:
    email, senha = sys.argv[1].strip(), sys.argv[2]
    url = os.environ["SUPABASE_URL"].rstrip("/")
    service = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    anon = None
    for k in (
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
    ):
        if os.environ.get(k):
            anon = os.environ[k]
            break

    if anon:
        r = httpx.post(
            f"{url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": anon, "Content-Type": "application/json"},
            json={"email": email, "password": senha},
            timeout=20,
        )
        print(f"Login por senha -> HTTP {r.status_code}")
        if r.status_code < 300:
            tok = r.json().get("access_token")
            print(f"OK: autenticou. access_token presente: {bool(tok)}")
        else:
            print("FALHOU:", r.text)
            sys.exit(1)
        return

    print("Sem anon key no cérebro; conferindo via Admin API (existência + confirmação):")
    headers = {"apikey": service, "Authorization": f"Bearer {service}"}
    pagina, achou = 1, None
    while True:
        rr = httpx.get(
            f"{url}/auth/v1/admin/users",
            headers=headers,
            params={"page": pagina, "per_page": 200},
            timeout=20,
        )
        rr.raise_for_status()
        corpo = rr.json()
        us = corpo.get("users", corpo) if isinstance(corpo, dict) else corpo
        for u in us:
            if (u.get("email") or "").lower() == email.lower():
                achou = u
                break
        if achou or not us or len(us) < 200:
            break
        pagina += 1
    if achou:
        print(f"Conta existe. email_confirmed_at: {achou.get('email_confirmed_at')}")
    else:
        print("NÃO encontrada.")
        sys.exit(1)


if __name__ == "__main__":
    main()
