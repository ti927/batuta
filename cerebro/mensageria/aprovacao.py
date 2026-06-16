"""Aprovação de execução por canal (Telegram), coexistindo com a tela.

O portão de aprovação humana (`pausa_humano` num nó da cadeia) sempre pôde ser
resolvido NA TELA (`POST /execucoes/{id}/responder`). Aqui mora a ponte para
resolvê-lo também por MENSAGERIA: quando uma execução pausa, se a automação tem
um CANAL DE APROVAÇÃO configurado (`automacoes.aprovacao_instrumento_id`, um
instrumento de canal do time), amarramos uma `Conversa` viva do aprovador a essa
execução (`Conversa.execucao_id`). A resposta de entrada do aprovador é então
roteada para a retoma (`mensageria/servico.py`), em vez do modo conversacional.

O destinatário (aprovador) vem do `destinatario_padrao` do próprio instrumento —
decisão do maestro: sem cadastro extra. O agente continua enviando o pedido de
aprovação como hoje (via `enviar_telegram`); esta camada só faz a CORRELAÇÃO da
resposta. Borda pura — o núcleo de orquestração não conhece esta tabela.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from modelos import Agente, AgenteInstrumento, Automacao, Conversa, Execucao, Instrumento

# Tipos de instrumento que são canais de mensageria (podem ser canal de aprovação).
CANAIS_TIPOS = {"enviar_telegram", "enviar_whatsapp"}


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
    """Chamada quando uma execução entra em `aguardando_humano`. Se a automação tem
    canal de aprovação e o instrumento tem destinatário fixo, amarra (upsert) uma
    `Conversa` viva desse (instrumento, destinatário) a esta execução, para a
    resposta do aprovador religar o fluxo. Idempotente; respeita o índice único de
    conversa viva. NÃO envia nada (o agente já enviou o pedido)."""
    auto = sessao.get(Automacao, execucao.automacao_id)
    if auto is None or not getattr(auto, "aprovacao_instrumento_id", None):
        return
    inst = sessao.get(Instrumento, auto.aprovacao_instrumento_id)
    if inst is None or inst.tipo not in CANAIS_TIPOS:
        return
    destinatario = ((inst.configuracao or {}).get("destinatario_padrao") or "").strip()
    if not destinatario:
        return  # sem destinatário fixo não há como correlacionar a resposta

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
