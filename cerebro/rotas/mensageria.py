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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import segredos_instrumento
from auth import usuario_atual
from mensageria import servico, telegram
from modelos import Instrumento, Usuario
from rotas._comum import instrumento_acessivel
from sessao import obter_sessao

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
