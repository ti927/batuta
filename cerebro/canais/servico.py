"""Serviço de borda dos canais: usa o encaixe sem o motor saber dele.

É aqui — não no `TipoCanal` puro (que só fala com o provedor) — que mora o que
precisa de banco: resolver o token do cofre, mesclar na config, chamar o provedor
e REGISTRAR a mensagem no log (`mensagens_canal`). A cola da orquestração (Passo
6) chama `enviar_pelo_canal` quando um fluxo pausa/conclui; o webhook (Passo 5+)
chama o lado da entrada.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import canais as encaixe
import segredos_canal
from canais.base import FalhaCanal, MensagemNormalizada
from modelos import Canal, MensagemCanal


def _config_com_segredos(sessao: Session, canal: Canal):
    """Monta a Config do tipo do canal já com os segredos (token) do cofre — só
    em memória."""
    tipo = encaixe.obter_tipo(canal.tipo)
    if tipo is None:
        raise FalhaCanal(f"Tipo de canal desconhecido: {canal.tipo!r}")
    segredos = segredos_canal.decifrar(sessao, canal.id)
    return tipo, tipo.Config.model_validate({**(canal.config or {}), **segredos})


def enviar_pelo_canal(
    sessao: Session,
    canal: Canal,
    destinatario: str,
    texto: str,
    *,
    execucao_id: uuid.UUID | None = None,
) -> dict:
    """Envia `texto` ao `destinatario` pelo `canal` e registra a saída no log.
    Levanta `FalhaCanal` se o provedor falhar (a saída NÃO é registrada nesse
    caso). Não faz commit — quem chama controla a transação."""
    tipo, config = _config_com_segredos(sessao, canal)
    resultado = tipo.enviar(config, destinatario, texto)
    sessao.add(
        MensagemCanal(
            organizacao_id=canal.organizacao_id,
            canal_id=canal.id,
            execucao_id=execucao_id,
            direcao="saida",
            identificador_externo=destinatario,
            texto=texto,
        )
    )
    sessao.flush()
    return resultado


def baixar_anexo(sessao: Session, canal: Canal, ref: str) -> tuple[bytes, str]:
    """Baixa um anexo do provedor (ex.: a foto pelo file_id do Telegram),
    resolvendo o token do cofre. Devolve (bytes, content_type)."""
    tipo, config = _config_com_segredos(sessao, canal)
    return tipo.baixar_arquivo(config, ref)


def normalizar_entrada(canal: Canal, payload: dict) -> MensagemNormalizada | None:
    """Traduz o payload cru do provedor para o formato interno. None se o evento
    não é uma mensagem que tratamos."""
    tipo = encaixe.obter_tipo(canal.tipo)
    if tipo is None:
        raise FalhaCanal(f"Tipo de canal desconhecido: {canal.tipo!r}")
    return tipo.normalizar(payload)


def registrar_entrada(
    sessao: Session, canal: Canal, msg: MensagemNormalizada
) -> MensagemCanal | None:
    """Registra a mensagem recebida no log, DEDUPLICANDO por (canal, id_externo).
    Devolve a linha criada, ou None se o update já tinha sido processado
    (idempotência: o Telegram reenvia o mesmo update)."""
    ja = sessao.scalars(
        select(MensagemCanal).where(
            MensagemCanal.canal_id == canal.id,
            MensagemCanal.id_externo == msg.id_externo,
        )
    ).first()
    if ja is not None:
        return None
    registro = MensagemCanal(
        organizacao_id=canal.organizacao_id,
        canal_id=canal.id,
        direcao="entrada",
        identificador_externo=msg.identificador_externo,
        texto=msg.texto,
        anexos=[a.model_dump() for a in msg.anexos] or None,
        id_externo=msg.id_externo,
    )
    sessao.add(registro)
    sessao.flush()
    return registro


def registrar_webhook(sessao: Session, canal: Canal, url: str) -> None:
    """Registra `url` como o webhook do canal no provedor (ex.: setWebhook do
    Telegram), resolvendo o token do cofre."""
    tipo, config = _config_com_segredos(sessao, canal)
    tipo.configurar_webhook(config, url)
