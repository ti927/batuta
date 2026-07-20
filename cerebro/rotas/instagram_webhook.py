"""Receptor do webhook de COMENTÁRIOS do Instagram (GAP 2) — nível do app.

A Meta chama UMA URL com os comentários de TODAS as contas conectadas (não é uma
URL por automação como o webhook genérico de `rotas/webhooks.py`). Este receptor:

- GET  /instagram/webhook  → handshake de verificação (devolve `hub.challenge` se
  o `hub.verify_token` bater com o do servidor).
- POST /instagram/webhook  → valida a assinatura `X-Hub-Signature-256`, responde
  200 NA HORA e processa em segundo plano (fast-ack: senão a Meta reentrega e
  acaba desligando o webhook).

Em segundo plano, para cada comentário: resolve a conta (`ig_user_id` → credencial
`instagram` → organização, pelo `resumo` em texto claro — sem descriptografar),
aplica os guardas anti-loop (só comentário de topo; ignora a resposta da própria
conta), acha as automações ATIVAS com gatilho `comentario_instagram` cujos filtros
casam, e dispara UMA execução por automação — com DEDUPE (a Meta reentrega) e TETO
(protege custo num post viral), via a tabela `eventos_comentario_instagram`.

É BORDA: reusa `criar_execucao` + a fila; o núcleo de orquestração não é tocado.
"""

import json
import uuid  # noqa: F401  (mantém simetria com as demais rotas; ids vêm do banco)
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import fila
import instagram_webhook as ig
from modelos import Automacao, Credencial, EventoComentarioInstagram, Time
from orquestracao.disparo import criar_execucao
from sessao import CriadorDeSessao

rotas = APIRouter(tags=["instagram"])

TIPO_GATILHO = "comentario_instagram"
# Teto de disparos/hora por automação quando o gatilho não define o seu. Protege o
# custo de IA num post que viralizou. `teto_por_hora=0` no gatilho = sem teto.
TETO_POR_HORA_PADRAO = 50
JANELA_TETO = timedelta(hours=1)


# ───────────────────────────── Pontas HTTP ──────────────────────────────────


@rotas.get("/instagram/webhook")
def verificar(request: Request):
    """Handshake da Meta: devolve o `hub.challenge` se o verify_token bater."""
    params = request.query_params
    modo = params.get("hub.mode")
    token = params.get("hub.verify_token")
    desafio = params.get("hub.challenge")
    esperado = ig.token_de_verificacao()
    if modo == "subscribe" and esperado and token == esperado:
        return PlainTextResponse(desafio or "")
    return PlainTextResponse(
        "token de verificação inválido", status_code=status.HTTP_403_FORBIDDEN
    )


@rotas.post("/instagram/webhook")
async def receber(request: Request, tarefas: BackgroundTasks):
    """Valida a assinatura e faz fast-ack. O trabalho pesado (LLM/execução) roda em
    segundo plano — a resposta à Meta não pode esperar por ele."""
    corpo = await request.body()
    if not ig.verificar_assinatura(corpo, request.headers.get("X-Hub-Signature-256")):
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    tarefas.add_task(processar_entrada, corpo)
    return {"ok": True}


# ───────────────────────── Processamento (borda) ────────────────────────────


