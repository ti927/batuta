"""Instrumento "Instagram — conteúdo e métricas" (Fase 2 — instrumentos de Instagram).

Lê (sem alterar nada) a conta e os posts recentes do Instagram: usuário, tipo de
conta e total de publicações; e, por post, o tipo, a legenda, o link, a data e os
números de curtidas e comentários. Usa a Instagram API with Instagram Login
(`graph.instagram.com`) com a credencial `instagram`.

LIMITE (decisão do plano, confirmada pela própria Meta): RASTREAR HASHTAGS e os
INSIGHTS avançados (alcance, impressões, visualizações) exigem o setup "API com
login do Facebook" (`graph.facebook.com`) — sub-fase futura. Este instrumento
entrega o que o login do Instagram já dá: conta + posts + engajamento básico
(curtidas/comentários). Só leitura → não exige portão de aprovação.
"""

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

API = "https://graph.instagram.com/v23.0"
TIMEOUT_S = 20.0
CAMPOS_MIDIA = "id,caption,media_type,permalink,timestamp,like_count,comments_count"


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


class ConfigInstagramInsights(BaseModel):
    """Vem da credencial `instagram`: a conta e o token (nomes batem com a credencial)."""

    ig_user_id: str = Field(
        default="", description="ID da conta Instagram (vem da credencial)."
    )
    token: str = Field(
        default="",
        description="Token de acesso do Instagram (segredo; vem da credencial).",
    )


class ArgsInstagramInsights(BaseModel):
    """O que a IA passa: quantos posts recentes trazer."""

    limite: int = Field(
        default=10, ge=1, le=25, description="Quantos posts recentes ler (1 a 25)."
    )


class InstagramInsights(TipoInstrumento):
    tipo = "instagram_insights"
    nome_exibicao = "Instagram — conteúdo e métricas"
    descricao = (
        "Lê a conta do Instagram e os posts recentes (tipo, legenda, link, data, "
        "curtidas e comentários). Use para acompanhar o desempenho dos posts. Só "
        "leitura. (Hashtags e métricas avançadas de alcance ainda não estão "
        "disponíveis por este caminho.)"
    )
    Config = ConfigInstagramInsights
    Args = ArgsInstagramInsights
    campos_secretos = ("token",)
    tipos_credencial_aceitos = ("instagram",)

    def executar(
        self, config: ConfigInstagramInsights, args: ArgsInstagramInsights
    ) -> dict:
        if not (config.token and config.ig_user_id):
            raise FalhaInstrumento(
                "o Instagram não está conectado — configure a credencial 'instagram' "
                "(token + conta).",
                retentavel=False,
            )
        with httpx.Client(timeout=TIMEOUT_S) as cli:
            conta = _get(
                cli,
                f"{API}/{config.ig_user_id}",
                {"fields": "username,account_type,media_count", "access_token": config.token},
            )
            midia = _get(
                cli,
                f"{API}/{config.ig_user_id}/media",
                {"fields": CAMPOS_MIDIA, "limit": args.limite, "access_token": config.token},
            )
        posts = [
            {
                "id": m.get("id"),
                "tipo": m.get("media_type"),
                "legenda": (m.get("caption") or "")[:300],
                "link": m.get("permalink"),
                "data": m.get("timestamp"),
                "curtidas": m.get("like_count"),
                "comentarios": m.get("comments_count"),
            }
            for m in (midia.get("data") or [])
        ]
        return {
            "ok": True,
            "conta": {
                "usuario": conta.get("username"),
                "tipo_conta": conta.get("account_type"),
                "total_posts": conta.get("media_count"),
            },
            "posts": posts,
        }


registrar(InstagramInsights())
