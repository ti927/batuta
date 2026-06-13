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
from canais import servico as servico_canal
from modelos import Automacao, Canal
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
    execucao = criar_execucao(sessao, auto, entrada)
    fila.enfileirar()
    return {"execucao_id": str(execucao.id), "estado": execucao.estado}


@rotas.post("/canais/{canal_id}/webhook")
async def receber_canal(
    canal_id: uuid.UUID,
    request: Request,
    sessao: Session = Depends(obter_sessao),
):
    """Entrada de um canal de mensageria (o Telegram chama isto a cada mensagem).

    Público, idempotente e tolerante: o provedor espera 200 — qualquer coisa que
    não tratamos (canal inativo, evento sem mensagem, update repetido) é ignorada
    com 200 para não gerar reentrega. Aqui só NORMALIZA e REGISTRA; o roteamento
    Modo A (resposta a execução pausada) e Modo B (inicia fluxo) entra nos Passos
    6 e 7.
    """
    canal = sessao.get(Canal, canal_id)
    if canal is None or not canal.ativo:
        return {"ok": True, "ignorado": "canal desconhecido ou inativo"}
    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError):
        return {"ok": True, "ignorado": "corpo não-JSON"}

    msg = servico_canal.normalizar_entrada(canal, payload)
    if msg is None:
        return {"ok": True, "ignorado": "evento sem mensagem"}

    registro = servico_canal.registrar_entrada(sessao, canal, msg)
    if registro is None:
        return {"ok": True, "duplicado": True}  # idempotência: update já processado
    sessao.commit()
    return {"ok": True, "mensagem_id": str(registro.id)}
