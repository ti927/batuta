"""Identidade e autorização da Etapa 2 (Fase 6).

Liga o token já validado (`auth_supabase`) a um `Usuario` do banco e oferece a
checagem de papel por organização (admin > operador > observador). É a CAMADA DE
ACESSO — o núcleo de orquestração não é tocado.

A revogação imediata (usuário desativado ou papel removido) é coberta aqui, e não
no token: `usuario_atual` relê `usuarios.ativo` e os helpers releem `membros` a
cada requisição. Por isso a validação do token pode ser local (sem round-trip).
"""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth_supabase import TokenInvalido, validar_token
from modelos import Membro, Usuario
from observabilidade import contexto
from observabilidade.escritor import registrar_evento
from sessao import obter_sessao

# Hierarquia de papéis: um papel "contém" os de ordem menor.
ORDEM_PAPEL = {"observador": 1, "operador": 2, "admin": 3}


def _token_do_cabecalho(request: Request) -> str:
    cabecalho = request.headers.get("Authorization", "")
    if not cabecalho.startswith("Bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token de acesso ausente."
        )
    return cabecalho[len("Bearer ") :].strip()


def usuario_atual(
    request: Request, sessao: Session = Depends(obter_sessao)
) -> Usuario:
    """Dependência do FastAPI: resolve o `Usuario` autenticado a partir do
    Bearer token. 401 se o token falta/é inválido; 403 se não há cadastro para
    esse login (ninguém se autoinscreve — MIGRACAO §3.7) ou se está inativo."""
    token = _token_do_cabecalho(request)
    try:
        claims = validar_token(token)
    except TokenInvalido as e:
        registrar_evento(
            categoria="auth", acao="auth.negado", nivel="warning", resultado="falha",
            detalhe={"motivo": "token_invalido", "status": 401},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {e}")

    sub = claims.get("sub")
    try:
        auth_id = uuid.UUID(sub) if sub else None
    except (ValueError, TypeError):
        auth_id = None
    if auth_id is None:
        registrar_evento(
            categoria="auth", acao="auth.negado", nivel="warning", resultado="falha",
            detalhe={"motivo": "sem_sub", "status": 401},
        )
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token sem identificação de usuário."
        )

    usuario = sessao.scalars(
        select(Usuario).where(Usuario.auth_id == auth_id)
    ).first()
    if usuario is None:
        registrar_evento(
            categoria="auth", acao="auth.negado", nivel="warning", resultado="falha",
            detalhe={"motivo": "sem_cadastro", "status": 403},
        )
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Sem acesso ao Batuta. Peça um convite a um administrador.",
        )
    if not usuario.ativo:
        registrar_evento(
            categoria="auth", acao="auth.negado", nivel="warning", resultado="falha",
            usuario_id=usuario.id,
            detalhe={"motivo": "desativado", "status": 403},
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu acesso foi desativado.")
    # Sucesso: fixa o "quem" no contexto (eventos do endpoint) e em request.state (o
    # middleware, num contexto-pai, lê de lá para o evento http).
    request.state.usuario_id = usuario.id
    contexto.completar(usuario_id=usuario.id)
    return usuario


def papel_na_org(
    sessao: Session, usuario: Usuario, organizacao_id: uuid.UUID
) -> str | None:
    """O papel do usuário naquela organização, ou None se ele não é membro."""
    return sessao.scalars(
        select(Membro.papel).where(
            Membro.usuario_id == usuario.id,
            Membro.organizacao_id == organizacao_id,
        )
    ).first()


def exigir_papel(
    sessao: Session, usuario: Usuario, organizacao_id: uuid.UUID, minimo: str
) -> str:
    """Garante que o usuário tem ao menos o papel `minimo` na organização.
    Levanta 404 se ele não é membro (não revela a existência do recurso a quem
    não é da organização); 403 se é membro, mas com papel insuficiente.
    Devolve o papel efetivo."""
    papel = papel_na_org(sessao, usuario, organizacao_id)
    if papel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso não encontrado")
    if ORDEM_PAPEL.get(papel, 0) < ORDEM_PAPEL[minimo]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"Esta ação exige o papel '{minimo}'."
        )
    return papel
