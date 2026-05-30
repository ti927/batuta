"""Arquivos gerados pelo cérebro (ex.: PDFs de instrumentos).

No core, os arquivos ficam num diretório local servido pelo próprio cérebro em
`/arquivos`. É autossuficiente (sem storage externo) para provar o instrumento;
na Etapa 2 isso migra para o Supabase Storage. O diretório é ignorado pelo git.
"""

import os
from pathlib import Path

DIRETORIO_ARQUIVOS = Path(__file__).resolve().parent / "arquivos"
DIRETORIO_ARQUIVOS.mkdir(exist_ok=True)

# Endereço público do cérebro, para montar o link do arquivo.
BASE_PUBLICA = os.environ.get("CEREBRO_PUBLIC_URL", "http://localhost:8000").rstrip(
    "/"
)


def url_do_arquivo(nome: str) -> str:
    return f"{BASE_PUBLICA}/arquivos/{nome}"
