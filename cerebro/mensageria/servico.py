"""Roteamento da mensageria de mão dupla — a borda que coordena os turnos.

Recebe uma mensagem (já neutra), acha/cria a Conversa, registra na thread e,
no modo conversacional, roda UM turno do agente e entrega a resposta ao contato.
Reusa `executar_agente`, a resolução de chaves e o cofre de segredos — NÃO toca
o núcleo de orquestração. Ver `docs/MENSAGERIA-PLANO.md`.

Modo conversacional (Fase 1, foco inicial): o agente atendente é o que tem este
instrumento de canal no cinto. O instrumento de canal serve de AMARRAÇÃO (diz
qual agente atende); a resposta é enviada pela BORDA (não pelo agente), então o
instrumento de canal é filtrado das ferramentas daquele turno para não haver
envio em dobro. O modo fluxo (cadeia com pausa/retoma) entra depois.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import segredos_instrumento
from chaves import resolver_chaves_por_time
from mensageria import telegram
from modelos import Agente, AgenteInstrumento, Conversa, Instrumento, MensagemConversa
from orquestracao.agente import executar_agente
from orquestracao.llm import usar_chaves
from sessao import CriadorDeSessao

# Tipos de instrumento que são canais de mensageria (a borda os opera; o agente
# não os aciona como ferramenta no modo conversacional).
CANAIS_TIPOS = {"enviar_telegram", "enviar_whatsapp"}

# Quantas mensagens da thread injetar como histórico no turno do agente.
LIMITE_HISTORICO = 20

_ROTULOS = {
    "contato": "Cliente",
    "agente": "Você",
    "operador": "Operador (humano)",
    "sistema": "Sistema",
}


def agente_atendente(sessao: Session, instrumento_id: uuid.UUID) -> Agente | None:
    """O agente que atende este canal: o que tem o instrumento no cinto. Se mais
    de um o tiver (incomum), usa o mais antigo (e isso é uma limitação conhecida
    da v1 — um canal deveria ter um atendente)."""
    return sessao.scalars(
        select(Agente)
        .join(AgenteInstrumento, AgenteInstrumento.agente_id == Agente.id)
        .where(AgenteInstrumento.instrumento_id == instrumento_id)
        .order_by(Agente.criado_em)
    ).first()


def _cinto_sem_canais(sessao: Session, agente_id: uuid.UUID) -> list[Instrumento]:
    """O cinto do agente, COM os segredos decifrados em memória, mas SEM os
    instrumentos de canal (a borda envia a resposta; o agente não envia)."""
    cinto = list(
        sessao.scalars(
            select(Instrumento)
            .join(AgenteInstrumento, AgenteInstrumento.instrumento_id == Instrumento.id)
            .where(AgenteInstrumento.agente_id == agente_id)
            .where(Instrumento.tipo.notin_(CANAIS_TIPOS))
        ).all()
    )
    segredos_instrumento.anexar_aos_instrumentos(sessao, cinto)
    return cinto


def _montar_entrada(sessao: Session, conversa: Conversa) -> str:
    """A entrada do turno: um enquadramento curto + o histórico recente da
    conversa (a última linha é a mensagem mais recente do contato)."""
    msgs = list(
        reversed(
            sessao.scalars(
                select(MensagemConversa)
                .where(MensagemConversa.conversa_id == conversa.id)
                .order_by(MensagemConversa.criado_em.desc())
                .limit(LIMITE_HISTORICO)
            ).all()
        )
    )
    linhas = [f"{_ROTULOS.get(m.papel, m.papel)}: {m.conteudo or ''}" for m in msgs]
    nome = conversa.contato_nome or "o cliente"
    enquadramento = (
        f"Você está atendendo {nome} numa conversa pelo Telegram. Abaixo está o "
        "histórico (a última linha é a mensagem mais recente). Responda em "
        "português, de forma natural e direta, à última mensagem do cliente. "
        "Escreva APENAS a sua resposta ao cliente — ela será enviada como está."
    )
    return enquadramento + "\n\n---\n" + "\n".join(linhas)


def _conversa_viva(
    sessao: Session, instrumento_id: uuid.UUID, contato_chave: str
) -> Conversa | None:
    return sessao.scalars(
        select(Conversa)
        .where(Conversa.instrumento_id == instrumento_id)
        .where(Conversa.contato_chave == contato_chave)
        .where(Conversa.estado != "fechada")
    ).first()


def registrar_entrada(
    sessao: Session, instrumento: Instrumento, msg: telegram.MensagemEntrante
) -> tuple[Conversa, bool]:
    """Parte rápida (no request): acha/cria a Conversa, grava a mensagem do
    contato e decide se há um turno de bot a processar. Devolve
    `(conversa, deve_processar)`. `deve_processar` é False quando um humano
    assumiu a conversa ou não há agente atendente."""
    conversa = _conversa_viva(sessao, instrumento.id, msg.contato_chave)
    if conversa is None:
        agente = agente_atendente(sessao, instrumento.id)
        conversa = Conversa(
            instrumento_id=instrumento.id,
            contato_chave=msg.contato_chave,
            contato_nome=msg.contato_nome,
            estado="aberta",
            destino_tipo="agente" if agente else None,
            destino_id=agente.id if agente else None,
        )
        sessao.add(conversa)
        sessao.flush()
    elif msg.contato_nome and conversa.contato_nome != msg.contato_nome:
        conversa.contato_nome = msg.contato_nome

    # Conteúdo do contato (texto; mídia/voz vira aviso até a Fase H tratar).
    conteudo = msg.texto
    if conteudo is None:
        conteudo = "[mensagem de voz — ainda não consigo ouvir áudio]" if (
            msg.midia or {}
        ).get("tipo") == "voz" else "[conteúdo não textual — ainda não consigo ler]"
    sessao.add(
        MensagemConversa(
            conversa_id=conversa.id, papel="contato", conteudo=conteudo, midia=msg.midia
        )
    )

    deve_processar = (
        conversa.estado not in ("humano_assumiu", "fechada")
        and conversa.destino_tipo == "agente"
        and conversa.destino_id is not None
    )
    if deve_processar:
        conversa.estado = "bot_respondendo"
    sessao.commit()
    return conversa, deve_processar


def processar_turno(conversa_id: uuid.UUID) -> None:
    """Roda UM turno do agente para a conversa e entrega a resposta ao contato.
    Pensado para rodar em segundo plano (a resposta ao Telegram já foi dada).
    Abre a própria sessão de banco (a do request já fechou)."""
    sessao = CriadorDeSessao()
    try:
        conversa = sessao.get(Conversa, conversa_id)
        if conversa is None or conversa.estado in ("humano_assumiu", "fechada"):
            return
        if conversa.destino_tipo != "agente" or conversa.destino_id is None:
            return
        agente = sessao.get(Agente, conversa.destino_id)
        instrumento = sessao.get(Instrumento, conversa.instrumento_id)
        if agente is None or instrumento is None:
            return

        token = segredos_instrumento.decifrar(sessao, instrumento.id).get("token_bot", "")
        cinto = _cinto_sem_canais(sessao, agente.id)
        entrada = _montar_entrada(sessao, conversa)
        chaves, _ = resolver_chaves_por_time(sessao, agente.time_id)

        try:
            with usar_chaves(chaves):
                resultado = executar_agente(agente, cinto, entrada)
            saida = (resultado.get("saida") or "").strip()
        except Exception as e:  # falha de LLM/instrumento — não morre em silêncio
            sessao.add(
                MensagemConversa(
                    conversa_id=conversa.id,
                    papel="sistema",
                    conteudo=f"Falha ao gerar a resposta: {e}",
                    entregue=False,
                )
            )
            conversa.estado = "aberta"
            sessao.commit()
            return

        if not saida:
            conversa.estado = "aberta"
            sessao.commit()
            return

        # A BORDA entrega a resposta (não o agente).
        entregue = True
        try:
            envio = telegram.enviar(token, conversa.contato_chave, saida)
            entregue = bool(envio.get("ok"))
        except Exception as e:
            entregue = False
            sessao.add(
                MensagemConversa(
                    conversa_id=conversa.id,
                    papel="sistema",
                    conteudo=f"Falha ao enviar pelo Telegram: {e}",
                    entregue=False,
                )
            )

        sessao.add(
            MensagemConversa(
                conversa_id=conversa.id, papel="agente", conteudo=saida, entregue=entregue
            )
        )
        conversa.turnos = (conversa.turnos or 0) + 1
        conversa.estado = "aguardando_resposta"
        sessao.commit()
    finally:
        sessao.close()
