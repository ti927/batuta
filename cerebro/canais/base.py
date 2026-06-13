"""O contrato e o registro de tipos de canal de mensageria (o encaixe de canais).

Um canal é uma capacidade de mensageria plugável (Telegram, no futuro WhatsApp)
que pende da ORGANIZAÇÃO. Diferente de um instrumento — que um agente aciona
dentro de um passo via `executar(config, args)` —, um canal é um serviço da
BORDA, acionado pela cola da orquestração: manda mensagem quando um fluxo pausa
ou conclui (`enviar`) e recebe mensagens de fora (`normalizar`). Mas o PADRÃO de
encaixe é o mesmo dos instrumentos: cada tipo declara `Config`, `campos_secretos`
e se auto-registra ao ser importado.

Toda a lógica de roteamento de entrada (Modo A — resposta a execução pausada;
Modo B — início de fluxo novo) opera sobre o formato `MensagemNormalizada`,
independente do provedor. Assim, adicionar WhatsApp depois é só implementar um
novo `TipoCanal` — o roteamento não muda.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class FalhaCanal(Exception):
    """O canal não conseguiu operar (provedor fora do ar, token inválido, rede
    oscilou). Distinta de uma resposta legítima do provedor — é uma falha de
    comunicação que a borda transforma em erro visível, sem morrer em silêncio."""


class Anexo(BaseModel):
    """Um anexo de uma mensagem recebida, normalizado e independente do provedor.

    `tipo` é uma categoria simples (ex.: "imagem", "audio", "documento").
    `ref` é o identificador do arquivo no provedor (ex.: o `file_id` do Telegram),
    resolvido para conteúdo real só quando for baixado (Passo 8).
    `nome` e `mime` são metadados opcionais quando o provedor os fornece.
    """

    tipo: str
    ref: str
    nome: str = ""
    mime: str = ""


class MensagemNormalizada(BaseModel):
    """Uma mensagem de ENTRADA já traduzida para o formato interno único.

    É sobre este formato — não sobre o payload cru do Telegram/WhatsApp — que o
    roteamento Modo A/Modo B opera.
    """

    identificador_externo: str = Field(
        min_length=1,
        description="Quem mandou, no jargão do canal (ex.: o chat_id do Telegram).",
    )
    texto: str = Field(
        default="", description="O texto da mensagem (vazio se for só anexo)."
    )
    anexos: list[Anexo] = Field(
        default_factory=list, description="Anexos da mensagem (imagens, etc.)."
    )
    id_externo: str = Field(
        min_length=1,
        description=(
            "Id único do evento no provedor (ex.: o update_id do Telegram). Base "
            "da idempotência: um update reenviado tem o mesmo id_externo."
        ),
    )


class TipoCanal(ABC):
    """Contrato comum a todo tipo de canal de mensageria."""

    tipo: str
    nome_exibicao: str
    descricao: str
    Config: type[BaseModel]
    # Campos da Config que são SEGREDOS (cofre): em vez de irem para a
    # `canais.config` (JSONB em claro), são cifrados no cofre de segredos do
    # canal e injetados só em runtime. Top-level, string. (Ex.: o token do bot.)
    campos_secretos: tuple[str, ...] = ()

    @abstractmethod
    def enviar(self, config: BaseModel, destinatario: str, mensagem: str) -> dict:
        """Manda uma mensagem pelo canal para `destinatario` (o identificador
        externo, ex.: chat_id). `config` é uma instância de `self.Config` já com
        os segredos mesclados. Devolve um dicionário serializável (ex.: o id da
        mensagem enviada)."""

    @abstractmethod
    def normalizar(self, payload: dict) -> MensagemNormalizada | None:
        """Traduz um evento cru do provedor para `MensagemNormalizada`.

        Devolve `None` quando o evento não é uma mensagem que tratamos (ex.: um
        update do Telegram que não carrega mensagem) — o webhook ignora.
        """

    def configurar_webhook(self, config: BaseModel, url: str) -> None:
        """Registra `url` como o webhook do canal no provedor, se ele exigir
        (ex.: `setWebhook` do Telegram). O padrão é no-op: nem todo provedor
        precisa de registro explícito."""
        return None


_REGISTRO: dict[str, TipoCanal] = {}


def registrar(instancia: TipoCanal) -> None:
    """Registra um tipo de canal. Chamado pelo módulo de cada tipo ao importar."""
    _REGISTRO[instancia.tipo] = instancia


def obter_tipo(tipo: str) -> TipoCanal | None:
    return _REGISTRO.get(tipo)


def tipos_disponiveis() -> list[TipoCanal]:
    return list(_REGISTRO.values())


def campos_secretos(tipo: str) -> tuple[str, ...]:
    """Os campos secretos de um tipo de canal (vazio se não tem segredos)."""
    t = obter_tipo(tipo)
    return tuple(getattr(t, "campos_secretos", ()) or ()) if t else ()


def preparar_config(tipo: str, configuracao: dict | None) -> tuple[dict, dict]:
    """Valida a config de um canal e SEPARA os segredos (espelha o encaixe de
    instrumentos). Devolve `(config_publica, segredos)`:
    - `config_publica`: a config validada SEM os campos secretos — vai para
      `canais.config` (JSONB em claro).
    - `segredos`: {campo: valor} só com os campos secretos REALMENTE informados
      (presentes e não-vazios) — é o que será cifrado no cofre. Campo secreto
      omitido ou vazio não entra (na edição, preserva o valor atual).

    Levanta `ValueError` se o tipo é desconhecido ou a configuração é inválida.
    """
    t = obter_tipo(tipo)
    if t is None:
        raise ValueError(f"Tipo de canal desconhecido: {tipo!r}")
    secretos = set(t.campos_secretos)
    bruta = dict(configuracao or {})
    segredos = {
        campo: str(bruta[campo])
        for campo in secretos
        if campo in bruta and str(bruta[campo]).strip()
    }
    config_publica = t.Config.model_validate(bruta).model_dump()
    for campo in secretos:
        config_publica.pop(campo, None)
    return config_publica, segredos
