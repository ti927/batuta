"""Lista (só leitura) times e conversas da IA criadora de uma organização.

Para identificar criações recentes (ex.: um time montado na org errada).
Ferramenta de teste.

Uso (da pasta cerebro/):  uv run python scripts/listar_criacoes_recentes.py <organizacao>
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import engine
from modelos import Agente, Automacao, ConversaCriacao, Organizacao, Time

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

        print(f"Org: {alvo.nome}  [{alvo.id}]\n")

        times = s.scalars(
            select(Time)
            .where(Time.organizacao_id == alvo.id)
            .order_by(Time.criado_em.desc())
        ).all()
        print(f"TIMES ({len(times)}), mais recentes primeiro:")
        for t in times:
            n = s.scalars(select(Agente).where(Agente.time_id == t.id)).all()
            autos = s.scalars(
                select(Automacao).where(Automacao.time_id == t.id)
            ).all()
            print(f"  - {t.nome!r}  criado_em={t.criado_em}  agentes={len(n)}  [{t.id}]")
            for a in autos:
                print(
                    f"      automação: {a.nome!r}  gatilho={a.tipo_gatilho}  "
                    f"ativa={a.ativa}"
                )

        convs = s.scalars(
            select(ConversaCriacao)
            .where(ConversaCriacao.organizacao_id == alvo.id)
            .order_by(ConversaCriacao.criado_em.desc())
        ).all()
        print(f"\nCONVERSAS DA IA ({len(convs)}), mais recentes primeiro:")
        for c in convs:
            print(
                f"  - titulo={c.titulo!r}  criado_em={c.criado_em}  "
                f"time_id={c.time_id}  [{c.id}]"
            )


if __name__ == "__main__":
    main()
