"""Bootstrap do primeiro admin (Fase 6, Tarefa 6.8).

Liga a conta do maestro no Supabase Auth ao Batuta: cria (ou atualiza) o registro
`usuarios` com o `auth_id` correspondente e `ativo=true`. A partir daí ele loga e
cria a primeira organização, tornando-se admin dela (não criamos membro aqui — a
posse nasce na criação da organização).

O id (sub) é buscado no Supabase pela Admin API (service role), pelo email — sem
precisar copiar UUID à mão.

Uso:  uv run python scripts/bootstrap_admin.py <email>
"""

import os
import sys
import uuid

# Permite rodar de scripts/ achando os módulos do cérebro (db, modelos).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import engine
from modelos import Usuario

load_dotenv()


def achar_usuario_supabase(email: str) -> dict | None:
    """Procura a conta no Supabase Auth pelo email, via Admin API (paginado)."""
    url = os.environ["SUPABASE_URL"].rstrip("/")
    chave = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": chave, "Authorization": f"Bearer {chave}"}
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


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: bootstrap_admin.py <email>")
        sys.exit(2)
    email = sys.argv[1].strip()

    conta = achar_usuario_supabase(email)
    if conta is None:
        print(
            f"ERRO: não encontrei a conta '{email}' no Supabase Auth. "
            "Crie-a no painel (Authentication → Users) antes."
        )
        sys.exit(1)

    sub = conta["id"]
    confirmado = bool(conta.get("email_confirmed_at") or conta.get("confirmed_at"))
    print(f"Conta Supabase encontrada: id={sub}  confirmado={'sim' if confirmado else 'NÃO'}")

    with Session(engine) as sessao:
        usuario = sessao.scalars(select(Usuario).where(Usuario.email == email)).first()
        if usuario:
            usuario.auth_id = uuid.UUID(sub)
            usuario.ativo = True
            acao = "atualizado"
        else:
            sessao.add(
                Usuario(
                    nome=email.split("@")[0],
                    email=email,
                    auth_id=uuid.UUID(sub),
                    ativo=True,
                )
            )
            acao = "criado"
        sessao.commit()

    print(f"OK: usuário admin {acao} no Batuta (auth_id ligado, ativo). Pronto para logar.")
    if not confirmado:
        print(
            "ATENÇÃO: o email ainda NÃO está confirmado no Supabase. "
            "Confirme (link do email ou 'Confirm' no painel) antes de tentar logar."
        )


if __name__ == "__main__":
    main()
