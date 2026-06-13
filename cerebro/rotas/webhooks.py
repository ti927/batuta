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
from sqlalchemy import select
from sqlalchemy.orm import Session

import fila
import storage
from canais import servico as servico_canal
from modelos import Automacao, Canal, Execucao, IdentidadeCanal, Time
from orquestracao.disparo import criar_execucao, retomar_execucao
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

    # Modo A: a mensagem é resposta a uma execução pausada esperando este contato
    # neste canal? (ambíguo → a mais recente). Reusa a espera-por-humano.
    execucao = sessao.scalars(
        select(Execucao)
        .where(
            Execucao.aguardando_canal_id == canal.id,
            Execucao.aguardando_identificador == msg.identificador_externo,
            Execucao.estado == "aguardando_humano",
        )
        .order_by(Execucao.criado_em.desc())
    ).first()
    if execucao is not None:
        registro.execucao_id = execucao.id
        # Commit ANTES do trabalho (possivelmente lento): grava a idempotência, de
        # modo que uma reentrega do Telegram durante a retomada caia no dedupe.
        sessao.commit()
        retomar_execucao(sessao, execucao, msg.texto or "")
        return {"ok": True, "modo": "A", "execucao_id": str(execucao.id)}

    # Modo B: iniciar um fluxo novo. Só para CONTATO CONHECIDO (cadastrado em
    # identidades_canal). Identidade desconhecida → ignora, mas fica logada.
    identidade = sessao.scalars(
        select(IdentidadeCanal).where(
            IdentidadeCanal.canal_id == canal.id,
            IdentidadeCanal.identificador_externo == msg.identificador_externo,
        )
    ).first()
    if identidade is None:
        sessao.commit()
        return {"ok": True, "ignorado": "identidade desconhecida"}

    # Há automação ativa da organização com gatilho 'mensagem_recebida' ligada a
    # este canal? Se sim, a mensagem inicia o fluxo (carimba a origem para a
    # resposta voltar a quem mandou — Modo A no futuro da mesma execução).
    auto = sessao.scalars(
        select(Automacao)
        .join(Time, Automacao.time_id == Time.id)
        .where(
            Time.organizacao_id == canal.organizacao_id,
            Automacao.tipo_gatilho == "mensagem_recebida",
            Automacao.ativa.is_(True),
            Automacao.configuracao_gatilho["canal_id"].astext == str(canal.id),
        )
    ).first()
    if auto is None:
        sessao.commit()
        return {"ok": True, "ignorado": "sem automação para este canal"}

    execucao = criar_execucao(sessao, auto, msg.texto or "")
    execucao.origem_canal_id = canal.id
    execucao.origem_identificador = msg.identificador_externo
    # Imagem na entrada (ex.: foto do recibo): baixa do provedor e guarda no
    # Storage; o agente a lê em runtime. Best-effort: sem imagem, segue só o texto.
    imagem = next((a for a in msg.anexos if a.tipo == "imagem"), None)
    if imagem is not None:
        try:
            conteudo, content_type = servico_canal.baixar_anexo(
                sessao, canal, imagem.ref
            )
            caminho = f"{canal.organizacao_id}/{execucao.id}/{imagem.ref}"
            storage.enviar(caminho, conteudo, content_type)
            execucao.entrada = {
                **(execucao.entrada or {}),
                "imagem": {"storage_path": caminho, "media_type": content_type},
            }
        except Exception:
            pass
    registro.execucao_id = execucao.id
    sessao.commit()
    fila.enfileirar()
    return {"ok": True, "modo": "B", "execucao_id": str(execucao.id)}
