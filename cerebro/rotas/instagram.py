"""Conectar Instagram por OAuth (Business Login) — sem colar token à mão.

Duas pontas:
- POST /organizacoes/{id}/instagram/iniciar  (operador+): devolve a URL de
  consentimento da Meta, com um `state` CIFRADO (carrega de qual org/usuário é o
  pedido e tem prazo de validade). A interface manda o navegador para essa URL.
- GET /instagram/oauth/callback  (PÚBLICA — quem chama é o navegador no retorno
  da Meta, SEM Bearer): valida o `state`, troca o `code` por um token de 60 dias,
  cria/atualiza a credencial `instagram` da org e redireciona de volta à tela de
  credenciais. A confiança vem do `state` (cifrado+TTL pelo cofre — só nós o
  emitimos a um operador+), revalidado contra o banco antes de gravar.

Reusa toda a fundação da caixa-forte: o tipo de credencial `instagram`, o cofre
cifrado e a renovação automática do agendador. Aqui só se acrescenta a "porta de
entrada" automática — o núcleo de orquestração não é tocado.
"""

import json
import os
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import cofre
import credenciais_cofre as cofre_cred
import instagram_oauth
from auth import usuario_atual
from instrumentos.base import FalhaInstrumento
from modelos import Credencial, Membro, Usuario
from rotas._comum import organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["instagram"])

# Janela entre clicar "Conectar Instagram" e a Meta devolver o navegador. Curta:
# o `state` é descartável.
TTL_STATE_S = 600


# ─────────────────────────── Iniciar (autenticado) ──────────────────────────


@rotas.post("/organizacoes/{organizacao_id}/instagram/iniciar")
def iniciar(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Monta a URL de consentimento da Meta para esta organização (operador+).
    Devolve `{url}`; a interface faz o navegador navegar até lá."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="operador")
    if not instagram_oauth.configurado():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "A conexão com o Instagram ainda não está configurada no servidor "
            "(faltam as credenciais do app da Meta). Avise o administrador.",
        )
    state = cofre.cifrar(
        json.dumps({"org": str(organizacao_id), "usuario": str(usuario.id)})
    )
    return {"url": instagram_oauth.montar_url_autorizacao(state)}


# ─────────────────────────── Callback (público) ─────────────────────────────


def _front_base() -> str:
    """A origem da interface (1ª de INTERFACE_ORIGINS) — para onde o navegador
    volta depois do consentimento."""
    origens = os.environ.get("INTERFACE_ORIGINS", "http://localhost:3000")
    return origens.split(",")[0].strip().rstrip("/")


def _voltar(organizacao_id: uuid.UUID | str, **params: str) -> RedirectResponse:
    """Redireciona o navegador de volta à tela de credenciais da org, com um
    parâmetro (`instagram=ok|erro`) que a interface usa para dar o aviso."""
    consulta = urlencode({k: v for k, v in params.items() if v})
    return RedirectResponse(
        f"{_front_base()}/organizacoes/{organizacao_id}/chaves?{consulta}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _org_do_state(state: str | None) -> uuid.UUID | None:
    """Tenta extrair a org de um `state` (para conseguir redirecionar mesmo num
    erro). None se o state falta/é inválido/expirou."""
    if not state:
        return None
    try:
        dados = json.loads(cofre.decifrar_temporario(state, TTL_STATE_S))
        return uuid.UUID(dados["org"])
    except Exception:
        return None


@rotas.get("/instagram/oauth/callback")
def callback(
    sessao: Session = Depends(obter_sessao),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """Retorno da Meta. Valida o `state`, troca o `code` por token de 60 dias e
    grava a credencial. Sempre redireciona o navegador de volta à interface."""
    # 1. O usuário negou / a Meta devolveu erro.
    if error:
        org = _org_do_state(state)
        if org is not None:
            return _voltar(
                org, instagram="erro", motivo=(error_description or error)[:200]
            )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A autorização do Instagram falhou: {error}.",
        )
    if not code or not state:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Retorno do Instagram incompleto."
        )

    # 2. Valida o `state` (cifrado + prazo). Inválido/expirado → pede para refazer.
    try:
        dados = json.loads(cofre.decifrar_temporario(state, TTL_STATE_S))
        organizacao_id = uuid.UUID(dados["org"])
        usuario_id = uuid.UUID(dados["usuario"])
    except Exception:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Pedido de conexão inválido ou expirado. Tente conectar de novo.",
        )

    # 3. Revalida a permissão (o usuário ainda é operador+ na org?) — o `state` é
    #    confiável, mas o papel pode ter mudado nesse meio-tempo.
    papel = sessao.scalar(
        select(Membro.papel).where(
            Membro.usuario_id == usuario_id,
            Membro.organizacao_id == organizacao_id,
        )
    )
    if papel is None or papel == "observador":
        return _voltar(
            organizacao_id,
            instagram="erro",
            motivo="Sem permissão para conectar uma conta nesta organização.",
        )

    # 4. Troca o code pelo token de 60 dias (+ identidade da conta).
    try:
        conta = instagram_oauth.conectar(code)
    except FalhaInstrumento as e:
        return _voltar(organizacao_id, instagram="erro", motivo=str(e)[:200])

    # 5. Cria/atualiza a credencial e audita.
    cred = _upsert_credencial(sessao, organizacao_id, conta)
    auditoria.registrar(
        sessao,
        usuario=sessao.get(Usuario, usuario_id),
        acao="credencial.instagram_conectada",
        recurso_tipo="credencial",
        recurso_id=cred.id,
        organizacao_id=organizacao_id,
        detalhe={"username": conta["username"], "ig_user_id": conta["ig_user_id"]},
    )
    sessao.commit()
    return _voltar(organizacao_id, instagram="ok", conta=conta["username"])


# ───────────────────────────── Gravação ─────────────────────────────────────


def _upsert_credencial(
    sessao: Session, organizacao_id: uuid.UUID, conta: dict
) -> Credencial:
    """Grava a conta conectada como credencial `instagram` da org.

    Reconexão da MESMA conta (mesmo `ig_user_id`) atualiza o token na credencial
    existente — não cria duplicata. Conta nova vira uma credencial nova com nome
    único 'Instagram: @usuario'."""
    ig_user_id = conta["ig_user_id"]
    existentes = list(
        sessao.scalars(
            select(Credencial).where(
                Credencial.organizacao_id == organizacao_id,
                Credencial.tipo == "instagram",
            )
        ).all()
    )
    alvo = next(
        (
            c
            for c in existentes
            if (c.resumo or {}).get("ig_user_id", {}).get("valor") == ig_user_id
        ),
        None,
    )
    if alvo is None:
        alvo = Credencial(
            organizacao_id=organizacao_id,
            nome=_nome_unico(sessao, organizacao_id, conta["username"]),
            tipo="instagram",
            compartilhavel=False,
        )
        sessao.add(alvo)
    cofre_cred.gravar(alvo, {"token": conta["token"], "ig_user_id": ig_user_id})
    alvo.expira_em = conta["expira_em"]
    sessao.flush()
    return alvo


def _nome_unico(
    sessao: Session, organizacao_id: uuid.UUID, username: str
) -> str:
    """'Instagram: @user', com sufixo (2), (3)… se já houver esse nome na org (o
    índice org+nome é único)."""
    base = f"Instagram: @{username}" if username else "Instagram"
    nome, i = base, 2
    while sessao.scalar(
        select(Credencial.id).where(
            Credencial.organizacao_id == organizacao_id, Credencial.nome == nome
        )
    ):
        nome, i = f"{base} ({i})", i + 1
    return nome
