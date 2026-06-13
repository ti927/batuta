"""Canal Telegram (Bot API).

Vínculo por TOKEN do bot, criado no BotFather — sem servidor próprio, sem
burocracia da Meta. O token é o único segredo da config (vai pro cofre).

Nesta etapa (Passo 3) só o contrato de configuração está pronto, para o CRUD de
canais validar e separar o token. O `enviar` (Passo 4) e o `normalizar` +
webhook (Passo 5) entram nos próximos passos.
"""

import httpx
from pydantic import BaseModel, Field

from canais.base import FalhaCanal, MensagemNormalizada, TipoCanal, registrar

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
        raise NotImplementedError("Normalização do Telegram entra no Passo 5.")


registrar(CanalTelegram())
