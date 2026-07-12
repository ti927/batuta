"""Instrumento "Responder / moderar comentário no Instagram" (Fase 3 — escrita).

Responde a um comentário OU o oculta / reexibe / apaga, pela Instagram API with
Instagram Login (`graph.instagram.com`). Ação irreversível → exige portão de
aprovação. O par é o `instagram_ler_comentarios` (leitura).

IDEMPOTÊNCIA: responder NÃO é idempotente (re-chamar comenta de novo). Como a
orquestração reexecuta um instrumento em falha RETENTÁVEL, aqui TODAS as falhas
são NÃO-retentáveis — nunca reage duas vezes por reexecução.
"""

from typing import Literal

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

API = "https://graph.instagram.com/v23.0"
TIMEOUT_S = 20.0
MAX_RESPOSTA = 2200


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


def _conferir(resposta: httpx.Response) -> None:
    """Qualquer falha é NÃO-retentável (idempotência: ver módulo)."""
    if not resposta.is_success:
        raise FalhaInstrumento(
            f"o Instagram recusou a operação (HTTP {resposta.status_code}): "
            f"{_detalhe_erro(resposta)}",
            retentavel=False,
        )


def _post(cli: httpx.Client, url: str, dados: dict) -> dict:
    try:
        r = cli.post(url, data=dados)
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível falar com o Instagram: {e}", retentavel=False
        )
    _conferir(r)
    return r.json()


def _delete(cli: httpx.Client, url: str, params: dict) -> dict:
    try:
        r = cli.delete(url, params=params)
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível falar com o Instagram: {e}", retentavel=False
        )
    _conferir(r)
    return r.json()


class ConfigResponderComentario(BaseModel):
    """Vem da credencial `instagram` (nomes batem com a credencial)."""

    ig_user_id: str = Field(
        default="", description="ID da conta Instagram (vem da credencial)."
    )
    token: str = Field(
        default="",
        description="Token de acesso do Instagram (segredo; vem da credencial).",
    )


class ArgsResponderComentario(BaseModel):
    """O que a IA passa: em qual comentário agir, qual ação e (se responder) o texto."""

    comment_id: str = Field(min_length=1, description="ID do comentário alvo.")
    acao: Literal["responder", "ocultar", "reexibir", "apagar"] = Field(
        default="responder",
        description="responder = publica uma resposta; ocultar/reexibir = esconde ou "
        "mostra o comentário; apagar = remove o comentário (não dá para desfazer).",
    )
    mensagem: str = Field(
        default="", description="Texto da resposta (obrigatório só para acao=responder)."
    )


class InstagramResponderComentario(TipoInstrumento):
    tipo = "instagram_responder_comentario"
    categoria = "Instagram"
    nome_exibicao = "Instagram: responder ou moderar comentário"
    descricao = (
        "Age sobre um comentário do Instagram: responde (publica uma resposta), "
        "oculta, reexibe ou apaga. Acione com o id do comentário e a ação; para "
        "responder, passe também a mensagem."
    )
    Config = ConfigResponderComentario
    Args = ArgsResponderComentario
    campos_secretos = ("token",)
    tipos_credencial_aceitos = ("instagram",)
    acao_irreversivel = True  # age publicamente — exige portão de aprovação

    def executar(
        self, config: ConfigResponderComentario, args: ArgsResponderComentario
    ) -> dict:
        if not config.token:
            raise FalhaInstrumento(
                "o Instagram não está conectado — configure a credencial 'instagram'.",
                retentavel=False,
            )
        with httpx.Client(timeout=TIMEOUT_S) as cli:
            if args.acao == "responder":
                msg = (args.mensagem or "").strip()[:MAX_RESPOSTA]
                if not msg:
                    raise FalhaInstrumento(
                        "a resposta veio vazia — escreva o texto da resposta.",
                        retentavel=False,
                    )
                r = _post(
                    cli,
                    f"{API}/{args.comment_id}/replies",
                    {"message": msg, "access_token": config.token},
                )
                return {
                    "ok": True,
                    "acao": "responder",
                    "comentario_id": args.comment_id,
                    "resposta_id": r.get("id"),
                }
            if args.acao in ("ocultar", "reexibir"):
                _post(
                    cli,
                    f"{API}/{args.comment_id}",
                    {
                        "hide": "true" if args.acao == "ocultar" else "false",
                        "access_token": config.token,
                    },
                )
                return {"ok": True, "acao": args.acao, "comentario_id": args.comment_id}
            # apagar
            _delete(
                cli, f"{API}/{args.comment_id}", {"access_token": config.token}
            )
            return {"ok": True, "acao": "apagar", "comentario_id": args.comment_id}


registrar(InstagramResponderComentario())
