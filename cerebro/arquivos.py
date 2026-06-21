"""Arquivos gerados pelo cérebro (imagens do gerar_imagem, PDFs do gerar_pdf).

Em produção os arquivos vão para o **Supabase Storage**, num bucket PÚBLICO: a URL
é durável e acessível por terceiros — em especial a Meta, que BAIXA a imagem pela
URL ao publicar no Instagram. Reusa as credenciais do Supabase que o cérebro já
tem (as mesmas do Auth). Sem Supabase configurado (dev), os arquivos caem num
diretório local servido pelo próprio cérebro em `/arquivos` (efêmero no Railway —
some a cada deploy; por isso o Storage em produção). O diretório é ignorado pelo git.
"""

import logging
import os
from pathlib import Path

import httpx

DIRETORIO_ARQUIVOS = Path(__file__).resolve().parent / "arquivos"
DIRETORIO_ARQUIVOS.mkdir(exist_ok=True)

# Endereço público do cérebro, para o link do arquivo servido localmente (fallback).
BASE_PUBLICA = os.environ.get("CEREBRO_PUBLIC_URL", "http://localhost:8000").rstrip("/")

# Supabase Storage (bucket público) — reusa as credenciais já usadas no Auth.
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BUCKET = os.environ.get("SUPABASE_BUCKET_ARQUIVOS", "arquivos")
_TIMEOUT_S = 30.0

logger = logging.getLogger("batuta.arquivos")
_bucket_garantido = False


def url_do_arquivo(nome: str) -> str:
    """URL do arquivo servido localmente pelo cérebro (fallback de dev)."""
    return f"{BASE_PUBLICA}/arquivos/{nome}"


def storage_configurado() -> bool:
    return bool(_SUPABASE_URL and _SUPABASE_KEY)


def _headers() -> dict:
    return {"Authorization": f"Bearer {_SUPABASE_KEY}", "apikey": _SUPABASE_KEY}


def _garantir_bucket() -> None:
    """Cria o bucket PÚBLICO se ainda não existe (idempotente; roda uma vez)."""
    global _bucket_garantido
    if _bucket_garantido:
        return
    with httpx.Client(timeout=_TIMEOUT_S) as cli:
        r = cli.post(
            f"{_SUPABASE_URL}/storage/v1/bucket",
            headers=_headers(),
            json={"id": BUCKET, "name": BUCKET, "public": True},
        )
    # 200/201 = criado; já existir também é sucesso (idempotente).
    if r.status_code in (200, 201) or "exist" in (r.text or "").lower():
        _bucket_garantido = True
    else:
        logger.warning(
            "Bucket '%s' não confirmado (HTTP %s): %s",
            BUCKET, r.status_code, (r.text or "")[:200],
        )


def _url_publica(nome: str) -> str:
    return f"{_SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{nome}"


def salvar(
    nome: str, conteudo: bytes, content_type: str = "application/octet-stream"
) -> str:
    """Guarda um arquivo gerado e devolve a URL PÚBLICA para acessá-lo.

    Usa o Supabase Storage (bucket público — URL durável, acessível pela Meta e por
    terceiros) quando configurado; senão cai no disco local servido em `/arquivos`
    (dev). Se o upload ao Storage falhar, cai no disco (best-effort) e loga — a
    geração não é derrubada por uma oscilação do Storage."""
    if storage_configurado():
        try:
            _garantir_bucket()
            with httpx.Client(timeout=_TIMEOUT_S) as cli:
                r = cli.post(
                    f"{_SUPABASE_URL}/storage/v1/object/{BUCKET}/{nome}",
                    headers={**_headers(), "Content-Type": content_type, "x-upsert": "true"},
                    content=conteudo,
                )
            if r.is_success:
                return _url_publica(nome)
            logger.warning(
                "Upload ao Storage falhou (HTTP %s): %s", r.status_code, (r.text or "")[:200]
            )
        except httpx.HTTPError as e:
            logger.warning("Erro de rede no upload ao Storage: %s", e)
    # Fallback: disco local (dev, ou se o Storage falhar).
    DIRETORIO_ARQUIVOS.mkdir(exist_ok=True)
    (DIRETORIO_ARQUIVOS / nome).write_bytes(conteudo)
    return url_do_arquivo(nome)
