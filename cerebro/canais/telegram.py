"""Canal Telegram (Bot API).

Vínculo por TOKEN do bot, criado no BotFather — sem servidor próprio, sem
burocracia da Meta. O token é o único segredo da config (vai pro cofre).

Nesta etapa (Passo 3) só o contrato de configuração está pronto, para o CRUD de
canais validar e separar o token. O `enviar` (Passo 4) e o `normalizar` +
webhook (Passo 5) entram nos próximos passos.
"""

from pydantic import BaseModel, Field

from canais.base import MensagemNormalizada, TipoCanal, registrar


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
        raise NotImplementedError("Envio pelo Telegram entra no Passo 4.")

    def normalizar(self, payload: dict) -> MensagemNormalizada | None:
        raise NotImplementedError("Normalização do Telegram entra no Passo 5.")


registrar(CanalTelegram())
