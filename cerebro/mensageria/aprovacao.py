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
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

import segredos_instrumento
from mensageria import telegram
from mensageria.config import (
    aviso_expectativa_portao,
    com_ajuste_do_no,
    resolver_config,
)
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    Conversa,
    Execucao,
    Instrumento,
    MensagemConversa,
    PassoExecucao,
)
from orquestracao import grafo

# Tipos de instrumento que são canais de mensageria (podem ser canal de aprovação).
CANAIS_TIPOS = {"enviar_telegram", "enviar_whatsapp"}


def no_pausado(sessao: Session, execucao: Execucao) -> dict | None:
    """O NÓ do grafo onde a execução pausou (último passo → `no_id` → nó normalizado),
    ou None se não há passo/nó. FONTE ÚNICA do lookup para quem precisa aplicar ajustes
    POR-NÓ (`com_ajuste_do_no`) a um portão parado — sweeper, retoma e aqui. Fica neste
    módulo (folha da borda: não importa sweeper/retoma/servico) para não criar ciclo."""
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
    return grafo.indexar(grafo.normalizar(auto.cadeia or {})).no(no_id)


def passo_pausado(sessao: Session, execucao: Execucao) -> PassoExecucao | None:
    """O último passo desta execução — aquele em que ela parou."""
    return sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()


def config_aprovacao(sessao: Session, execucao: Execucao) -> dict | None:
    """Por onde o pedido de aprovação foi apresentado (`{instrumento_id,
    destinatario}`), ou None se não foi por canal (só pela tela).

    A verdade mora no PASSO: quem pediu foi o agente, chamando `pedir_aprovacao`, e o
    passo guarda o canal que ele de fato usou. Antes isso era configuração do NÓ
    (`no.aprovacao`, do extinto portão) — um campo à parte que podia divergir do envio
    e deixava a execução órfã. Execuções pausadas ANTES desta virada ainda têm a config
    no nó, então ele fica como fallback."""
    passo = passo_pausado(sessao, execucao)
    do_passo = ((passo.saida or {}).get("aprovacao") or {}) if passo else {}
    if do_passo.get("canal_instrumento_id"):
        return {
            "instrumento_id": do_passo["canal_instrumento_id"],
            "destinatario": do_passo.get("destinatario") or "",
        }
    no = no_pausado(sessao, execucao) or {}
    legado = no.get("aprovacao") or {}
    return legado if legado.get("instrumento_id") else None


def _conversa_viva(
    sessao: Session, instrumento_id: uuid.UUID, contato_chave: str
) -> Conversa | None:
    return sessao.scalars(
        select(Conversa)
        .where(Conversa.instrumento_id == instrumento_id)
        .where(Conversa.contato_chave == contato_chave)
        .where(Conversa.estado != "fechada")
    ).first()


def _destino_efetivo(inst: Instrumento, cfg: dict) -> str:
    """O aprovador do portão = destino EFETIVO do instrumento (`destinatario_padrao`),
    com o `destinatario` do nó só como FALLBACK (instrumento sem destino configurado).

    FONTE ÚNICA: quem recebe o envio é quem aprova. O envio usa `destinatario_padrao`
    desde "o instrumento é a verdade" (2026-06-25); então o portão passa a esperar a
    resposta no MESMO chat para onde o agente mandou o pedido. Antes o aprovador vinha
    de `no.aprovacao.destinatario`, um campo à parte que divergia do envio e deixava a
    execução órfã (o pedido ia para um chat e o sistema esperava em outro)."""
    padrao = ((inst.configuracao or {}).get("destinatario_padrao") or "").strip()
    return padrao or (cfg.get("destinatario") or "").strip()


