"""Instrumento "Ler comentários do Instagram" (Fase 3 — leitura).

Lê os comentários de um post do Instagram (texto, autor, data, curtidas), pela
Instagram API with Instagram Login (`graph.instagram.com`). Só leitura → não
exige portão de aprovação. O par é o `instagram_responder_comentario` (escrita).
"""

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

API = "https://graph.instagram.com/v23.0"
TIMEOUT_S = 20.0
CAMPOS = "id,text,username,timestamp,like_count"


def _detalhe_erro(resposta: httpx.Response) -> str:
    try:
        dados = resposta.json()
        if isinstance(dados, dict):
            erro = dados.get("error")
            if isinstance(erro, dict):
                return str(erro.get("message") or erro)[:200]
            return str(dados.get("message") or dados)[:200]
    except Exception:
        pass
    return (resposta.text or "sem detalhe").strip()[:200]


def _get(cli: httpx.Client, url: str, params: dict) -> dict:
    """Leitura idempotente: 400/401/403 não-retentável; 429/5xx retentável."""
    try:
        r = cli.get(url, params=params)
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível falar com o Instagram: {e}", retentavel=True
        )
    status = r.status_code
    if status in (400, 401, 403):
        raise FalhaInstrumento(
            f"o Instagram recusou a consulta (HTTP {status}): {_detalhe_erro(r)}",
            retentavel=False,
        )
    if status == 429 or 500 <= status < 600:
        raise FalhaInstrumento(f"o Instagram respondeu HTTP {status}.", retentavel=True)
    if not r.is_success:
        raise FalhaInstrumento(
            f"a consulta ao Instagram falhou (HTTP {status}): {_detalhe_erro(r)}",
            retentavel=False,
        )
    return r.json()


class ConfigLerComentarios(BaseModel):
    """Vem da credencial `instagram` (nomes batem com a credencial)."""

    ig_user_id: str = Field(
        default="", description="ID da conta Instagram (vem da credencial)."
    )
    token: str = Field(
        default="",
        description="Token de acesso do Instagram (segredo; vem da credencial).",
    )


class ArgsLerComentarios(BaseModel):
    """O que a IA passa: de qual post ler os comentários e quantos."""

    media_id: str = Field(
        min_length=1,
        description="ID do post/mídia cujos comentários ler (ex.: o id devolvido ao "
        "publicar, ou da listagem de posts).",
    )
    limite: int = Field(
        default=20, ge=1, le=50, description="Quantos comentários trazer (1 a 50)."
    )


class InstagramLerComentarios(TipoInstrumento):
    tipo = "instagram_ler_comentarios"
    categoria = "Instagram"
    nome_exibicao = "Instagram: ler comentários"
    descricao = (
        "Lê os comentários de um post do Instagram (texto, autor, data e curtidas). "
        "Acione com o id do post. Só leitura."
    )
    Config = ConfigLerComentarios
    Args = ArgsLerComentarios
    campos_secretos = ("token",)
    tipos_credencial_aceitos = ("instagram",)

    def executar(
        self, config: ConfigLerComentarios, args: ArgsLerComentarios
    ) -> dict:
        if not config.token:
            raise FalhaInstrumento(
                "o Instagram não está conectado — configure a credencial 'instagram'.",
                retentavel=False,
            )
        with httpx.Client(timeout=TIMEOUT_S) as cli:
            dados = _get(
                cli,
                f"{API}/{args.media_id}/comments",
                {"fields": CAMPOS, "limit": args.limite, "access_token": config.token},
            )
        comentarios = [
            {
                "id": c.get("id"),
                "texto": c.get("text"),
                "autor": c.get("username"),
                "data": c.get("timestamp"),
                "curtidas": c.get("like_count"),
            }
            for c in (dados.get("data") or [])
        ]
        return {"ok": True, "media_id": args.media_id, "comentarios": comentarios}


registrar(InstagramLerComentarios())
