"""Diagnóstico read-only do fuso de uma execução agendada. NÃO escreve nada.

Uso: uv run python scripts/diag_fuso.py <execucao_id>
Mostra os timestamps BRUTOS (UTC, como gravados) e a config do gatilho, para
decidir se o cron disparou no fuso certo ou se é bug de exibição.
"""

import os
import sys
from datetime import timezone
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

from modelos import Automacao, Execucao  # noqa: E402
from sessao import CriadorDeSessao  # noqa: E402

load_dotenv()
BRT = ZoneInfo("America/Sao_Paulo")


def _mostra(rotulo, dt):
    if dt is None:
        print(f"{rotulo}: None")
        return
    # Garante leitura como UTC se vier naive
    utc = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    print(
        f"{rotulo}: bruto={dt!r}  UTC={utc.astimezone(timezone.utc):%Y-%m-%d %H:%M:%S %Z}"
        f"  BRT={utc.astimezone(BRT):%Y-%m-%d %H:%M:%S %Z}"
    )


def main(exec_id: str) -> None:
    with CriadorDeSessao() as s:
        ex = s.get(Execucao, exec_id)
        if ex is None:
            print(f"Execução {exec_id} NÃO encontrada.")
            return
        print(f"=== EXECUÇÃO {ex.id} | estado={ex.estado} ===")
        _mostra("criado_em   ", ex.criado_em)
        _mostra("iniciada_em ", ex.iniciada_em)
        _mostra("finalizada_em", ex.finalizada_em)
        print(f"automacao_id: {ex.automacao_id}")

        auto = s.get(Automacao, ex.automacao_id) if ex.automacao_id else None
        if auto is None:
            print("Automação não encontrada (avulsa?).")
            return
        print(f"\n=== AUTOMAÇÃO {auto.id} | ativa={auto.ativa} ===")
        print(f"tipo_gatilho: {auto.tipo_gatilho}")
        print(f"configuracao_gatilho: {auto.configuracao_gatilho}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python scripts/diag_fuso.py <execucao_id>")
        sys.exit(1)
    main(sys.argv[1])
