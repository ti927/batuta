"""Gestão de acesso (Etapa 2, Fase 6, Tarefa 6.7).

Membros, convites e (des)ativação de usuários. Quase tudo é ação de admin da
organização; ver a lista de membros é de qualquer membro. Aceitar um convite é o
único endpoint que NÃO exige cadastro prévio — é como um convidado entra.
Toda ação sensível é auditada.
"""

import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import auth
import supabase_admin
from auth import usuario_atual
from auth_supabase import TokenInvalido, validar_token
from esquemas import (
    AlterarPapel,
    ConviteCriado,
    ConviteCriar,
    ConviteLer,
    ConvitePendente,
    MembroLer,
    MeuAcesso,
    UsuarioLer,
)
from modelos import Convite, Membro, Organizacao, Usuario
from rotas._comum import organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["membros"])

VALIDADE_CONVITE = timedelta(days=7)


def _conta_admins(sessao: Session, organizacao_id: uuid.UUID) -> int:
    return len(
        sessao.scalars(
            select(Membro.id).where(
                Membro.organizacao_id == organizacao_id, Membro.papel == "admin"
            )
        ).all()
    )


def _membro(sessao: Session, organizacao_id: uuid.UUID, usuario_id: uuid.UUID) -> Membro:
    m = sessao.scalars(
        select(Membro).where(
            Membro.organizacao_id == organizacao_id, Membro.usuario_id == usuario_id
        )
    ).first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membro não encontrado")
    return m


# ───────────────────────────── Eu ────────────────────────────────


