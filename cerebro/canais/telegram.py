"""Canal Telegram (Bot API).

Vínculo por TOKEN do bot, criado no BotFather — sem servidor próprio, sem
burocracia da Meta. O token é o único segredo da config (vai pro cofre).

Nesta etapa (Passo 3) só o contrato de configuração está pronto, para o CRUD de
canais validar e separar o token. O `enviar` (Passo 4) e o `normalizar` +
webhook (Passo 5) entram nos próximos passos.
"""

import httpx
from pydantic import BaseModel, Field

from canais.base import Anexo, FalhaCanal, MensagemNormalizada, TipoCanal, registrar

API_TELEGRAM = "https://api.telegram.org"
TIMEOUT_S = 15.0


class ConfigTelegram(BaseModel):
    """Configuração do canal Telegram. `token` é SEGREDO (cofre)."""

    token: str = Field(
        default="",
        description="Token do bot (BotFather), no formato 123456:ABC-...; é segredo.",
    )


class CanalTelegram(TipoCanal):
    tipo = "telegram"
    nome_exibicao = "Telegram"
    descricao = "Bot do Telegram (Bot API). Vínculo por token do BotFather."
    Config = ConfigTelegram
    campos_secretos = ("token",)

    def enviar(self, config: ConfigTelegram, destinatario: str, mensagem: str) -> dict:
        """Manda uma mensagem de texto via Bot API (`sendMessage`). `destinatario`
        é o chat_id. O token chega na config (mesclado do cofre pela borda)."""
        if not config.token:
            raise FalhaCanal("Canal Telegram sem token configurado.")
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(
                    f"{API_TELEGRAM}/bot{config.token}/sendMessage",
                    json={"chat_id": destinatario, "text": mensagem},
                )
        except httpx.HTTPError as e:
            raise FalhaCanal(f"não foi possível falar com o Telegram: {e}")
        if resposta.status_code != 200:
            descricao = ""
            try:
                descricao = resposta.json().get("description", "")
            except Exception:
                descricao = resposta.text[:200]
            raise FalhaCanal(
                f"o Telegram recusou o envio (HTTP {resposta.status_code}): {descricao}"
            )
        resultado = resposta.json().get("result", {})
        return {"ok": True, "id_mensagem": resultado.get("message_id")}

    def normalizar(self, payload: dict) -> MensagemNormalizada | None:
        """Traduz um update do Telegram para o formato interno. Devolve None para
        updates que não são mensagem que tratamos (ex.: callback de botão)."""
        msg = payload.get("message") or payload.get("edited_message")
        update_id = payload.get("update_id")
        if not isinstance(msg, dict) or update_id is None:
            return None
        chat_id = (msg.get("chat") or {}).get("id")
        if chat_id is None:
            return None
        anexos: list[Anexo] = []
        fotos = msg.get("photo") or []
        if fotos:
            # O Telegram manda a mesma foto em várias resoluções; a maior é a última.
            maior = fotos[-1]
            if maior.get("file_id"):
                anexos.append(Anexo(tipo="imagem", ref=maior["file_id"]))
        return MensagemNormalizada(
            identificador_externo=str(chat_id),
            texto=msg.get("text") or msg.get("caption") or "",
            anexos=anexos,
            id_externo=str(update_id),
        )

    def configurar_webhook(self, config: ConfigTelegram, url: str) -> None:
        """Registra `url` como o webhook do bot no Telegram (`setWebhook`). É como
        o Telegram passa a entregar as mensagens recebidas ao cérebro."""
        if not config.token:
            raise FalhaCanal("Canal Telegram sem token configurado.")
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(
                    f"{API_TELEGRAM}/bot{config.token}/setWebhook",
                    json={"url": url},
                )
        except httpx.HTTPError as e:
            raise FalhaCanal(f"não foi possível registrar o webhook no Telegram: {e}")
        if resposta.status_code != 200 or not resposta.json().get("ok"):
            raise FalhaCanal(
                f"o Telegram recusou o setWebhook (HTTP {resposta.status_code})."
            )


registrar(CanalTelegram())
