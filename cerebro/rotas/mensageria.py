"""Endpoints da mensageria de mão dupla.

`POST /mensageria/{instrumento_id}/entrada` é PÚBLICO (o Telegram chama sem
login), no molde de `rotas/webhooks.py`. A origem é validada pelo `secret_token`
do Telegram (cabeçalho), quando o canal já foi conectado (Fase E). Responde 200
rápido (ack) e processa o turno em segundo plano — a chamada de LLM não pode
segurar a resposta ao Telegram.
"""

import os
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import segredos_instrumento
from auth import usuario_atual
from esquemas import (
    ConversaComMensagens,
    ConversaLer,
    MensagemConversaLer,
    ResponderOperador,
)
from mensageria import servico, telegram
from modelos import Conversa, Execucao, Instrumento, MensagemConversa, Usuario
from rotas._comum import conversa_acessivel, instrumento_acessivel, time_acessivel
from sessao import obter_sessao

# Estados de execução já encerrados (alinhado a rotas/automacoes.py).
_ENCERRADOS = {"concluida", "falhou", "cancelada"}

rotas = APIRouter(tags=["mensageria"])

# Tipos de canal cujo webhook este endpoint aceita (WhatsApp entra na Fase 2).
TIPOS_CANAL = {"enviar_telegram"}


def _exigir_canal(inst: Instrumento) -> None:
    if inst.tipo not in TIPOS_CANAL:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Este instrumento não é um canal de Telegram."
        )


@rotas.post("/mensageria/{instrumento_id}/entrada")
async def entrada(
    instrumento_id: uuid.UUID,
    request: Request,
    tarefas: BackgroundTasks,
    sessao: Session = Depends(obter_sessao),
):
    instrumento = sessao.get(Instrumento, instrumento_id)
    if instrumento is None or instrumento.tipo not in TIPOS_CANAL:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Canal não encontrado.")

    # Valida a origem pelo secret token, quando o canal já foi conectado (Fase E).
    esperado = (instrumento.configuracao or {}).get("webhook_secret")
    if esperado:
        recebido = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if recebido != esperado:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Origem não autorizada.")

    try:
        corpo = await request.json()
    except Exception:
        corpo = None
    msg = telegram.extrair_update(corpo) if corpo is not None else None
    if msg is None:
        return {"ok": True}  # update não tratável (status, edição vazia): ignora

    conversa, deve_processar = servico.registrar_entrada(sessao, instrumento, msg)
    if deve_processar:
        tarefas.add_task(servico.processar_turno, conversa.id)
    return {"ok": True}


