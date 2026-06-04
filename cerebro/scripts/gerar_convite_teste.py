"""Gera um link de convite de TESTE, sem depender do envio de e-mail.

Mina o link de convite direto pela Admin API do Supabase (generate_link — NÃO
dispara e-mail), grava o convite no Batuta e imprime a URL pronta para abrir no
navegador (janela anônima). Ferramenta de teste — não faz parte do produto.

Uso (a partir da pasta cerebro/):
    uv run python scripts/gerar_convite_teste.py <email> [papel] [organizacao]

  - papel: admin|operador|observador (padrão: operador)
  - organizacao: parte do nome OU o id; se omitido, lista as organizações.
"""

import os
import sys
import uuid  # noqa: F401 — usado indiretamente via modelos
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import engine
from modelos import Convite, Membro, Organizacao

load_dotenv()

BASE_INTERFACE = os.environ.get("URL_INTERFACE", "http://localhost:3000")


def gerar_link_supabase(email: str) -> tuple[str, str]:
    """Devolve (hashed_token, tipo). Tenta 'invite' (cria o usuário); se já
    existe, cai para 'magiclink'."""
    url = os.environ["SUPABASE_URL"].rstrip("/")
    chave = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {
        "apikey": chave,
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
    }
    r = httpx.post(
        f"{url}/auth/v1/admin/generate_link",
        headers=headers,
        json={"type": "invite", "email": email},
        timeout=20,
    )
    if r.status_code >= 400:
        r = httpx.post(
            f"{url}/auth/v1/admin/generate_link",
            headers=headers,
            json={"type": "magiclink", "email": email},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()["hashed_token"], "magiclink"
    return r.json()["hashed_token"], "invite"


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: gerar_convite_teste.py <email> [papel] [organizacao]")
        sys.exit(2)
    email = sys.argv[1].strip()
    papel = sys.argv[2].strip() if len(sys.argv) > 2 else "operador"
    org_ref = sys.argv[3].strip() if len(sys.argv) > 3 else None

    if papel not in ("admin", "operador", "observador"):
        print(f"papel inválido: {papel} (use admin|operador|observador)")
        sys.exit(2)

    with Session(engine) as sessao:
        orgs = sessao.scalars(select(Organizacao).order_by(Organizacao.nome)).all()
        if not orgs:
            print("Nenhuma organização no banco. Crie uma pela interface primeiro.")
            sys.exit(1)
        if not org_ref:
            print("Organizações disponíveis (rode de novo passando o nome ou id):")
            for o in orgs:
                print(f"  - {o.nome}  [{o.id}]")
            sys.exit(0)

        alvo = None
        for o in orgs:
            if str(o.id) == org_ref or org_ref.lower() in o.nome.lower():
                alvo = o
                break
        if alvo is None:
            print(f"Organização não encontrada: {org_ref}")
            sys.exit(1)

        admin_id = sessao.scalars(
            select(Membro.usuario_id).where(
                Membro.organizacao_id == alvo.id, Membro.papel == "admin"
            )
        ).first()

        hashed_token, tipo = gerar_link_supabase(email)

        sessao.add(
            Convite(
                email=email,
                organizacao_id=alvo.id,
                papel=papel,
                status="pendente",
                convidado_por_id=admin_id,
                expira_em=datetime.now(timezone.utc) + timedelta(days=7),
            )
        )
        sessao.commit()
        nome_org = alvo.nome

    link = (
        f"{BASE_INTERFACE}/auth/confirm"
        f"?token_hash={hashed_token}&type={tipo}&next=/convite"
    )
    print("\n=== CONVITE DE TESTE CRIADO ===")
    print(f"Organizacao: {nome_org}")
    print(f"Convidado:   {email}  (papel: {papel})")
    print("\nAbra este link numa JANELA ANONIMA:\n")
    print(link)
    print()


if __name__ == "__main__":
    main()
