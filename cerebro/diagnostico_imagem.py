"""Vigia dos instrumentos de imagem — registra EXATAMENTE o que é transmitido à API
de imagem da OpenAI, para diagnóstico.

Motivação: provar, com fato (não suposição), se a imagem-base vai para a OpenAI como
ANEXO (bytes no multipart `image[]`) ou não — e quantos bytes. A cada chamada,
sobrescreve um JSON de nome FIXO por instrumento no Supabase Storage (bucket público),
que dá para ler depois pela URL. Best-effort: NUNCA derruba o instrumento (se o vigia
falhar, a geração segue normal).

Para LER depois: `uv run python scripts/ler_diagnostico_imagem.py` (lê pelo endpoint
autenticado, sem cache de CDN).
"""

import json
import logging
from datetime import datetime, timezone

import arquivos

logger = logging.getLogger("batuta.diagnostico_imagem")


def registrar(
    instrumento: str,
    endpoint: str,
    metodo: str,
    campos: dict,
    imagens: list[dict],
    observacao: str = "",
) -> str | None:
    """Grava o diagnóstico de UMA chamada à API de imagem.

    `imagens`: lista de dicts por imagem de entrada, cada um com `origem_url`,
    `content_type`, `bytes_anexados` (tamanho real dos bytes no multipart) e
    `enviado_como`. Lista vazia = nenhuma imagem de entrada (instrumento texto→imagem).
    Devolve a URL do JSON, ou None se o vigia falhar (best-effort)."""
    registro = {
        "instrumento": instrumento,
        "quando_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "metodo": metodo,
        "campos": campos,
        "imagens_de_entrada": imagens,
        "total_imagens_anexadas": sum(1 for i in imagens if i.get("bytes_anexados")),
        "observacao": observacao,
    }
    try:
        conteudo = json.dumps(registro, ensure_ascii=False, indent=2).encode("utf-8")
        url = arquivos.salvar(
            f"diagnostico-{instrumento}.json", conteudo, "application/json"
        )
        logger.warning(
            "VIGIA imagem [%s]: %d imagem(ns) anexada(s); registro em %s",
            instrumento,
            registro["total_imagens_anexadas"],
            url,
        )
        return url
    except Exception:
        logger.exception("VIGIA imagem: falha ao registrar diagnóstico de %s", instrumento)
        return None
