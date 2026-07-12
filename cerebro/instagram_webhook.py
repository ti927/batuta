"""Helpers do webhook de COMENTÁRIOS do Instagram (GAP 2) — sem tocar o núcleo.

A Meta entrega os comentários de TODAS as contas conectadas numa ÚNICA URL de
callback no nível do app (`/instagram/webhook`, ver `rotas/instagram_webhook.py`).
Aqui vivem as peças puras (sem banco) que o receptor usa:

- `token_de_verificacao` / `verificar_assinatura`: a segurança das duas pontas do
  webhook — o handshake de verificação (GET) e a assinatura `X-Hub-Signature-256`
  (POST), calculada com o app secret que já temos (`INSTAGRAM_APP_SECRET`).
- `extrair_comentarios`: normaliza o corpo cru da Meta (`entry[].changes[]`) numa
  lista de comentários neutros — a topologia do payload fica ISOLADA aqui.
- `montar_entrada`: monta o bloco de texto que vira a entrada da execução (o núcleo
  só passa texto adiante — PRODUTO/BUILD-PLAN; por isso os campos vão rotulados).
- `inscrever_conta`: assina o campo `comments` para UMA conta no ato do OAuth, para
  a Meta passar a entregar os comentários dela.

Mesmo padrão httpx/`FalhaInstrumento` de `instagram_oauth.py`, ao lado do qual mora.
"""

import hashlib
import hmac
import os

import httpx

import instagram_oauth
import instagram_tokens
from instrumentos.base import FalhaInstrumento

API = "https://graph.instagram.com/v23.0"
TIMEOUT_S = 20.0

# O campo do webhook que o Batuta assina (comentários). DM/mensagens ficam de fora
# (o Batuta não faz DM — bate com o App Review).
CAMPO_INSCRICAO = "comments"


# ─────────────────────────── Segurança do webhook ───────────────────────────


def token_de_verificacao() -> str:
    """O segredo do handshake de verificação (GET). Tem de bater com o valor
    cadastrado no painel da Meta. Vazio = webhook não configurado no servidor."""
    return os.environ.get("INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "").strip()


def verificar_assinatura(corpo: bytes, header: str | None) -> bool:
    """True se `X-Hub-Signature-256` bate com o HMAC-SHA256 do corpo CRU usando o
    app secret. Sem app secret configurado, ou header ausente/malformado, é False
    (o receptor recusa) — não confiamos em nada que não possamos verificar."""
    _, app_secret, _ = instagram_oauth._config()
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    esperado = hmac.new(app_secret.encode(), corpo, hashlib.sha256).hexdigest()
    recebido = header.split("=", 1)[1].strip()
    return hmac.compare_digest(esperado, recebido)


# ──────────────────────── Leitura do payload da Meta ─────────────────────────


def extrair_comentarios(corpo: dict | None) -> list[dict]:
    """Normaliza o corpo do webhook numa lista de comentários neutros.

    Cada item: `{ig_user_id, comment_id, texto, media_id, autor_id, autor_nome,
    parent_id}`. `ig_user_id` é a CONTA que recebeu o comentário (entry.id);
    `parent_id` presente = é resposta a outro comentário (o receptor usa isso no
    anti-loop). Ignora mudanças que não sejam do campo `comments`."""
    if not isinstance(corpo, dict) or corpo.get("object") != "instagram":
        return []
    saida: list[dict] = []
    for entry in corpo.get("entry") or []:
        ig_user_id = str((entry or {}).get("id") or "")
        for change in (entry or {}).get("changes") or []:
            if (change or {}).get("field") != "comments":
                continue
            v = (change or {}).get("value") or {}
            cid = str(v.get("id") or "")
            if not ig_user_id or not cid:
                continue
            frm = v.get("from") or {}
            media = v.get("media") or {}
            saida.append(
                {
                    "ig_user_id": ig_user_id,
                    "comment_id": cid,
                    "texto": v.get("text") or "",
                    "media_id": str(media.get("id") or "") or None,
                    "autor_id": str(frm.get("id") or "") or None,
                    "autor_nome": frm.get("username") or None,
                    "parent_id": str(v.get("parent_id") or "") or None,
                }
            )
    return saida


def montar_entrada(comentario: dict) -> str:
    """O bloco de texto que vira a entrada da execução. Como o motor só passa
    TEXTO adiante (núcleo congelado), os campos estruturais (comment_id/media_id)
    vão rotulados — o agente copia o `comment_id` para o instrumento de resposta."""
    autor = comentario.get("autor_nome")
    autor_txt = f"@{autor}" if autor else "(não informado)"
    return (
        "[COMENTÁRIO DO INSTAGRAM]\n"
        f"comment_id: {comentario['comment_id']}\n"
        f"media_id: {comentario.get('media_id') or '(não informado)'}\n"
        f"autor: {autor_txt}\n"
        f"texto: {comentario.get('texto') or ''}\n\n"
        "[INSTRUÇÃO]\n"
        'Você recebeu um novo comentário no Instagram (dados acima). Se for responder, '
        'use o instrumento "instagram_responder_comentario" com acao="responder", '
        "comment_id=<o comment_id acima> e mensagem=<sua resposta>. Se a automação "
        "tiver um portão de aprovação, sua resposta vira um rascunho e só é publicada "
        "depois que um humano aprovar."
    )


# ─────────────────────── Inscrição da conta (no OAuth) ───────────────────────


def inscrever_conta(token: str, ig_user_id: str) -> None:
    """Assina o campo `comments` para ESTA conta, para a Meta passar a entregar os
    comentários dela ao nosso receptor. Chamado no callback do OAuth em best-effort
    (o chamador engole a falha para não derrubar a conexão). Idempotente do lado da
    Meta: reconectar re-afirma a inscrição."""
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            resposta = cliente.post(
                f"{API}/{ig_user_id}/subscribed_apps",
                params={"subscribed_fields": CAMPO_INSCRICAO, "access_token": token},
            )
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível assinar o webhook de comentários: {e}", retentavel=True
        )
    instagram_tokens._tratar_falha(resposta)
