"""Começar do zero (Fase 6, Tarefa 6.8) — decisão do maestro.

Apaga TODOS os dados de negócio (organizações, times, agentes, instrumentos,
automações, execuções, passos, membros, convites, auditoria), MANTENDO a
estrutura (tabelas) e os usuários já ligados a uma conta real do Supabase
(auth_id != null — ex.: o admin do bootstrap). Remove o usuário fixo de testes
(auth_id null), encerrando a Etapa 1.

DESTRUTIVO e IRREVERSÍVEL. Exige a flag --confirmar.

Uso:  uv run python scripts/iniciar_do_zero.py --confirmar
"""

import os
import sys

# Permite rodar de scripts/ achando os módulos do cérebro.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from db import engine

# Tabelas de negócio a esvaziar (o CASCADE cobre dependências; usuarios fica fora).
TABELAS = [
    "passos_execucao",
    "execucoes",
    "automacoes",
    "agente_instrumentos",
    "instrumentos",
    "agentes",
    "times",
    "membros",
    "convites",
    "auditoria",
    "organizacoes",
]


def main() -> None:
    if "--confirmar" not in sys.argv:
        print(
            "DESTRUTIVO: apaga TODOS os dados de negócio (mantém estrutura e o admin "
            "real). Rode com --confirmar para executar."
        )
        sys.exit(2)
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE " + ", ".join(TABELAS) + " RESTART IDENTITY CASCADE")
        )
        apagados = conn.execute(
            text("DELETE FROM usuarios WHERE auth_id IS NULL")
        ).rowcount
        restantes = conn.execute(text("SELECT count(*) FROM usuarios")).scalar()
    print(f"Dados de negócio apagados. Usuários sem conta real removidos: {apagados}.")
    print(f"Usuários mantidos (com conta real ligada): {restantes}.")
    print("Estrutura (tabelas) preservada. Batuta pronto para começar do zero.")


if __name__ == "__main__":
    main()
