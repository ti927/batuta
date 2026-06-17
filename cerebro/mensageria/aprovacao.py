"""Aprovação de execução por canal (Telegram), coexistindo com a tela.

O portão de aprovação humana (`gate` num nó da cadeia) sempre pôde ser resolvido NA
TELA (`POST /execucoes/{id}/responder`). Aqui mora a ponte para resolvê-lo também
por MENSAGERIA: quando uma execução pausa, lemos a config de aprovação DO PRÓPRIO NÓ
pausado (no grafo: `no.aprovacao = {instrumento_id, destinatario}`). Se houver canal
+ destinatário, amarramos uma `Conversa` viva do aprovador a essa execução
(`Conversa.execucao_id`). A resposta de entrada do aprovador é então roteada para a
retoma (`mensageria/servico.py`), em vez do modo conversacional.

O destinatário (aprovador) é EXPLÍCITO no nó (construtor visual) — decisão do maestro:
configurado no portão, não num cadastro à parte. Isso resolve o atrito do antigo
`destinatario_padrao` vazio. O agente continua enviando o pedido de aprovação como
hoje (via `enviar_telegram`); esta camada só faz a CORRELAÇÃO da resposta. Borda pura
— o núcleo de orquestração não conhece esta tabela.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    Conversa,
    Execucao,
    Instrumento,
    PassoExecucao,
)
from orquestracao import grafo

# Tipos de instrumento que são canais de mensageria (podem ser canal de aprovação).
CANAIS_TIPOS = {"enviar_telegram", "enviar_whatsapp"}


def _config_aprovacao_do_no(sessao: Session, execucao: Execucao) -> dict | None:
    """A config de aprovação do nó pausado desta execução (`{instrumento_id,
    destinatario}`), ou None se o nó não tem portão por canal. O nó é localizado pelo
    último passo (`no_id`, com fallback ao agente, p/ execuções antigas)."""
    auto = sessao.get(Automacao, execucao.automacao_id)
    if auto is None:
        return None
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    no_id = (ultimo.no_id if ultimo else None) or (
        str(ultimo.agente_id) if ultimo and ultimo.agente_id else None
    )
    if not no_id:
        return None
    no = grafo.indexar(grafo.normalizar(auto.cadeia or {})).no(no_id) or {}
    aprovacao = no.get("aprovacao") or {}
    return aprovacao if aprovacao.get("instrumento_id") else None


def _conversa_viva(
    sessao: Session, instrumento_id: uuid.UUID, contato_chave: str
) -> Conversa | None:
    return sessao.scalars(
        select(Conversa)
        .where(Conversa.instrumento_id == instrumento_id)
        .where(Conversa.contato_chave == contato_chave)
        .where(Conversa.estado != "fechada")
    ).first()


def _agente_atendente_id(sessao: Session, instrumento_id: uuid.UUID) -> uuid.UUID | None:
    """O agente que atende este canal (tem o instrumento no cinto), se houver — para
    a conversa do aprovador voltar ao modo conversacional depois da aprovação."""
    return sessao.scalars(
        select(Agente.id)
        .join(AgenteInstrumento, AgenteInstrumento.agente_id == Agente.id)
        .where(AgenteInstrumento.instrumento_id == instrumento_id)
        .order_by(Agente.criado_em)
    ).first()


def vincular_pausa(sessao: Session, execucao: Execucao) -> None:
    """Chamada quando uma execução entra em `aguardando_humano`. Se o NÓ pausado tem
    portão por canal (`aprovacao = {instrumento_id, destinatario}`), amarra (upsert)
    uma `Conversa` viva desse (instrumento, destinatário) a esta execução, para a
    resposta do aprovador religar o fluxo. Idempotente; respeita o índice único de
    conversa viva. NÃO envia nada (o agente já enviou o pedido)."""
    cfg = _config_aprovacao_do_no(sessao, execucao)
    if cfg is None:
        return
    inst = sessao.get(Instrumento, uuid.UUID(str(cfg["instrumento_id"])))
    auto = sessao.get(Automacao, execucao.automacao_id)
    if inst is None or inst.tipo not in CANAIS_TIPOS:
        return
    if auto is not None and inst.time_id != auto.time_id:
        return  # o canal precisa ser do mesmo time da automação
    destinatario = (cfg.get("destinatario") or "").strip()
    if not destinatario:
        return  # sem destinatário não há como correlacionar a resposta

    conversa = _conversa_viva(sessao, inst.id, destinatario)
    if conversa is None:
        agente_id = _agente_atendente_id(sessao, inst.id)
        conversa = Conversa(
            instrumento_id=inst.id,
            contato_chave=destinatario,
            estado="aguardando_resposta",
            # destino conversacional preservado (se houver atendente): depois da
            # aprovação a conversa volta ao normal. A aprovação é detectada pelo
            # `execucao_id` + estado da execução, não pelo destino.
            destino_tipo="agente" if agente_id else None,
            destino_id=agente_id,
            execucao_id=execucao.id,
        )
        sessao.add(conversa)
    else:
        conversa.execucao_id = execucao.id
        if conversa.estado not in ("humano_assumiu", "fechada"):
            conversa.estado = "aguardando_resposta"
    sessao.flush()


def desvincular(sessao: Session, execucao_id: uuid.UUID) -> None:
    """Desfaz o vínculo de qualquer conversa que apontava para esta execução (ex.:
    a aprovação foi resolvida pela tela). Seguro chamar mesmo sem vínculo."""
    sessao.execute(
        update(Conversa)
        .where(Conversa.execucao_id == execucao_id)
        .values(execucao_id=None)
    )
    sessao.flush()