def execucao_parada_do_contato(
    sessao: Session, instrumento: Instrumento, contato_chave: str
) -> Execucao | None:
    """Uma execução `aguardando_humano` cujo portão por canal (aprovador DERIVADO,
    `_destino_efetivo`) é (este instrumento, este contato). Serve para RELIGAR uma
    resposta TARDIA a um portão que ficou parado — mesmo depois de o sweeper ter
    encerrado a conversa anterior. Devolve a mais recente (a resposta do aprovador
    costuma se referir ao último pedido apresentado)."""
    contato = (contato_chave or "").strip()
    if not contato:
        return None
    auto_ids = sessao.scalars(
        select(Automacao.id).where(Automacao.time_id == instrumento.time_id)
    ).all()
    if not auto_ids:
        return None
    execs = sessao.scalars(
        select(Execucao)
        .where(Execucao.automacao_id.in_(auto_ids))
        .where(Execucao.estado == "aguardando_humano")
        .order_by(Execucao.iniciada_em.desc())
    ).all()
    for ex in execs:
        cfg = config_aprovacao(sessao, ex)
        if cfg is None:
            continue
        inst = sessao.get(Instrumento, uuid.UUID(str(cfg["instrumento_id"])))
        if inst is None or inst.id != instrumento.id:
            continue
        if _destino_efetivo(inst, cfg) == contato:
            return ex
    return None


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
    conversa viva. O PEDIDO em si é do agente (já enviado); aqui a borda só acrescenta UM
    aviso de expectativa derivado do Tipo de fluxo (`_avisar_expectativa`, à prova de falha
    e idempotente) — o que acontece se o humano não responder."""
    cfg = config_aprovacao(sessao, execucao) or {}
    if not cfg.get("instrumento_id"):
        return
    no = no_pausado(sessao, execucao) or {}
    inst = sessao.get(Instrumento, uuid.UUID(str(cfg["instrumento_id"])))
    auto = sessao.get(Automacao, execucao.automacao_id)
    if inst is None or inst.tipo not in CANAIS_TIPOS:
        return
    if auto is not None and inst.time_id != auto.time_id:
        return  # o canal precisa ser do mesmo time da automação
    destinatario = _destino_efetivo(inst, cfg)
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

    # Relógio de inatividade: o portão por canal também é varrido pelo sweeper
    # (regra geral de mensageria) — antes ficava "aberto para sempre". Cutuca e,
    # persistindo o silêncio, encerra (cancelando/estacionando a execução).
    # `com_ajuste_do_no`: o prazo/ação DESTE portão (`no.config`) vence o do Tipo de
    # fluxo — mesma cascata do turno por canal (`servico._turno_de_portao`).
    conf = com_ajuste_do_no(resolver_config(sessao, conversa), no)
    # Ordem natural na thread: primeiro o PEDIDO apresentado, depois o aviso de expectativa.
    _registrar_apresentado(sessao, conversa, execucao)
    if conf["encerrar_por_inatividade"] and conversa.estado not in (
        "humano_assumiu", "fechada",
    ):
        conversa.aguardando_ate = datetime.now(timezone.utc) + timedelta(
            minutes=int(conf["timeout_min"])
        )
        conversa.nudge_enviado = False
        sessao.flush()
        _avisar_expectativa(sessao, conversa, inst, conf, execucao)


def _avisar_expectativa(
    sessao: Session, conversa: Conversa, inst: Instrumento, conf: dict, execucao: Execucao
) -> None:
    """Envia, JUNTO da pausa do portão, UM aviso do que acontece se o humano não
    responder (prazo até encerrar + destino da aprovação), DERIVADO do Tipo de fluxo
    (`config.aviso_expectativa_portao`). À PROVA DE FALHA — `vincular_pausa` roda no
    `try` de `disparo`/`retoma` que marca a execução como `falhou` se algo estourar, então
    o envio NUNCA pode propagar exceção. Idempotente por passo pausado (carimba
    `midia.tipo='aviso_portao'` + `passo_id`): uma 2ª chamada da mesma pausa não duplica."""
    msg = aviso_expectativa_portao(conf)
    if not msg:
        return
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    if ultimo is None:
        return
    ja_avisado = sessao.scalars(
        select(MensagemConversa.id)
        .where(MensagemConversa.conversa_id == conversa.id)
        .where(MensagemConversa.midia["tipo"].astext == "aviso_portao")
        .where(MensagemConversa.midia["passo_id"].astext == str(ultimo.id))
    ).first()
    if ja_avisado:
        return
    entregue = False
    try:
        token = segredos_instrumento.decifrar(sessao, inst.id).get("token_bot")
        if token:
            entregue = bool(
                telegram.enviar(token, conversa.contato_chave, msg).get("ok")
            )
    except Exception:
        entregue = False  # nunca falha a execução por causa do aviso
    sessao.add(
        MensagemConversa(
            conversa_id=conversa.id,
            papel="agente",
            conteudo=msg,
            midia={"tipo": "aviso_portao", "passo_id": str(ultimo.id)},
            entregue=entregue,
        )
    )
    sessao.flush()


def _registrar_apresentado(
    sessao: Session, conversa: Conversa, execucao: Execucao
) -> None:
    """Grava na thread da conversa o que o agente APRESENTOU ao humano nesta pausa
    (o pedido de aprovação). Sem isto a conversa fica pela metade: o que o agente
    envia por canal durante a execução só vive em memória e nunca aparecia nas
    Conversas (só a resposta do humano e os acks). É o passo pausado que carrega o
    apresentado (`cadeia.py` sobrescreve a saída com a mensagem que a pessoa viu).
    Idempotente pelo SEU marcador (`midia.origem='execucao'` + `passo_id`), pois
    `vincular_pausa` pode ser chamada mais de uma vez para a mesma pausa — e a mesma pausa
    também grava o aviso de expectativa com o mesmo `passo_id` (por isso o dedup filtra
    pela origem, não só pelo passo)."""
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    if ultimo is None:
        return
    texto = ((ultimo.saida or {}).get("texto") or "").strip()
    if not texto:
        return
    ja_gravado = sessao.scalars(
        select(MensagemConversa.id)
        .where(MensagemConversa.conversa_id == conversa.id)
        .where(MensagemConversa.midia["origem"].astext == "execucao")
        .where(MensagemConversa.midia["passo_id"].astext == str(ultimo.id))
    ).first()
    if ja_gravado:
        return
    sessao.add(
        MensagemConversa(
            conversa_id=conversa.id,
            papel="agente",
            conteudo=texto,
            midia={"origem": "execucao", "passo_id": str(ultimo.id)},
            entregue=True,
        )
    )
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


# Estados em que uma execução já encerrou — não se cancela de novo.
ESTADOS_ENCERRADOS = {"concluida", "falhou", "cancelada"}


def cancelar_execucao(
    sessao: Session, execucao: Execucao, *, motivo: str = "Cancelada pelo operador."
) -> bool:
    """Encerra uma execução como `cancelada` — FONTE ÚNICA usada pela TELA (rota
    `/cancelar`) e pelo CANAL (comando reservado no portão): seta estado/finalização/
    resultado e DESVINCULA a conversa de portão (se houver). Idempotente: se a execução
    já encerrou, devolve False sem tocar em nada. NÃO comita — o chamador fecha a
    transação junto com a sua auditoria (tela) ou ack + estado da conversa (canal)."""
    if execucao.estado in ESTADOS_ENCERRADOS:
        return False
    execucao.estado = "cancelada"
    if not execucao.resultado:
        execucao.resultado = {"texto": motivo}
    execucao.finalizada_em = datetime.now(timezone.utc)
    desvincular(sessao, execucao.id)
    return True