@rotas.post("/mensageria/{instrumento_id}/ativar-canal")
def ativar_canal(
    instrumento_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Conecta o canal: registra o webhook do bot apontando para o cérebro, com um
    secret token (gerado e guardado na config) que valida a origem das chamadas."""
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="operador")
    _exigir_canal(inst)
    token = segredos_instrumento.decifrar(sessao, inst.id).get("token_bot")
    if not token:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Configure o token do bot antes de conectar o canal.",
        )
    segredo = secrets.token_urlsafe(32)
    base = os.environ.get("CEREBRO_PUBLIC_URL", "http://localhost:8000").rstrip("/")
    url = f"{base}/mensageria/{inst.id}/entrada"
    resultado = telegram.configurar_webhook(token, url, segredo)
    if not resultado.get("ok"):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"O Telegram recusou o webhook: {resultado.get('description') or resultado}",
        )
    inst.configuracao = {**(inst.configuracao or {}), "webhook_secret": segredo}
    sessao.commit()
    return {"ok": True, "url": url}


@rotas.get("/mensageria/{instrumento_id}/canal")
def status_canal(
    instrumento_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Estado do canal: se já foi conectado (secret guardado) e o que o Telegram
    reporta do webhook (para a UI confirmar)."""
    inst = instrumento_acessivel(sessao, usuario, instrumento_id)
    _exigir_canal(inst)
    token = segredos_instrumento.decifrar(sessao, inst.id).get("token_bot")
    conectado = bool((inst.configuracao or {}).get("webhook_secret"))
    info = telegram.info_webhook(token) if token else {"ok": False}
    return {
        "conectado": conectado,
        "tem_token": bool(token),
        "webhook": info.get("result") if info.get("ok") else None,
    }


# ─────────────────────── Inbox e transferência (Fase F) ──────────────────────


@rotas.get("/times/{time_id}/conversas", response_model=list[ConversaLer])
def listar_conversas(
    time_id: uuid.UUID,
    estado: str | None = None,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """A caixa de entrada do time: as conversas dos canais deste time, mais
    recentes primeiro. Filtro opcional por estado."""
    time_acessivel(sessao, usuario, time_id)
    consulta = (
        select(Conversa)
        .join(Instrumento, Instrumento.id == Conversa.instrumento_id)
        .where(Instrumento.time_id == time_id)
        .order_by(Conversa.atualizado_em.desc())
    )
    if estado:
        consulta = consulta.where(Conversa.estado == estado)
    return sessao.scalars(consulta).all()


@rotas.get("/conversas/{conversa_id}", response_model=ConversaComMensagens)
def obter_conversa(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Uma conversa com sua thread completa (a tela da conversa)."""
    conversa = conversa_acessivel(sessao, usuario, conversa_id)
    mensagens = sessao.scalars(
        select(MensagemConversa)
        .where(MensagemConversa.conversa_id == conversa.id)
        .order_by(MensagemConversa.criado_em)
    ).all()
    base = ConversaLer.model_validate(conversa).model_dump()
    return ConversaComMensagens(
        **base, mensagens=[MensagemConversaLer.model_validate(m) for m in mensagens]
    )


@rotas.post("/conversas/{conversa_id}/assumir", response_model=ConversaLer)
def assumir(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """O operador assume a conversa: o bot cala (estado `humano_assumiu`) e, se
    houver uma execução de fluxo viva, ela é cancelada (cooperativo)."""
    conversa = conversa_acessivel(sessao, usuario, conversa_id, minimo="operador")
    conversa.estado = "humano_assumiu"
    conversa.atribuida_a = usuario.id
    if conversa.execucao_id:
        execucao = sessao.get(Execucao, conversa.execucao_id)
        if execucao and execucao.estado not in _ENCERRADOS:
            execucao.estado = "cancelada"
            execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.add(
        MensagemConversa(
            conversa_id=conversa.id,
            papel="sistema",
            conteudo=f"{usuario.nome} assumiu a conversa.",
        )
    )
    sessao.commit()
    sessao.refresh(conversa)
    return conversa


@rotas.post(
    "/conversas/{conversa_id}/responder-operador", response_model=MensagemConversaLer
)
def responder_operador(
    conversa_id: uuid.UUID,
    dados: ResponderOperador,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """O operador envia uma mensagem ao contato pela conversa (pelo bot do canal)."""
    conversa = conversa_acessivel(sessao, usuario, conversa_id, minimo="operador")
    instrumento = sessao.get(Instrumento, conversa.instrumento_id)
    token = segredos_instrumento.decifrar(sessao, instrumento.id).get("token_bot")
    if not token:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Canal sem token configurado."
        )
    entregue = True
    try:
        envio = telegram.enviar(token, conversa.contato_chave, dados.texto)
        entregue = bool(envio.get("ok"))
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Falha ao enviar pelo Telegram: {e}"
        )
    msg = MensagemConversa(
        conversa_id=conversa.id, papel="operador", conteudo=dados.texto, entregue=entregue
    )
    sessao.add(msg)
    # Mantém a conversa como assumida pelo humano enquanto ele responde.
    if conversa.estado != "humano_assumiu":
        conversa.estado = "humano_assumiu"
        conversa.atribuida_a = usuario.id
    sessao.commit()
    sessao.refresh(msg)
    return msg


@rotas.post("/conversas/{conversa_id}/devolver", response_model=ConversaLer)
def devolver(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Devolve a conversa ao bot: a próxima mensagem do contato volta a ser
    atendida automaticamente."""
    conversa = conversa_acessivel(sessao, usuario, conversa_id, minimo="operador")
    conversa.estado = "aberta"
    conversa.atribuida_a = None
    sessao.add(
        MensagemConversa(
            conversa_id=conversa.id,
            papel="sistema",
            conteudo=f"{usuario.nome} devolveu a conversa ao atendimento automático.",
        )
    )
    sessao.commit()
    sessao.refresh(conversa)
    return conversa


@rotas.post("/conversas/{conversa_id}/fechar", response_model=ConversaLer)
def fechar(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Encerra a conversa. Uma nova mensagem do mesmo contato abre outra conversa."""
    conversa = conversa_acessivel(sessao, usuario, conversa_id, minimo="operador")
    conversa.estado = "fechada"
    sessao.commit()
    sessao.refresh(conversa)
    return conversa
