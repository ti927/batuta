"""Inspeção read-only de uma execução (diagnóstico). NÃO escreve nada.

Uso: uv run python scripts/inspecionar_exec.py <execucao_id>
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Permite rodar de scripts/ achando os módulos do cérebro.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import select

from modelos import (
    Agente,
    AgenteInstrumento,
    Execucao,
    Instrumento,
    PassoExecucao,
)
from sessao import CriadorDeSessao

load_dotenv()


def _txt(v, limite=4000):
    s = "" if v is None else str(v)
    return s if len(s) <= limite else s[:limite] + f"… [+{len(s) - limite} chars]"


def main(exec_id: str) -> None:
    with CriadorDeSessao() as s:
        ex = s.get(Execucao, exec_id)
        if ex is None:
            print(f"Execução {exec_id} NÃO encontrada.")
            return
        print(f"=== EXECUÇÃO {ex.id} ===")
        print(f"estado: {ex.estado}")
        print(f"automacao_id: {ex.automacao_id}")
        print(f"entrada: {_txt(ex.entrada)}")
        print(f"resultado: {_txt(ex.resultado)}")
        print(f"iniciada_em: {ex.iniciada_em}  finalizada_em: {ex.finalizada_em}")

        passos = s.scalars(
            select(PassoExecucao)
            .where(PassoExecucao.execucao_id == ex.id)
            .order_by(PassoExecucao.ordem)
        ).all()
        nomes = {
            a.id: a.nome
            for a in s.scalars(select(Agente)).all()
        }
        print(f"\n=== {len(passos)} PASSOS ===")
        for p in passos:
            saida = p.saida or {}
            print(f"\n--- passo {p.ordem} | nó={p.no_id} | estado={p.estado} ---")
            print(f"agente: {nomes.get(p.agente_id, p.agente_id)}")
            print(f"ENTRADA: {_txt((p.entrada or {}).get('texto'))}")
            print(f"SAÍDA.texto: {_txt(saida.get('texto'))}")
            print(f"instrumentos_acionados: {saida.get('instrumentos_acionados')}")
            print(f"ramo_escolhido: {saida.get('ramo_escolhido')}")
            if saida.get("mensagens_enviadas"):
                print(f"mensagens_enviadas: {_txt(saida.get('mensagens_enviadas'))}")

        # Cinto de cada agente que apareceu nos passos (instrumentos: nome + tipo).
        agentes_ids = {p.agente_id for p in passos if p.agente_id}
        print("\n=== CINTO DOS AGENTES ===")
        for aid in agentes_ids:
            insts = s.scalars(
                select(Instrumento)
                .join(AgenteInstrumento, AgenteInstrumento.instrumento_id == Instrumento.id)
                .where(AgenteInstrumento.agente_id == aid)
            ).all()
            print(f"\nagente: {nomes.get(aid, aid)}")
            for i in insts:
                print(f"  - nome='{i.nome}' tipo={i.tipo} id8={i.id.hex[:8]} cfg={_txt(i.configuracao, 300)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python scripts/inspecionar_exec.py <execucao_id>")
        sys.exit(1)
    main(sys.argv[1])
