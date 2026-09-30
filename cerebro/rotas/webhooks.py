"""Webhook de entrada — Tarefa 4.7, endurecido em 2026-09-30.

Um sistema externo (o ERP da empresa, uma rede social, outro app) aciona uma
automação por uma URL, sem login: é o gatilho disparado por uma máquina, não por uma
pessoa nem pelo relógio (PRODUTO §12). Só dispara automações cujo gatilho é
'webhook' e que estejam `ativa`. O corpo recebido vira a entrada da cadeia: o campo
`entrada`, se houver; senão, o corpo inteiro como texto.

Antes de disparar, aplica as regras de `webhook_entrada` nesta ordem: ASSINATURA
(se a automação tem segredo) → FILTROS (tipo do aviso, eco da própria conta, campos)
→ REPETIDO (o mesmo aviso reentregue) → TETO por hora. Aviso ignorado responde 200
com o motivo — responder erro faria o serviço reenviar o que foi ignorado de
propósito. Assinatura errada responde 401 e fica no banco de logs.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import cofre
import fila
import webhook_entrada as regras
from modelos import Automacao, EventoWebhook
from observabilidade.escritor import registrar_evento
from orquestracao.disparo import criar_execucao
from sessao import obter_sessao

rotas = APIRouter(tags=["webhooks"])

TIPO_WEBHOOK = "webhook"
JANELA_TETO = timedelta(hours=1)


def _ignorado(auto: Automacao, motivo: str, evento_id: str | None = None) -> dict:
    registrar_evento(
        categoria="webhook", acao="webhook.ignorado", nivel="info",
        recurso_tipo="automacao", recurso_id=str(auto.id),
        detalhe={"motivo": motivo, "evento_id": evento_id},
    )
    return {"ignorado": True, "motivo": motivo}


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

    corpo = await request.body()
    cabecalhos = dict(request.headers)
    cfg = auto.configuracao_gatilho or {}

    # 1. ASSINATURA — com segredo guardado, aviso sem a assinatura certa não entra.
    if auto.segredo_webhook_cifrado:
        assinatura = regras.cabecalho_da_assinatura(
            cabecalhos, cfg.get("cabecalho_assinatura")
        )
        if not regras.assinatura_confere(
            corpo, cofre.decifrar(auto.segredo_webhook_cifrado), assinatura
        ):
            registrar_evento(
                categoria="webhook", acao="webhook.assinatura_recusada", nivel="warning",
                recurso_tipo="automacao", recurso_id=str(auto.id),
                detalhe={"tinha_assinatura": assinatura is not None},
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Assinatura inválida.")

    dados = regras.ler_json(corpo)
    evento_id = regras.id_do_evento(cabecalhos, dados, corpo)

    # 2. FILTROS — tipo do aviso, eco da própria conta, campos.
    motivo = regras.motivo_para_ignorar(cfg, cabecalhos, dados)
    if motivo:
        return _ignorado(auto, motivo, evento_id)

    # 3. TETO por hora — protege o custo num pico de avisos.
    teto = regras.teto_por_hora(cfg)
    if teto is not None:
        desde = datetime.now(timezone.utc) - JANELA_TETO
        qtd = sessao.scalar(
            select(func.count())
            .select_from(EventoWebhook)
            .where(EventoWebhook.automacao_id == auto.id, EventoWebhook.criado_em >= desde)
        ) or 0
        if qtd >= teto:
            registrar_evento(
                categoria="webhook", acao="webhook.teto_atingido", nivel="warning",
                recurso_tipo="automacao", recurso_id=str(auto.id),
                detalhe={"teto_por_hora": teto, "evento_id": evento_id},
            )
            return {"ignorado": True, "motivo": f"passou do teto de {teto} por hora"}

    # 4. REPETIDO — o índice único (automação, id do aviso) barra a reentrega.
    registro = EventoWebhook(automacao_id=auto.id, evento_id=evento_id)
    sessao.add(registro)
    try:
        sessao.flush()
    except IntegrityError:
        sessao.rollback()
        return {"ignorado": True, "motivo": "aviso repetido (já recebido)"}

    # Enfileira e responde na hora (ack ao sistema externo); a fila roda a cadeia.
    execucao = criar_execucao(
        sessao, auto, regras.extrair_entrada(corpo, dados), origem="webhook"
    )
    registro.execucao_id = execucao.id
    sessao.commit()
    fila.enfileirar()
    return {"execucao_id": str(execucao.id), "estado": execucao.estado}
