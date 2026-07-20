"""Webhook de entrada — Tarefa 4.7.

Um sistema externo (o ERP da empresa, outro app) aciona uma automação por uma
URL, sem login: é o gatilho disparado por uma máquina, não por uma pessoa nem
pelo relógio (PRODUTO §12). Só dispara automações cujo gatilho é 'webhook' e
que estejam `ativa`. O corpo recebido vira a entrada da cadeia: o campo
`entrada`, se houver; senão, o corpo inteiro como texto.
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import fila
from modelos import Automacao
from orquestracao.disparo import criar_execucao
from sessao import obter_sessao

rotas = APIRouter(tags=["webhooks"])

TIPO_WEBHOOK = "webhook"


def _extrair_entrada(bruto: bytes) -> str:
    """Deriva o texto de entrada do corpo cru recebido do sistema externo."""
    texto = bruto.decode("utf-8", errors="replace").strip()
    if not texto:
        return ""
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return texto  # corpo não-JSON: usa o cru
    if isinstance(dados, dict) and isinstance(dados.get("entrada"), str):
        return dados["entrada"]
    return texto  # JSON sem campo 'entrada': usa o corpo inteiro


@rotas.post("/webhooks/automacoes/{automacao_id}")
async def receber(
    automacao_id: uuid.UUID,
    request: Request,
    sessao: Session = Depends(obter_sessao),
):
    auto = sessao.get(Automacao, automacao_id)
    if auto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Automação não encontrada")
    if auto.tipo_gatilho != TIPO_WEBHOOK:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Esta automação não tem gatilho de webhook."
        )
    if not auto.ativa:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta automação está desativada.")

    entrada = _extrair_entrada(await request.body())
    # Enfileira e responde na hora (ack ao sistema externo); a fila roda a cadeia.
    execucao = criar_execucao(sessao, auto, entrada, origem="webhook")
    fila.enfileirar()
    return {"execucao_id": str(execucao.id), "estado": execucao.estado}
