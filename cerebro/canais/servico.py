"""Serviço de borda dos canais: usa o encaixe sem o motor saber dele.

É aqui — não no `TipoCanal` puro (que só fala com o provedor) — que mora o que
precisa de banco: resolver o token do cofre, mesclar na config, chamar o provedor
e REGISTRAR a mensagem no log (`mensagens_canal`). A cola da orquestração (Passo
6) chama `enviar_pelo_canal` quando um fluxo pausa/conclui; o webhook (Passo 5+)
chama o lado da entrada.
"""

import uuid

from sqlalchemy.orm import Session

import canais as encaixe
import segredos_canal
from canais.base import FalhaCanal
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
