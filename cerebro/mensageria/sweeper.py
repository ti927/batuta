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
from mensageria import aprovacao, telegram
from mensageria.config import (  # noqa: F401 (compat sweeper.X)
    DESPEDIDA_MSG,
    DESPEDIDA_PORTAO_CANCELA_MSG,
    DESPEDIDA_PORTAO_MSG,
    NUDGE_MSG,
    TETO_TURNO_PRESO_MIN,
    TETO_TURNO_PRESO_PORTAO_MIN,
    TURNO_PRESO_MSG,
    TURNO_PRESO_PORTAO_MSG,
    com_ajuste_do_no,
    complemento_nudge_portao,
    resolver_config,
)
from modelos import Conversa, Execucao, Instrumento, MensagemConversa
from observabilidade.escritor import registrar_evento
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
        # Portão parado: o ajuste DESTE portão (`no.config`) vence o do Tipo de fluxo —
        # mesma cascata do vínculo (`aprovacao.vincular_pausa`) e do turno por canal. Só
        # no ramo portão (`execucao_id`); atendimento puro segue sem nó (sem regressão).
        execucao = (
            sessao.get(Execucao, conversa.execucao_id) if conversa.execucao_id else None
        )
        if execucao is not None:
            conf = com_ajuste_do_no(conf, aprovacao.no_pausado(sessao, execucao))
        if not conf["encerrar_por_inatividade"]:
            continue  # este fluxo não encerra por silêncio (ex.: deixa vivo de propósito)
        if not conversa.nudge_enviado:
            nudge = conf["mensagem_nudge"]
            # Conduzindo um portão: acrescenta o prazo até encerrar, a opção de *cancelar*
            # e (se estacionar) que a aprovação segue no app — tudo derivado do Tipo de
            # fluxo. Só aqui — não polui conversas de atendimento puro.
            if conversa.execucao_id:
                nudge += complemento_nudge_portao(conf)
            entregue = _enviar(token, conversa.contato_chave, nudge)
            _registrar(sessao, conversa, nudge, entregue)
            conversa.nudge_enviado = True
            conversa.aguardando_ate = agora + timedelta(
                minutes=int(conf["nudge_timeout_min"])
            )
        else:
            eh_portao = bool(conversa.execucao_id)
            acao = conf["portao_acao_abandono"]  # chave ÚNICA (unificada com o turno)
            # Portão: despedida derivada da ação de abandono — estacionar diz que a
            # aprovação segue no app; cancelar avisa que o fluxo foi encerrado junto.
            if eh_portao:
                msg = DESPEDIDA_PORTAO_CANCELA_MSG if acao == "cancelar" else DESPEDIDA_PORTAO_MSG
            else:
                msg = conf["mensagem_despedida"]
            entregue = _enviar(token, conversa.contato_chave, msg)
            _registrar(sessao, conversa, msg, entregue)
            conversa.estado = "fechada"
            # Portão por canal abandonado por inatividade: cancela ou ESTACIONA a
            # execução conforme a chave única e desvincula. Se estacionar, a execução
            # fica `aguardando_humano` e uma resposta tardia a religa (via
            # `servico.registrar_entrada`) — antes ficava órfã para sempre.
            if eh_portao:
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


def varrer_turnos_presos(sessao: Session) -> int:
    """Destrava a conversa cujo TURNO começou e nunca voltou (§12-A).

    Enquanto o turno roda em segundo plano a conversa fica `bot_respondendo`. Se a
    tarefa morrer (reinício do servidor) ou pendurar (chamada externa sem retorno),
    esse estado NÃO era varrido por ninguém: a conversa ficava presa para sempre e o
    contato não recebia sinal nenhum — exatamente o que aconteceu em 2026-08-26, com
    uma aprovação de portão parada ~1h em silêncio até ser descoberta por inspeção
    manual do banco.

    Aqui a falha deixa de ser silenciosa em três frentes: registra um evento de ERRO
    (visível em GET /logs, com há quanto tempo travou), AVISA o contato com um texto
    honesto (o que houve + o que fazer) e DESTRAVA a conversa para
    `aguardando_resposta`, devolvendo-a ao relógio normal do sweeper. Não reprocessa
    o turno sozinho: o turno pendurado pode ainda estar correndo e ter efeito externo
    (publicar, enviar), e disparar de novo arriscaria repetir a ação — a pessoa
    reenvia a mensagem, que é barato e seguro.

    O portão NÃO é resolvido aqui: a execução segue `aguardando_humano` e retomável
    (por resposta tardia no canal ou pela tela) — só a conversa é destravada."""
    agora = datetime.now(timezone.utc)
    # Busca pelo teto MENOR (atendimento); o teto maior do portão é aplicado por
    # conversa logo abaixo (a retomada de fluxo pode legitimamente demorar mais).
    limite = agora - timedelta(minutes=TETO_TURNO_PRESO_MIN)
    limite_portao = agora - timedelta(minutes=TETO_TURNO_PRESO_PORTAO_MIN)
    candidatas = sessao.scalars(
        select(Conversa).where(
            Conversa.estado == "bot_respondendo",
            Conversa.ultima_entrada_em.is_not(None),
            Conversa.ultima_entrada_em <= limite,
        )
    ).all()
    presas = [
        c
        for c in candidatas
        if not c.execucao_id or c.ultima_entrada_em <= limite_portao
    ]
    for conversa in presas:
        parado_min = int((agora - conversa.ultima_entrada_em).total_seconds() // 60)
        instrumento = sessao.get(Instrumento, conversa.instrumento_id)
        token = (
            segredos_instrumento.decifrar(sessao, instrumento.id).get("token_bot")
            if instrumento
            else None
        )
        eh_portao = bool(conversa.execucao_id)
        msg = TURNO_PRESO_PORTAO_MSG if eh_portao else TURNO_PRESO_MSG
        entregue = _enviar(token, conversa.contato_chave, msg)
        _registrar(sessao, conversa, msg, entregue)
        conversa.estado = "aguardando_resposta"
        # Relógio normal de inatividade re-armado: sem isto a conversa destravada
        # ficaria fora tanto deste vigia quanto do sweeper de silêncio.
        conf = resolver_config(sessao, conversa)
        conversa.aguardando_ate = agora + timedelta(minutes=int(conf["timeout_min"]))
        registrar_evento(
            categoria="mensageria",
            acao="turno.preso",
            nivel="error",
            resultado="falha",
            persistir=True,
            recurso_tipo="conversa",
            recurso_id=conversa.id,
            detalhe={
                "parado_min": parado_min,
                "canal": conversa.canal,
                "portao": eh_portao,
                "execucao_id": str(conversa.execucao_id) if eh_portao else None,
                "aviso_entregue": entregue,
                "efeito": "conversa destravada; o contato foi avisado e pode reenviar",
            },
        )
    if presas:
        sessao.commit()
    return len(presas)


# Heartbeat do vigia (lido pela sonda `vigia_mensageria` do `saude_elos`): quando a
# última varredura completou. None = ainda não varreu desde o boot. Sem isto, um job
# morto no agendador deixaria as conversas sem vigia EM SILÊNCIO — exatamente a
# classe de falha que o vigia existe para matar.
ULTIMA_VARREDURA_EM: datetime | None = None


def varrer_job() -> None:
    """Entrada do agendador: abre a própria sessão e varre (silêncio + turno preso)."""
    global ULTIMA_VARREDURA_EM
    sessao = CriadorDeSessao()
    try:
        varrer(sessao)
        varrer_turnos_presos(sessao)
        ULTIMA_VARREDURA_EM = datetime.now(timezone.utc)
    finally:
        sessao.close()
