"""Lê os diagnósticos do vigia de imagem (diagnostico_imagem) gravados no Storage.

Usa o endpoint AUTENTICADO do Supabase (sem cache de CDN), então sempre traz a
ÚLTIMA chamada. Uso: uv run python scripts/ler_diagnostico_imagem.py
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BUCKET = os.environ.get("SUPABASE_BUCKET_ARQUIVOS", "arquivos")


def main() -> None:
    headers = {"Authorization": f"Bearer {KEY}", "apikey": KEY}
    for nome in ("diagnostico-montar_imagem.json", "diagnostico-gerar_imagem.json"):
        r = httpx.get(f"{URL}/storage/v1/object/{BUCKET}/{nome}", headers=headers)
        print(f"=== {nome} (HTTP {r.status_code}) ===")
        if r.is_success:
            print(r.text)
        else:
            print("(ainda não existe — rode uma execução de imagem primeiro)")
        print()


if __name__ == "__main__":
    main()
