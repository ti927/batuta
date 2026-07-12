"""Instrumento "Ler post do Instagram" — leitura do CONTEÚDO de um post.

Dado o id de um post (o `media_id` que o gatilho `comentario_instagram` entrega,
ou o id devolvido ao publicar), lê a LEGENDA, o tipo de mídia, o link e os
contadores. Serve para o agente responder um comentário COM o contexto do post,
em vez de só com o texto isolado do comentário. Pela Instagram API with Instagram
Login (`graph.instagram.com`). Só leitura → não exige portão. Complementa
`instagram_ler_comentarios` (os comentários) e o gatilho de comentário.
"""

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

API = "https://graph.instagram.com/v23.0"
TIMEOUT_S = 20.0
CAMPOS = (
    "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,"
    "like_count,comments_count"
)


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


class ConfigLerPost(BaseModel):
    """Vem da credencial `instagram` (nomes batem com a credencial)."""

    ig_user_id: str = Field(
        default="", description="ID da conta Instagram (vem da credencial)."
    )
    token: str = Field(
        default="",
        description="Token de acesso do Instagram (segredo; vem da credencial).",
    )


class ArgsLerPost(BaseModel):
    """O que a IA passa: de qual post ler o conteúdo."""

    media_id: str = Field(
        min_length=1,
        description="ID do post/mídia a ler (o media_id que o gatilho de comentário "
        "entrega, ou o id devolvido ao publicar).",
    )


class InstagramLerPost(TipoInstrumento):
    tipo = "instagram_ler_post"
    categoria = "Instagram"
    nome_exibicao = "Instagram: ler post"
    descricao = (
        "Lê o conteúdo de um post do Instagram (legenda, tipo, URL da imagem, link, "
        "curtidas e nº de comentários) a partir do id do post. Use para responder um "
        "comentário COM o contexto do post; a URL da imagem pode ir para o instrumento "
        "'Descrever/ler imagem' para o agente enxergar a foto. Só leitura."
    )
    Config = ConfigLerPost
    Args = ArgsLerPost
    campos_secretos = ("token",)
    tipos_credencial_aceitos = ("instagram",)

    def executar(self, config: ConfigLerPost, args: ArgsLerPost) -> dict:
        if not config.token:
            raise FalhaInstrumento(
                "o Instagram não está conectado — configure a credencial 'instagram'.",
                retentavel=False,
            )
        with httpx.Client(timeout=TIMEOUT_S) as cli:
            dados = _get(
                cli,
                f"{API}/{args.media_id}",
                {"fields": CAMPOS, "access_token": config.token},
            )
        return {
            "ok": True,
            "post": {
                "id": dados.get("id"),
                "legenda": dados.get("caption"),
                "tipo": dados.get("media_type"),
                # URL da mídia: para FOTO é a própria imagem; para VÍDEO/REELS é o
                # vídeo (use a `miniatura` como imagem). Serve para o agente "ver" a
                # imagem via o instrumento "Descrever/ler imagem".
                "imagem": dados.get("media_url"),
                "miniatura": dados.get("thumbnail_url"),
                "link": dados.get("permalink"),
                "data": dados.get("timestamp"),
                "curtidas": dados.get("like_count"),
                "comentarios": dados.get("comments_count"),
            },
        }


registrar(InstagramLerPost())