def processar_entrada(corpo: bytes) -> None:
    """Segundo plano: parseia o corpo cru e processa cada comentário. Abre a
    própria sessão (a da requisição já fechou)."""
    try:
        dados = json.loads(corpo.decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError:
        return
    comentarios = ig.extrair_comentarios(dados)
    if not comentarios:
        return
    sessao = CriadorDeSessao()
    try:
        disparou = False
        for comentario in comentarios:
            if _processar_comentario(sessao, comentario):
                disparou = True
        if disparou:
            fila.enfileirar()  # acorda os trabalhadores
    finally:
        sessao.close()


def _processar_comentario(sessao: Session, comentario: dict) -> bool:
    """Resolve a conta, aplica os guardas, acha as automações e dispara. Devolve
    True se criou ao menos uma execução."""
    ig_user_id = comentario["ig_user_id"]

    # Anti-loop 1: só comentários de TOPO. Resposta a comentário traz `parent_id` —
    # inclui a resposta que o próprio agente publica (evita a bola de neve).
    if comentario.get("parent_id"):
        return False
    # Anti-loop 2: descarta o comentário feito pela PRÓPRIA conta (ela reagindo a si).
    if comentario.get("autor_id") and comentario["autor_id"] == ig_user_id:
        return False

    # A MESMA conta do Instagram pode estar conectada em VÁRIAS organizações (cada
    # uma com sua credencial e suas automações). Consideramos TODAS — senão um
    # comentário resolveria numa org à toa e não acharia a automação da outra.
    creds = _credenciais_da_conta(sessao, ig_user_id)
    if not creds:
        return False  # conta não conectada aqui: ignora em silêncio (correto)

    disparou = False
    for auto, cred in _automacoes_que_casam(sessao, creds, comentario):
        if _registrar_e_disparar(sessao, auto, cred, comentario):
            disparou = True
    return disparou


def _credenciais_da_conta(sessao: Session, ig_user_id: str) -> list[Credencial]:
    """TODAS as credenciais `instagram` cujo `ig_user_id` (no `resumo`, texto claro)
    bate — a mesma conta pode estar em mais de uma organização. Mesma leitura do
    `resumo` que o upsert do OAuth faz (fonte única do formato)."""
    return [
        c
        for c in sessao.scalars(
            select(Credencial).where(Credencial.tipo == "instagram")
        )
        if (c.resumo or {}).get("ig_user_id", {}).get("valor") == ig_user_id
        and c.organizacao_id is not None
    ]


def _automacoes_que_casam(
    sessao: Session, creds: list[Credencial], comentario: dict
) -> list[tuple[Automacao, Credencial]]:
    """Pares (automação, credencial) das automações ATIVAS de comentário, nas orgs
    das credenciais desta conta, cujo `credencial_id` aponta para UMA delas e cujos
    filtros (posts + palavra-chave) casam este comentário. Um gatilho sem conta
    (recém-criado ou cópia duplicada "a conectar") não aponta para nenhuma → nunca
    casa, então nunca dispara indevidamente."""
    cred_por_id = {str(c.id): c for c in creds}
    orgs = {c.organizacao_id for c in creds}
    autos = sessao.scalars(
        select(Automacao)
        .join(Time, Time.id == Automacao.time_id)
        .where(
            Time.organizacao_id.in_(orgs),
            Automacao.tipo_gatilho == TIPO_GATILHO,
            Automacao.ativa.is_(True),
        )
    ).all()
    pares: list[tuple[Automacao, Credencial]] = []
    for auto in autos:
        cred = cred_por_id.get(
            str((auto.configuracao_gatilho or {}).get("credencial_id") or "")
        )
        if cred is not None and _casa_filtro(auto, comentario):
            pares.append((auto, cred))
    return pares


def _casa_filtro(auto: Automacao, comentario: dict) -> bool:
    """Filtros de POSTS + PALAVRA-CHAVE do `configuracao_gatilho` (a conta já foi
    resolvida antes, em `_automacoes_que_casam`)."""
    cfg = auto.configuracao_gatilho or {}
    midias = cfg.get("midias", "todas")
    if midias != "todas":
        mid = comentario.get("media_id")
        if not isinstance(midias, list) or mid is None or mid not in midias:
            return False
    pc = cfg.get("palavra_chave")
    if pc and pc.strip():
        if pc.strip().lower() not in (comentario.get("texto") or "").lower():
            return False
    return True


def _teto(auto: Automacao) -> int | None:
    """O teto/hora desta automação: o do gatilho, ou o padrão. `<=0` = sem teto."""
    v = (auto.configuracao_gatilho or {}).get("teto_por_hora", TETO_POR_HORA_PADRAO)
    try:
        v = int(v)
    except (TypeError, ValueError):
        return TETO_POR_HORA_PADRAO
    return v if v > 0 else None


def _registrar_e_disparar(
    sessao: Session, auto: Automacao, cred: Credencial, comentario: dict
) -> bool:
    """Aplica o teto, deduplica e dispara. Devolve True se criou a execução."""
    teto = _teto(auto)
    if teto is not None:
        desde = datetime.now(timezone.utc) - JANELA_TETO
        qtd = (
            sessao.scalar(
                select(func.count())
                .select_from(EventoComentarioInstagram)
                .where(
                    EventoComentarioInstagram.automacao_id == auto.id,
                    EventoComentarioInstagram.criado_em >= desde,
                )
            )
            or 0
        )
        if qtd >= teto:
            return False  # estourou o teto na janela: descarta (protege custo)

    # DEDUPE: o índice único (comment_id, automacao_id) barra a reentrega da Meta.
    evento = EventoComentarioInstagram(
        comment_id=comentario["comment_id"],
        automacao_id=auto.id,
        organizacao_id=cred.organizacao_id,
        credencial_id=cred.id,
        media_id=comentario.get("media_id"),
    )
    sessao.add(evento)
    try:
        sessao.flush()
    except IntegrityError:
        sessao.rollback()  # já processei este comentário para esta automação
        return False

    # Dispara a execução (mesmo caminho do webhook genérico; `criar_execucao`
    # comita). Guarda o vínculo comentário→execução para auditoria.
    execucao = criar_execucao(sessao, auto, ig.montar_entrada(comentario), origem="webhook")
    evento.execucao_id = execucao.id
    sessao.commit()
    return True
