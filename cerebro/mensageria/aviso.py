"""Aviso honesto quando uma execução FALHA (§12-A: nunca morrer em silêncio).

Até 2026-08-31 uma automação podia falhar todo dia e ninguém saber: a falha ficava
no `resultado` da execução e no banco de logs — lugares que só quem vai procurar
encontra. O `PRODUTO §16` diz que a falha nunca é silenciosa; na prática era.

Aqui a borda fecha esse buraco: ao falhar, o Batuta manda um recado pelo canal do
time (o mesmo instrumento de mensageria que o time já usa), dizendo O QUE quebrou,
EM QUAL passo e O QUE fazer. Se não houver canal, ou o envio falhar, isso também vira
evento no banco de logs — um fail-safe mudo seria repetir o próprio problema.

Módulo FOLHA da borda: não importa `servico`/`retoma`/`fila` (evita ciclo). Nunca
levanta — o chamador está no caminho de erro e não pode quebrar por causa do aviso.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import segredos_instrumento
from mensageria import telegram
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    Execucao,
    Instrumento,
    PassoExecucao,
)
from observabilidade.escritor import registrar_evento

# Tipos de instrumento que sabem entregar um recado a uma pessoa.
CANAIS_TIPOS = ("enviar_telegram",)

# Quanto do erro cru vai no recado (o texto completo fica no banco de logs).
MAX_ERRO = 300


def _canal_do_time(sessao: Session, time_id: uuid.UUID | None) -> tuple[Instrumento, str] | None:
    """Um canal do time com destinatário configurado — (instrumento, destino).

    Preferimos um canal que esteja no cinto de algum agente do time (é o canal em
    uso); na falta, qualquer canal do time com `destinatario_padrao`."""
    if time_id is None:
        return None
    canais = list(
        sessao.scalars(
            select(Instrumento)
            .where(Instrumento.time_id == time_id)
            .where(Instrumento.tipo.in_(CANAIS_TIPOS))
        )
    )
    com_destino = [
        (i, ((i.configuracao or {}).get("destinatario_padrao") or "").strip())
        for i in canais
    ]
    com_destino = [(i, d) for i, d in com_destino if d]
    if not com_destino:
        return None
    encaixados = set(
        sessao.scalars(
            select(AgenteInstrumento.instrumento_id)
            .join(Agente, Agente.id == AgenteInstrumento.agente_id)
            .where(Agente.time_id == time_id)
        )
    )
    for inst, destino in com_destino:
        if inst.id in encaixados:
            return inst, destino
    return com_destino[0]


def _onde_parou(sessao: Session, execucao: Execucao) -> str:
    """O nome do passo onde a execução parou — o que a pessoa precisa saber para
    olhar no lugar certo. Vazio se não há passo (falhou antes de rodar qualquer um)."""
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    if ultimo is None:
        return ""
    agente = sessao.get(Agente, ultimo.agente_id) if ultimo.agente_id else None
    return agente.nome if agente else (ultimo.no_id or "")


def montar_texto(automacao_nome: str, passo: str, erro: str) -> str:
    """O recado. Diz o quê, onde e o que fazer — nunca 'ocorreu um erro'."""
    linhas = [f"⚠️ A automação *{automacao_nome}* falhou e parou."]
    if passo:
        linhas.append(f"Parou no passo: {passo}")
    if erro:
        linhas.append(f"Motivo: {erro[:MAX_ERRO]}")
    linhas.append(
        "Abra a execução no Batuta para ver o passo a passo. Se foi uma falha "
        "passageira (rede, serviço fora do ar), dispare de novo."
    )
    return "\n".join(linhas)


def montar_texto_desligada(automacao_nome: str, quantas: int, passo: str) -> str:
    """O recado do disjuntor (Onda 4, fatia 3). Diz o que aconteceu, o que o Batuta
    fez a respeito e o que a pessoa precisa fazer — desligar em silêncio seria trocar
    um problema barulhento por um mudo."""
    linhas = [
        f"🛑 Desliguei a automação *{automacao_nome}*.",
        f"Ela falhou {quantas} vezes seguidas rodando sozinha.",
    ]
    if passo:
        linhas.append(f"A última parou no passo: {passo}")
    linhas.append(
        "Ela não vai disparar de novo até você religar. Abra as execuções no Batuta "
        "para ver o que quebrou, conserte e ative a automação outra vez — a contagem "
        "recomeça do zero."
    )
    return "\n".join(linhas)


def avisar_desligada(
    sessao: Session, execucao: Execucao, automacao: Automacao, quantas: int
) -> None:
    """Avisa pelo canal do time que o disjuntor tirou a automação do ar. Best-effort e
    SEMPRE com rastro, como o aviso de falha — um desligamento mudo seria pior que a
    falha que ele evita."""
    try:
        alvo = _canal_do_time(sessao, automacao.time_id)
        if alvo is None:
            registrar_evento(
                categoria="execucao", acao="desligada.sem_canal", nivel="warning",
                recurso_tipo="automacao", recurso_id=automacao.id,
                detalhe={
                    "automacao": automacao.nome,
                    "porque": "o time não tem canal de mensageria com destinatário "
                    "configurado — o desligamento não pôde ser avisado a ninguém",
                },
            )
            return
        inst, destino = alvo
        texto = montar_texto_desligada(
            automacao.nome, quantas, _onde_parou(sessao, execucao)
        )
        token = (segredos_instrumento.decifrar(sessao, inst.id) or {}).get("token_bot")
        entregue = bool(token) and bool(telegram.enviar(token, destino, texto).get("ok"))
        registrar_evento(
            categoria="execucao",
            acao="desligada.avisada" if entregue else "desligada.aviso_nao_entregue",
            nivel="info" if entregue else "warning",
            recurso_tipo="automacao", recurso_id=automacao.id,
            detalhe={"automacao": automacao.nome, "instrumento": inst.nome},
        )
    except Exception as e:  # o aviso NUNCA derruba o caminho de erro que o chamou
        registrar_evento(
            categoria="execucao", acao="desligada.aviso_quebrou", nivel="error",
            resultado="falha", erro=e, recurso_tipo="automacao",
            recurso_id=getattr(automacao, "id", None),
        )


def avisar_falha(sessao: Session, execucao: Execucao, erro: str) -> None:
    """Avisa pelo canal do time que esta execução falhou. Best-effort e SEMPRE com
    rastro: sem canal, envio recusado ou exceção viram evento no banco de logs."""
    try:
        if execucao is None or execucao.modo == "conversa":
            return  # o rastro-sombra de uma conversa não é uma automação
        automacao = sessao.get(Automacao, execucao.automacao_id)
        if automacao is None:
            return
        alvo = _canal_do_time(sessao, automacao.time_id)
        if alvo is None:
            registrar_evento(
                categoria="execucao", acao="falha.sem_canal", nivel="warning",
                recurso_tipo="execucao", recurso_id=execucao.id,
                detalhe={
                    "automacao": automacao.nome,
                    "porque": "o time não tem canal de mensageria com destinatário "
                    "configurado — a falha não pôde ser avisada a ninguém",
                },
            )
            return
        inst, destino = alvo
        texto = montar_texto(automacao.nome, _onde_parou(sessao, execucao), erro)
        token = (segredos_instrumento.decifrar(sessao, inst.id) or {}).get("token_bot")
        entregue = bool(token) and bool(telegram.enviar(token, destino, texto).get("ok"))
        registrar_evento(
            categoria="execucao",
            acao="falha.avisada" if entregue else "falha.aviso_nao_entregue",
            nivel="info" if entregue else "warning",
            recurso_tipo="execucao", recurso_id=execucao.id,
            detalhe={"automacao": automacao.nome, "instrumento": inst.nome},
        )
    except Exception as e:  # o aviso NUNCA derruba o caminho de erro que o chamou
        registrar_evento(
            categoria="execucao", acao="falha.aviso_quebrou", nivel="error",
            resultado="falha", erro=e, recurso_tipo="execucao",
            recurso_id=getattr(execucao, "id", None),
        )
