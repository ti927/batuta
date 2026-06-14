"""Adaptador do canal Telegram (Bot API).

Isola o formato da Bot API do resto da mensageria: traduz um `update` recebido
para um `MensagemEntrante` neutro, envia mensagens, e registra/limpa o webhook.
O envio reusa o instrumento `enviar_telegram` (mesma política de retentativa e de
erro). Áudio/mídia entra na Fase H (transcrição); aqui só detecta e marca.
"""

from dataclasses import dataclass

import httpx

from instrumentos.base import acionar_com_retentativa
from instrumentos.enviar_telegram import ArgsTelegram, ConfigTelegram, EnviarTelegram

API_BASE = "https://api.telegram.org"
TIMEOUT_S = 15.0

_ENVIAR = EnviarTelegram()


@dataclass
class MensagemEntrante:
    """Uma mensagem recebida, já no formato neutro da mensageria."""

    contato_chave: str  # chat_id (string)
    contato_nome: str | None
    texto: str | None
    midia: dict | None = None  # {tipo, file_id} quando não é texto (Fase H)


def _nome_do_remetente(frm: dict) -> str | None:
    if not frm:
        return None
    nome = " ".join(p for p in (frm.get("first_name"), frm.get("last_name")) if p)
    return nome or frm.get("username") or None


def extrair_update(corpo: dict) -> MensagemEntrante | None:
    """Traduz um update do Telegram para `MensagemEntrante`. Devolve None para
    updates que não são uma mensagem tratável (ex.: status, edição vazia)."""
    if not isinstance(corpo, dict):
        return None
    msg = corpo.get("message") or corpo.get("edited_message")
    if not isinstance(msg, dict):
        return None
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return None
    nome = _nome_do_remetente(msg.get("from") or {})

    texto = msg.get("text")
    if texto:
        return MensagemEntrante(str(chat_id), nome, texto, None)

    # Voz/áudio: marca a mídia (a transcrição entra na Fase H). Outros tipos
    # caem como mídia genérica para um tratamento gentil mais adiante.
    voz = msg.get("voice") or msg.get("audio")
    if voz:
        return MensagemEntrante(
            str(chat_id), nome, None, {"tipo": "voz", "file_id": voz.get("file_id")}
        )
    if any(k in msg for k in ("photo", "document", "sticker", "video", "location")):
        return MensagemEntrante(str(chat_id), nome, None, {"tipo": "outro"})
    return None


def enviar(token: str, chat_id: str, texto: str) -> dict:
    """Envia uma mensagem pelo bot. Reusa o instrumento `enviar_telegram` (com
    retentativa). Levanta `FalhaInstrumento` se não conseguir entregar."""
    return acionar_com_retentativa(
        _ENVIAR,
        ConfigTelegram(token_bot=token),
        ArgsTelegram(destinatario=str(chat_id), mensagem=texto),
    )


def configurar_webhook(token: str, url: str, secret: str) -> dict:
    """Registra o webhook do bot apontando para `url`, com `secret_token` (o
    Telegram passa esse segredo no cabeçalho a cada chamada — valida a origem).
    Restringe a updates de mensagem."""
    with httpx.Client(timeout=TIMEOUT_S) as cliente:
        resposta = cliente.post(
            f"{API_BASE}/bot{token}/setWebhook",
            json={
                "url": url,
                "secret_token": secret,
                "allowed_updates": ["message", "edited_message"],
            },
        )
    return resposta.json() if resposta.content else {"ok": resposta.is_success}


def info_webhook(token: str) -> dict:
    """Estado atual do webhook (para a UI confirmar a conexão)."""
    with httpx.Client(timeout=TIMEOUT_S) as cliente:
        resposta = cliente.post(f"{API_BASE}/bot{token}/getWebhookInfo")
    return resposta.json() if resposta.content else {"ok": resposta.is_success}


def baixar_arquivo(token: str, file_id: str) -> bytes:
    """Baixa o conteúdo de um arquivo do Telegram (ex.: o áudio de uma mensagem
    de voz): getFile devolve o caminho, depois baixa de /file/bot<token>/<caminho>."""
    with httpx.Client(timeout=30.0) as cliente:
        info = cliente.post(f"{API_BASE}/bot{token}/getFile", json={"file_id": file_id})
        info.raise_for_status()
        caminho = (info.json().get("result") or {}).get("file_path")
        if not caminho:
            raise RuntimeError("Telegram não devolveu o caminho do arquivo.")
        conteudo = cliente.get(f"{API_BASE}/file/bot{token}/{caminho}")
        conteudo.raise_for_status()
        return conteudo.content
