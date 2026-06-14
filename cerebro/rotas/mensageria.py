"""Endpoints da mensageria de mão dupla.

`POST /mensageria/{instrumento_id}/entrada` é PÚBLICO (o Telegram chama sem
login), no molde de `rotas/webhooks.py`. A origem é validada pelo `secret_token`
do Telegram (cabeçalho), quando o canal já foi conectado (Fase E). Responde 200
rápido (ack) e processa o turno em segundo plano — a chamada de LLM não pode
segurar a resposta ao Telegram.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mensageria import servico, telegram
from modelos import Instrumento
from sessao import obter_sessao

rotas = APIRouter(tags=["mensageria"])

# Tipos de canal cujo webhook este endpoint aceita (WhatsApp entra na Fase 2).
TIPOS_CANAL = {"enviar_telegram"}


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