@rotas.get("/eu", response_model=MeuAcesso)
def eu(
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Quem sou eu e quais meus papéis por organização (a interface usa para
    decidir o que mostrar)."""
    papeis = {
        org_id: papel
        for org_id, papel in sessao.execute(
            select(Membro.organizacao_id, Membro.papel).where(
                Membro.usuario_id == usuario.id
            )
        ).all()
    }
    return MeuAcesso(
        id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        ativo=usuario.ativo,
        papeis=papeis,
    )


# ───────────────────────────── Membros ───────────────────────────


@rotas.get("/organizacoes/{organizacao_id}/membros", response_model=list[MembroLer])
def listar_membros(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id)  # qualquer membro vê
    linhas = sessao.execute(
        select(Membro.usuario_id, Membro.papel, Usuario.nome, Usuario.email, Usuario.ativo)
        .join(Usuario, Usuario.id == Membro.usuario_id)
        .where(Membro.organizacao_id == organizacao_id)
        .order_by(Usuario.nome)
    ).all()
    return [
        MembroLer(usuario_id=uid, papel=papel, nome=nome, email=email, ativo=ativo)
        for uid, papel, nome, email, ativo in linhas
    ]


@rotas.post(
    "/organizacoes/{organizacao_id}/membros/{usuario_id}/papel",
    response_model=MembroLer,
)
def alterar_papel(
    organizacao_id: uuid.UUID,
    usuario_id: uuid.UUID,
    dados: AlterarPapel,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    m = _membro(sessao, organizacao_id, usuario_id)
    # Não deixar a organização sem nenhum admin.
    if m.papel == "admin" and dados.papel != "admin" and _conta_admins(sessao, organizacao_id) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A organização precisa de ao menos um admin."
        )
    anterior = m.papel
    m.papel = dados.papel
    auditoria.registrar(
        sessao, usuario=usuario, acao="papel.alterado", recurso_tipo="membro",
        recurso_id=usuario_id, organizacao_id=organizacao_id,
        detalhe={"de": anterior, "para": dados.papel},
    )
    sessao.commit()
    alvo = sessao.get(Usuario, usuario_id)
    return MembroLer(
        usuario_id=usuario_id, papel=m.papel, nome=alvo.nome, email=alvo.email, ativo=alvo.ativo
    )


@rotas.delete(
    "/organizacoes/{organizacao_id}/membros/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_membro(
    organizacao_id: uuid.UUID,
    usuario_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    m = _membro(sessao, organizacao_id, usuario_id)
    if m.papel == "admin" and _conta_admins(sessao, organizacao_id) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A organização precisa de ao menos um admin."
        )
    auditoria.registrar(
        sessao, usuario=usuario, acao="membro.removido", recurso_tipo="membro",
        recurso_id=usuario_id, organizacao_id=organizacao_id,
    )
    sessao.delete(m)
    sessao.commit()


# ───────────────────────────── Convites ──────────────────────────


@rotas.get("/organizacoes/{organizacao_id}/convites", response_model=list[ConviteLer])
def listar_convites(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    return sessao.scalars(
        select(Convite)
        .where(Convite.organizacao_id == organizacao_id)
        .order_by(Convite.criado_em.desc())
    ).all()


@rotas.post(
    "/organizacoes/{organizacao_id}/convites",
    response_model=ConviteCriado,
    status_code=status.HTTP_201_CREATED,
)
def criar_convite(
    organizacao_id: uuid.UUID,
    dados: ConviteCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    # Dispara o convite no Supabase (cria a conta e envia o email). Se o email já
    # tem conta, o Supabase responde 422 e NÃO reenvia — nesse caso o convite vale
    # mesmo assim, mas a pessoa só fica sabendo pelo aviso dentro do Batuta (banner
    # na home), pois nenhum e-mail saiu. `email_enviado` informa isso ao admin.
    email_enviado = True
    try:
        supabase_admin.convidar(dados.email)
    except httpx.HTTPStatusError as e:
        # 422 "email address already registered" não é impeditivo: seguimos só
        # registrando o Convite (a pessoa loga e aceita). Outros erros propagam.
        if e.response.status_code not in (422,):
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"Falha ao enviar o convite pelo Supabase: {e.response.text[:200]}",
            )
        email_enviado = False
    except httpx.HTTPError as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Falha ao contatar o Supabase: {e}"
        )

    convite = Convite(
        email=dados.email,
        organizacao_id=organizacao_id,
        papel=dados.papel,
        status="pendente",
        convidado_por_id=usuario.id,
        expira_em=datetime.now(timezone.utc) + VALIDADE_CONVITE,
    )
    sessao.add(convite)
    sessao.flush()
    auditoria.registrar(
        sessao, usuario=usuario, acao="convite.criado", recurso_tipo="convite",
        recurso_id=convite.id, organizacao_id=organizacao_id,
        detalhe={"email": dados.email, "papel": dados.papel, "email_enviado": email_enviado},
    )
    sessao.commit()
    sessao.refresh(convite)
    return ConviteCriado(
        id=convite.id,
        email=convite.email,
        organizacao_id=convite.organizacao_id,
        papel=convite.papel,
        status=convite.status,
        expira_em=convite.expira_em,
        criado_em=convite.criado_em,
        email_enviado=email_enviado,
    )


@rotas.delete("/convites/{convite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revogar_convite(
    convite_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    convite = sessao.get(Convite, convite_id)
    if convite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Convite não encontrado")
    organizacao_acessivel(sessao, usuario, convite.organizacao_id, minimo="admin")
    convite.status = "revogado"
    auditoria.registrar(
        sessao, usuario=usuario, acao="convite.revogado", recurso_tipo="convite",
        recurso_id=convite.id, organizacao_id=convite.organizacao_id,
    )
    sessao.commit()


@rotas.post("/convites/aceitar", response_model=list[ConviteLer])
def aceitar_convites(
    request: Request,
    sessao: Session = Depends(obter_sessao),
):
    """Aceite de convite — único endpoint que NÃO exige cadastro prévio: o
    convidado já tem um token válido do Supabase (definiu a senha pelo email),
    mas ainda não tem `Usuario`/`Membro`. Aqui criamos ambos a partir dos
    convites pendentes para o email do token."""
    token = auth._token_do_cabecalho(request)
    try:
        claims = validar_token(token)
    except TokenInvalido as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {e}")

    sub = claims.get("sub")
    email = (claims.get("email") or "").strip()
    if not sub or not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token sem sub/email.")

    agora = datetime.now(timezone.utc)
    pendentes = sessao.scalars(
        select(Convite).where(Convite.email == email, Convite.status == "pendente")
    ).all()
    validos = [c for c in pendentes if c.expira_em is None or c.expira_em > agora]
    if not validos:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Nenhum convite pendente para este email."
        )

    # Usuário: acha por auth_id ou por email; senão cria. Liga o auth_id e ativa.
    usuario = sessao.scalars(
        select(Usuario).where(Usuario.auth_id == uuid.UUID(sub))
    ).first()
    if usuario is None:
        usuario = sessao.scalars(select(Usuario).where(Usuario.email == email)).first()
    if usuario is None:
        usuario = Usuario(nome=email.split("@")[0], email=email)
        sessao.add(usuario)
    usuario.auth_id = uuid.UUID(sub)
    usuario.ativo = True
    sessao.flush()

    for c in validos:
        ja = sessao.scalars(
            select(Membro).where(
                Membro.usuario_id == usuario.id,
                Membro.organizacao_id == c.organizacao_id,
            )
        ).first()
        if ja is None:
            sessao.add(
                Membro(
                    usuario_id=usuario.id, organizacao_id=c.organizacao_id, papel=c.papel
                )
            )
        c.status = "aceito"
        auditoria.registrar(
            sessao, usuario=usuario, acao="convite.aceito", recurso_tipo="convite",
            recurso_id=c.id, organizacao_id=c.organizacao_id,
        )
    sessao.commit()
    for c in validos:
        sessao.refresh(c)
    return validos


@rotas.get("/convites/pendentes", response_model=list[ConvitePendente])
def convites_pendentes(
    request: Request,
    sessao: Session = Depends(obter_sessao),
):
    """Convites pendentes endereçados ao usuário logado — alimenta o banner de
    aviso na home. Autentica pelo token DIRETO (não `usuario_atual`): o convidado
    pode já ter conta no Supabase mas ainda não ter `Usuario`/`auth_id` ligado, e
    nesse caso `usuario_atual` daria 403 e o banner nunca apareceria."""
    token = auth._token_do_cabecalho(request)
    try:
        claims = validar_token(token)
    except TokenInvalido as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {e}")
    email = (claims.get("email") or "").strip()
    if not email:
        return []  # token sem email → nada a mostrar (não é erro)

    agora = datetime.now(timezone.utc)
    linhas = sessao.execute(
        select(
            Convite.id,
            Convite.organizacao_id,
            Organizacao.nome,
            Convite.papel,
            Convite.expira_em,
        )
        .join(Organizacao, Organizacao.id == Convite.organizacao_id)
        .where(Convite.email == email, Convite.status == "pendente")
        .order_by(Convite.criado_em.desc())
    ).all()
    return [
        ConvitePendente(
            id=cid, organizacao_id=oid, organizacao_nome=nome, papel=papel, expira_em=exp
        )
        for cid, oid, nome, papel, exp in linhas
        if exp is None or exp > agora
    ]


# ──────────────────────── (Des)ativação de usuário ───────────────


def _admin_compartilha_org(sessao: Session, admin: Usuario, alvo_id: uuid.UUID) -> bool:
    """O `admin` é admin de alguma organização da qual o `alvo` também é membro?"""
    orgs_admin = select(Membro.organizacao_id).where(
        Membro.usuario_id == admin.id, Membro.papel == "admin"
    )
    return (
        sessao.scalars(
            select(Membro.id).where(
                Membro.usuario_id == alvo_id,
                Membro.organizacao_id.in_(orgs_admin),
            )
        ).first()
        is not None
    )


def _definir_ativo(
    sessao: Session, admin: Usuario, alvo_id: uuid.UUID, ativo: bool
) -> Usuario:
    alvo = sessao.get(Usuario, alvo_id)
    if alvo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    if not _admin_compartilha_org(sessao, admin, alvo_id):
        # Não revela a existência de um usuário fora do alcance do admin.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    alvo.ativo = ativo
    auditoria.registrar(
        sessao, usuario=admin,
        acao="usuario.reativado" if ativo else "usuario.desativado",
        recurso_tipo="usuario", recurso_id=alvo_id,
    )
    sessao.commit()
    sessao.refresh(alvo)
    return alvo


@rotas.post("/usuarios/{usuario_id}/desativar", response_model=UsuarioLer)
def desativar(
    usuario_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    if usuario_id == usuario.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Você não pode desativar a si mesmo.")
    return _definir_ativo(sessao, usuario, usuario_id, False)


@rotas.post("/usuarios/{usuario_id}/reativar", response_model=UsuarioLer)
def reativar(
    usuario_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return _definir_ativo(sessao, usuario, usuario_id, True)
