"""Lista (só leitura) as credenciais de uma organização, para conferência.

Mostra nome, tipo, resumo (mascarado — nunca o segredo) e validade. Ferramenta de
teste.

Uso (da pasta cerebro/):  uv run python scripts/verificar_credenciais.py <organizacao>
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import engine
from modelos import Credencial, Organizacao

load_dotenv(os.path.join(RAIZ, ".env"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main() -> None:
    org_ref = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    with Session(engine) as s:
        orgs = s.scalars(select(Organizacao)).all()
        alvo = None
        for o in orgs:
            if str(o.id) == org_ref or (org_ref and org_ref.lower() in (o.nome or "").lower()):
                alvo = o
                break
        if alvo is None:
            print(f"Organização não encontrada: {org_ref}")
            print("Existentes:", [o.nome for o in orgs])
            sys.exit(1)

        creds = s.scalars(
            select(Credencial).where(Credencial.organizacao_id == alvo.id)
        ).all()
        print(f"Org: {alvo.nome}  [{alvo.id}]")
        print(f"Credenciais: {len(creds)}")
        for c in creds:
            print(f"  - nome={c.nome!r}  tipo={c.tipo!r}  expira_em={c.expira_em}")
            print(f"    resumo={c.resumo}")


if __name__ == "__main__":
    main()
