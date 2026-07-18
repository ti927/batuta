"""Conectar Google por OAuth — sem colar token à mão.

Espelha `rotas/instagram.py`. Duas pontas:
- POST /organizacoes/{id}/google/iniciar  (operador+): devolve a URL de
  consentimento do Google, com um `state` CIFRADO (carrega de qual org/usuário é o
  pedido e tem prazo). A interface manda o navegador para essa URL.
- GET /google/oauth/callback  (PÚBLICA — quem chama é o navegador no retorno do
  Google, SEM Bearer): valida o `state`, troca o `code` por access+refresh token,
  cria/atualiza a credencial `google` da org e redireciona à tela de credenciais.

Reusa a fundação da caixa-forte: o tipo de credencial `google`, o cofre cifrado e a
renovação sob demanda (`google_oauth.garantir_token`, na borda). Núcleo intocado.
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
import google_oauth
from auth import usuario_atual
from instrumentos.base import FalhaInstrumento
from modelos import Credencial, Membro, Usuario
from rotas._comum import organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["google"])

# Janela entre clicar "Conectar Google" e o Google devolver o navegador. Curta: o
# `state` é descartável.
TTL_STATE_S = 600


# ─────────────────────────── Iniciar (autenticado) ──────────────────────────


@rotas.post("/organizacoes/{organizacao_id}/google/iniciar")
def iniciar(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Monta a URL de consentimento do Google para esta organização (operador+).
    Devolve `{url}`; a interface faz o navegador navegar até lá."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="operador")
    if not google_oauth.configurado():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "A conexão com o Google ainda não está configurada no servidor "
            "(faltam as credenciais do app do Google). Avise o administrador.",
        )
    state = cofre.cifrar(
        json.dumps({"org": str(organizacao_id), "usuario": str(usuario.id)})
    )
    return {"url": google_oauth.montar_url_autorizacao(state)}


# ─────────────────────────── Callback (público) ─────────────────────────────


def _front_base() -> str:
    origens = os.environ.get("INTERFACE_ORIGINS", "http://localhost:3000")
    return origens.split(",")[0].strip().rstrip("/")


def _voltar(organizacao_id: uuid.UUID | str, **params: str) -> RedirectResponse:
    """Redireciona o navegador de volta à tela de credenciais da org, com um
    parâmetro (`google=ok|erro`) que a interface usa para dar o aviso."""
    consulta = urlencode({k: v for k, v in params.items() if v})
    return RedirectResponse(
        f"{_front_base()}/organizacoes/{organizacao_id}/chaves?{consulta}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _org_do_state(state: str | None) -> uuid.UUID | None:
    if not state:
        return None
    try:
        dados = json.loads(cofre.decifrar_temporario(state, TTL_STATE_S))
        return uuid.UUID(dados["org"])
    except Exception:
        return None


@rotas.get("/google/oauth/callback")
def callback(
    sessao: Session = Depends(obter_sessao),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """Retorno do Google. Valida o `state`, troca o `code` por tokens e grava a
    credencial. Sempre redireciona o navegador de volta à interface."""
    if error:
        org = _org_do_state(state)
        if org is not None:
            return _voltar(org, google="erro", motivo=(error_description or error)[:200])
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"A autorização do Google falhou: {error}."
        )
    if not code or not state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Retorno do Google incompleto.")

    try:
        dados = json.loads(cofre.decifrar_temporario(state, TTL_STATE_S))
        organizacao_id = uuid.UUID(dados["org"])
        usuario_id = uuid.UUID(dados["usuario"])
    except Exception:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Pedido de conexão inválido ou expirado. Tente conectar de novo.",
        )

    papel = sessao.scalar(
        select(Membro.papel).where(
            Membro.usuario_id == usuario_id,
            Membro.organizacao_id == organizacao_id,
        )
    )
    if papel is None or papel == "observador":
        return _voltar(
            organizacao_id,
            google="erro",
            motivo="Sem permissão para conectar uma conta nesta organização.",
        )

    try:
        conta = google_oauth.conectar(code)
    except FalhaInstrumento as e:
        return _voltar(organizacao_id, google="erro", motivo=str(e)[:200])

    cred = _upsert_credencial(sessao, organizacao_id, conta)
    auditoria.registrar(
        sessao,
        usuario=sessao.get(Usuario, usuario_id),
        acao="credencial.google_conectada",
        recurso_tipo="credencial",
        recurso_id=cred.id,
        organizacao_id=organizacao_id,
        detalhe={"email": conta["email"], "escopos": conta["escopos"]},
    )
    sessao.commit()
    return _voltar(organizacao_id, google="ok", conta=conta["email"])


# ───────────────────────────── Gravação ─────────────────────────────────────


def _upsert_credencial(
    sessao: Session, organizacao_id: uuid.UUID, conta: dict
) -> Credencial:
    """Grava a conta Google conectada como credencial `google` da org.

    Reconexão da MESMA conta (mesmo `email`) atualiza os tokens na credencial
    existente — não cria duplicata. Conta nova vira uma credencial 'Google: email'."""
    email = conta["email"]
    existentes = list(
        sessao.scalars(
            select(Credencial).where(
                Credencial.organizacao_id == organizacao_id,
                Credencial.tipo == "google",
            )
        ).all()
    )
    alvo = next(
        (
            c
            for c in existentes
            if email and (c.resumo or {}).get("email", {}).get("valor") == email
        ),
        None,
    )
    if alvo is None:
        alvo = Credencial(
            organizacao_id=organizacao_id,
            nome=_nome_unico(sessao, organizacao_id, email),
            tipo="google",
            compartilhavel=False,
        )
        sessao.add(alvo)
    cofre_cred.gravar(
        alvo,
        {
            "access_token": conta["access_token"],
            "refresh_token": conta["refresh_token"],
            "email": email,
            "escopos": conta["escopos"],
        },
    )
    alvo.expira_em = conta["expira_em"]
    sessao.flush()
    return alvo


def _nome_unico(sessao: Session, organizacao_id: uuid.UUID, email: str) -> str:
    """'Google: email', com sufixo (2), (3)… se já houver esse nome na org."""
    base = f"Google: {email}" if email else "Google"
    nome, i = base, 2
    while sessao.scalar(
        select(Credencial.id).where(
            Credencial.organizacao_id == organizacao_id, Credencial.nome == nome
        )
    ):
        nome, i = f"{base} ({i})", i + 1
    return nome
