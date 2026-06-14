"""Instrumento "Enviar mensagem no Telegram" (mensageria — canal = instrumento).

Manda uma mensagem por um bot do Telegram, via `sendMessage` da Bot API. É o
par de SAÍDA do canal: cada instância do instrumento (com seu próprio token de
bot) é um canal/bot do time. O recebimento (mão dupla) é tratado pela camada de
conversa na borda — ver `docs/MENSAGERIA-PLANO.md`.

Segue a mesma política de falha do encaixe (Tarefa 5.1): falha de transporte e
erros de servidor (5xx/429) são retentáveis; 401/403 (token inválido, bot
bloqueado, destinatário que nunca falou com o bot) não.
"""

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

API_BASE = "https://api.telegram.org"
TIMEOUT_S = 15.0
MAX_TEXTO = 4096  # limite do Telegram por mensagem


class ConfigTelegram(BaseModel):
    """Configuração fixa, preenchida por quem monta o agente. `token_bot` é
    SEGREDO (cofre, Fase 7-B). `destinatario_padrao` é opcional: se preenchido,
    o agente sempre manda para esse chat quando não informar um destinatário
    (útil para um canal/grupo fixo da equipe)."""

    token_bot: str = Field(
        default="",
        description="Token do bot do Telegram (segredo), obtido no BotFather.",
    )
    destinatario_padrao: str = Field(
        default="",
        description="chat_id fixo de destino (opcional). Usado quando o agente "
        "não informa um destinatário.",
    )


class ArgsTelegram(BaseModel):
    """O que a IA passa ao acionar: para quem e o quê."""

    destinatario: str = Field(
        default="",
        description="chat_id de quem recebe. Pode ficar vazio se houver um "
        "destinatário padrão configurado.",
    )
    mensagem: str = Field(min_length=1, description="O texto a enviar.")


class EnviarTelegram(TipoInstrumento):
    tipo = "enviar_telegram"
    nome_exibicao = "Enviar mensagem no Telegram"
    descricao = (
        "Envia uma mensagem de texto pelo Telegram, usando um bot. Use para "
        "responder ou avisar alguém por esse canal."
    )
    Config = ConfigTelegram
    Args = ArgsTelegram
    campos_secretos = ("token_bot",)
    acao_irreversivel = True  # manda mensagem para fora

    def executar(self, config: ConfigTelegram, args: ArgsTelegram) -> dict:
        if not config.token_bot:
            raise FalhaInstrumento(
                "token do bot do Telegram não configurado.", retentavel=False
            )
        destino = (args.destinatario or config.destinatario_padrao or "").strip()
        if not destino:
            raise FalhaInstrumento(
                "destinatário não informado (e não há destinatário padrão).",
                retentavel=False,
            )

        url = f"{API_BASE}/bot{config.token_bot}/sendMessage"
        corpo = {"chat_id": destino, "text": args.mensagem[:MAX_TEXTO]}
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(url, json=corpo)
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível falar com o Telegram: {e}", retentavel=True
            )

        status = resposta.status_code
        if status in (401, 403):
            raise FalhaInstrumento(
                f"o Telegram recusou (HTTP {status}) — verifique o token do bot "
                "e se o destinatário já iniciou uma conversa com o bot.",
                retentavel=False,
            )
        if status == 429 or 500 <= status < 600:
            raise FalhaInstrumento(
                f"o Telegram respondeu HTTP {status}.", retentavel=True
            )

        try:
            dados = resposta.json()
        except ValueError:
            dados = {}
        ok = bool(dados.get("ok")) if dados else resposta.is_success
        resultado = (dados.get("result") or {}) if isinstance(dados, dict) else {}
        return {
            "ok": ok,
            "status": status,
            "mensagem_id": resultado.get("message_id"),
            "descricao": None if ok else dados.get("description"),
        }


registrar(EnviarTelegram())
