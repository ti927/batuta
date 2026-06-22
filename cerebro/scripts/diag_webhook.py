"""Diagnóstico read-only: config dos instrumentos disparar_webhook de um time.

Uso: uv run python scripts/diag_webhook.py <execucao_id>
Mostra a URL e os cabeçalhos configurados (onde um acento quebra o httpx).
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import select  # noqa: E402

from modelos import Automacao, Execucao, Instrumento  # noqa: E402
from sessao import CriadorDeSessao  # noqa: E402

load_dotenv()


def main(exec_id: str) -> None:
    with CriadorDeSessao() as s:
        ex = s.get(Execucao, exec_id)
        if ex is None:
            print("execução não encontrada")
            return
        auto = s.get(Automacao, ex.automacao_id) if ex.automacao_id else None
        if auto is None:
            print("automação não encontrada")
            return
        insts = s.scalars(
            select(Instrumento).where(
                Instrumento.time_id == auto.time_id,
                Instrumento.tipo == "disparar_webhook",
            )
        ).all()
        print(f"time_id={auto.time_id}  instrumentos disparar_webhook: {len(insts)}")
        for i in insts:
            cfg = i.configuracao or {}
            print(f"\n=== {i.nome} (id8={i.id.hex[:8]}) ===")
            print(f"url: {cfg.get('url')!r}")
            cabecalhos = cfg.get("cabecalhos") or {}
            print(f"cabecalhos: {cabecalhos!r}")
            for k, v in cabecalhos.items():
                nao_ascii = [c for c in str(v) if ord(c) > 127]
                if nao_ascii:
                    print(f"  ⚠ cabeçalho '{k}' tem caractere não-ASCII: {nao_ascii}")
            # url não-ascii?
            nao_ascii_url = [c for c in str(cfg.get("url") or "") if ord(c) > 127]
            if nao_ascii_url:
                print(f"  ⚠ URL tem caractere não-ASCII: {nao_ascii_url}")


if __name__ == "__main__":
    main(sys.argv[1])
