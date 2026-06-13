"""Acesso ao Supabase Storage (com a service role key), via httpx.

Usado só pelo cérebro — NUNCA exposto à interface (segredos só no cérebro,
CLAUDE §8). Hoje guarda a mídia recebida pelos canais (ex.: a foto de um recibo
que chega pelo Telegram), no bucket privado `mensagens`. Espelha o padrão do
`supabase_admin.py` (sem SDK).
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

TIMEOUT_S = 30.0
BUCKET_MENSAGENS = "mensagens"


class FalhaStorage(RuntimeError):
    """O Storage não respondeu como esperado (rede, permissão, objeto ausente)."""


def _base_e_headers() -> tuple[str, dict]:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    chave = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return url, {"apikey": chave, "Authorization": f"Bearer {chave}"}


def enviar(
    caminho: str, conteudo: bytes, content_type: str, *, bucket: str = BUCKET_MENSAGENS
) -> str:
    """Sobe um objeto para `bucket/caminho` (upsert). Devolve o caminho salvo."""
    url, headers = _base_e_headers()
    try:
        r = httpx.post(
            f"{url}/storage/v1/object/{bucket}/{caminho}",
            headers={**headers, "Content-Type": content_type, "x-upsert": "true"},
            content=conteudo,
            timeout=TIMEOUT_S,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise FalhaStorage(f"falha ao enviar {bucket}/{caminho}: {e}")
    return caminho


def baixar(caminho: str, *, bucket: str = BUCKET_MENSAGENS) -> bytes:
    """Baixa os bytes de `bucket/caminho`."""
    url, headers = _base_e_headers()
    try:
        r = httpx.get(
            f"{url}/storage/v1/object/{bucket}/{caminho}",
            headers=headers,
            timeout=TIMEOUT_S,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise FalhaStorage(f"falha ao baixar {bucket}/{caminho}: {e}")
    return r.content


def remover(caminho: str, *, bucket: str = BUCKET_MENSAGENS) -> None:
    """Remove um objeto (best-effort: não levanta se já não existe)."""
    url, headers = _base_e_headers()
    try:
        httpx.request(
            "DELETE",
            f"{url}/storage/v1/object/{bucket}/{caminho}",
            headers=headers,
            timeout=TIMEOUT_S,
        )
    except httpx.HTTPError:
        pass
