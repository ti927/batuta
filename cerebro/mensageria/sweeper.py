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
from mensageria.config import (  # noqa: F401 (compat sweeper.X)
    DESPEDIDA_MSG,
    DESPEDIDA_PORTAO_MSG,
    NUDGE_MSG,
    resolver_config,
)
from modelos import Conversa, Execucao, Instrumento, MensagemConversa
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
        if not conf["encerrar_por_inatividade"]:
            continue  # este fluxo não encerra por silêncio (ex.: deixa vivo de propósito)
        if not conversa.nudge_enviado:
            nudge = conf["mensagem_nudge"]
            # Conduzindo um portão: lembra a opção de ENCERRAR (descoberta do comando
            # reservado de cancelar). Só aqui — não polui conversas de atendimento puro.
            if conversa.execucao_id:
                nudge += "\n\n(Ou responda *cancelar* para encerrar o fluxo.)"
            entregue = _enviar(token, conversa.contato_chave, nudge)
            _registrar(sessao, conversa, nudge, entregue)
            conversa.nudge_enviado = True
            conversa.aguardando_ate = agora + timedelta(
                minutes=int(conf["nudge_timeout_min"])
            )
        else:
            eh_portao = bool(conversa.execucao_id)
            acao = conf["portao_acao_abandono"]  # chave ÚNICA (unificada com o turno)
            # Portão deixado PENDENTE (estacionar): despedida que não sugere fim de fluxo.
            msg = (
                DESPEDIDA_PORTAO_MSG
                if eh_portao and acao != "cancelar"
                else conf["mensagem_despedida"]
            )
            entregue = _enviar(token, conversa.contato_chave, msg)
            _registrar(sessao, conversa, msg, entregue)
            conversa.estado = "fechada"
            # Portão por canal abandonado por inatividade: cancela ou ESTACIONA a
            # execução conforme a chave única e desvincula. Se estacionar, a execução
            # fica `aguardando_humano` e uma resposta tardia a religa (via
            # `servico.registrar_entrada`) — antes ficava órfã para sempre.
            if eh_portao:
                execucao = sessao.get(Execucao, conversa.execucao_id)
                if (
                    execucao is not None
                    and execucao.estado == "aguardando_humano"
                    and acao == "cancelar"
                ):
                    execucao.estado = "cancelada"
                    execucao.finalizada_em = agora
                conversa.execucao_id = None
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
