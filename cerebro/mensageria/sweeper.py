"""Vigia de inatividade das conversas (Fase J).

Roda periodicamente no agendador (1 réplica, sem duplicar): para conversas
paradas em `aguardando_resposta` além do prazo (`aguardando_ate`), CUTUCA uma vez
("ainda está aí?") e, se o silêncio persistir, ENCERRA com uma despedida
(decisão do maestro: cutuca 1x e depois encerra). Reusa o envio do canal; não
toca o núcleo de orquestração.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import segredos_instrumento
from mensageria import telegram
from mensageria.config import DESPEDIDA_MSG, NUDGE_MSG, resolver_config  # noqa: F401 (compat sweeper.X)
from modelos import Conversa, Instrumento, MensagemConversa
from sessao import CriadorDeSessao


def _enviar(token: str | None, chave: str, texto: str) -> bool:
    if not token:
        return False
    try:
        return bool(telegram.enviar(token, chave, texto).get("ok"))
    except Exception:
        return False


def _registrar(sessao: Session, conversa: Conversa, texto: str, entregue: bool) -> None:
    sessao.add(
        MensagemConversa(
            conversa_id=conversa.id, papel="agente", conteudo=texto, entregue=entregue
        )
    )


def varrer(sessao: Session) -> int:
    """Processa as conversas vencidas (cutuca ou encerra). Devolve quantas mexeu."""
    agora = datetime.now(timezone.utc)
    vencidas = sessao.scalars(
        select(Conversa).where(
            Conversa.estado == "aguardando_resposta",
            Conversa.aguardando_ate.is_not(None),
            Conversa.aguardando_ate <= agora,
        )
    ).all()
    for conversa in vencidas:
        instrumento = sessao.get(Instrumento, conversa.instrumento_id)
        token = (
            segredos_instrumento.decifrar(sessao, instrumento.id).get("token_bot")
            if instrumento
            else None
        )
        conf = resolver_config(sessao, conversa)  # fonte única (perfil do fluxo inclusive)
        if not conversa.nudge_enviado:
            entregue = _enviar(token, conversa.contato_chave, conf["mensagem_nudge"])
            _registrar(sessao, conversa, conf["mensagem_nudge"], entregue)
            conversa.nudge_enviado = True
            conversa.aguardando_ate = agora + timedelta(
                minutes=int(conf["nudge_timeout_min"])
            )
        else:
            entregue = _enviar(token, conversa.contato_chave, conf["mensagem_despedida"])
            _registrar(sessao, conversa, conf["mensagem_despedida"], entregue)
            conversa.estado = "fechada"
    if vencidas:
        sessao.commit()
    return len(vencidas)


def varrer_job() -> None:
    """Entrada do agendador: abre a própria sessão e varre."""
    sessao = CriadorDeSessao()
    try:
        varrer(sessao)
    finally:
        sessao.close()
