"""Cria um login de TESTE (p/ o analista da Meta) numa organização existente.

Cria/atualiza a conta no Supabase Auth (email + senha, JÁ CONFIRMADA, sem disparar
e-mail), liga ao Batuta (`usuarios`) e vincula como Membro da organização com o
papel informado. Imprime email + senha prontos para colar no App Review.
Idempotente: rodar de novo só reafirma a senha e o vínculo. Ferramenta de teste,
não faz parte do produto.

Uso (a partir da pasta cerebro/):
    uv run python scripts/criar_login_analista.py <email> <organizacao> [papel] [senha]

  - papel: admin|operador|observador (padrão: operador)
  - senha: opcional; se omitida, gera uma forte e imprime.
"""

import os
import secrets
import sys
import uuid

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import httpx
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import engine
from modelos import Membro, Organizacao, Usuario

load_dotenv(os.path.join(RAIZ, ".env"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _supabase() -> tuple[str, dict]:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    chave = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {
        "apikey": chave,
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
    }
    return url, headers


def achar_usuario_supabase(url: str, headers: dict, email: str) -> dict | None:
    """Procura a conta no Supabase Auth pelo email (Admin API, paginado)."""
    pagina = 1
    while True:
        r = httpx.get(
            f"{url}/auth/v1/admin/users",
            headers=headers,
            params={"page": pagina, "per_page": 200},
            timeout=20,
        )
        r.raise_for_status()
        corpo = r.json()
        usuarios = corpo.get("users", corpo) if isinstance(corpo, dict) else corpo
        for u in usuarios:
            if (u.get("email") or "").lower() == email.lower():
                return u
        if not usuarios or len(usuarios) < 200:
            return None
        pagina += 1


def criar_ou_atualizar_auth(url: str, headers: dict, email: str, senha: str) -> str:
    """Cria a conta (email+senha, confirmada) ou, se já existir, redefine a senha.
    Devolve o id (sub) do Supabase."""
    r = httpx.post(
        f"{url}/auth/v1/admin/users",
        headers=headers,
        json={"email": email, "password": senha, "email_confirm": True},
        timeout=20,
    )
    if r.status_code < 300:
        return r.json()["id"]
    existente = achar_usuario_supabase(url, headers, email)
    if existente is None:
        print(f"ERRO ao criar no Supabase: {r.status_code} {r.text}")
        sys.exit(1)
    uid = existente["id"]
    r2 = httpx.put(
        f"{url}/auth/v1/admin/users/{uid}",
        headers=headers,
        json={"password": senha, "email_confirm": True},
        timeout=20,
    )
    r2.raise_for_status()
    return uid


def main() -> None:
    if len(sys.argv) < 3:
        print("uso: criar_login_analista.py <email> <organizacao> [papel] [senha]")
        sys.exit(2)
    email = sys.argv[1].strip()
    org_ref = sys.argv[2].strip()
    papel = sys.argv[3].strip() if len(sys.argv) > 3 else "operador"
    senha = sys.argv[4].strip() if len(sys.argv) > 4 else "BatutaTeste-" + secrets.token_hex(4)

    if papel not in ("admin", "operador", "observador"):
        print(f"papel inválido: {papel} (use admin|operador|observador)")
        sys.exit(2)

    url, headers = _supabase()

    with Session(engine) as s:
        orgs = s.scalars(select(Organizacao)).all()
        alvo = None
        for o in orgs:
            if str(o.id) == org_ref or org_ref.lower() in (o.nome or "").lower():
                alvo = o
                break
        if alvo is None:
            print(f"Organização não encontrada: {org_ref}")
            print("Existentes:", [o.nome for o in orgs])
            sys.exit(1)

        sub = criar_ou_atualizar_auth(url, headers, email, senha)

        usuario = s.scalars(select(Usuario).where(Usuario.email == email)).first()
        if usuario:
            usuario.auth_id = uuid.UUID(sub)
            usuario.ativo = True
        else:
            usuario = Usuario(
                nome="Analista Meta", email=email, auth_id=uuid.UUID(sub), ativo=True
            )
            s.add(usuario)
            s.flush()

        membro = s.scalars(
            select(Membro).where(
                Membro.usuario_id == usuario.id, Membro.organizacao_id == alvo.id
            )
        ).first()
        if membro:
            membro.papel = papel
        else:
            s.add(Membro(usuario_id=usuario.id, organizacao_id=alvo.id, papel=papel))
        s.commit()
        nome_org = alvo.nome

    print("\n=== LOGIN DE TESTE PRONTO ===")
    print("App:   https://batuta.team/login")
    print(f"Org:   {nome_org}")
    print(f"Email: {email}")
    print(f"Senha: {senha}")
    print(f"Papel: {papel}")


if __name__ == "__main__":
    main()
