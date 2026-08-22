"""Endpoints da caixa-forte de credenciais nomeadas (FASE Caixa-forte, Passo 5).

Substitui o antigo "inventário de credenciais por-instrumento". Aqui o usuário
cria CREDENCIAIS NOMEADAS (ex.: "WordPress Blog" = usuario+senha_app) que os
instrumentos referenciam (`instrumentos.credencial_id`) em vez de guardar o
segredo inline — trocar num lugar só vale para todos os instrumentos que a usam.

Dois níveis (ver docs/CAIXA-FORTE-PLANO.md):
- **da organização** (`organizacao_id` preenchido): geridas pelos operadores+ da org;
- **da consultoria** (`organizacao_id` nulo): geridas só por admin da consultoria;
  ficam disponíveis às organizações apenas quando `compartilhavel`.

Os valores secretos são cifrados (`credenciais_cofre`) e NUNCA reexibidos: a
leitura traz só o `resumo` mascarado e o `usado_por`."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

import auditoria
import certificados
import credenciais_cofre as cofre_cred
import tipos_credencial as tc
from auth import usuario_atual
from consultoria import exigir_admin_consultoria
from instrumentos.base import FalhaInstrumento
from esquemas import (
    CampoCredencialLer,
    CredencialCriar,
    CredencialEditar,
    CredencialLer,
    TipoCredencialLer,
)
from modelos import Credencial, Usuario
from rotas._comum import organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["credenciais"])


def _ler(sessao: Session, cred: Credencial) -> Credencial:
    """Anexa o `usado_por` (atributo transitório) para o `CredencialLer` devolver."""
    cred.usado_por = cofre_cred.usado_por(sessao, cred.id)
    return cred


def _exigir_tipo_valido(tipo: str) -> None:
    if tc.obter_tipo(tipo) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Tipo de credencial desconhecido: {tipo!r}.",
        )


def _exigir_nome_livre(
    sessao: Session,
    organizacao_id: uuid.UUID | None,
    nome: str,
    exceto: uuid.UUID | None = None,
) -> None:
    cond = (
        Credencial.organizacao_id.is_(None)
        if organizacao_id is None
        else Credencial.organizacao_id == organizacao_id
    )
    consulta = select(Credencial.id).where(cond, Credencial.nome == nome)
    if exceto is not None:
        consulta = consulta.where(Credencial.id != exceto)
    if sessao.scalar(consulta) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Já existe uma credencial chamada '{nome}'."
        )


def _gravar(cred: Credencial, dados: dict) -> None:
    """Grava o saco da credencial. Casos especiais:
    - `instagram`: valida o token na Meta (descobre o `ig_user_id` e fixa a
      validade); um token recusado vira 422 claro;
    - `certificado_mtls`: normaliza o arquivo do certificado (.pfx/.pem) para PEM,
      cifra e deriva titular/validade; arquivo/senha inválidos viram 422 claro.
    Para os demais tipos, é o gravar normal."""
    try:
        if cred.tipo == "certificado_mtls":
            cofre_cred.gravar_com_certificado(cred, dados)
        else:
            cofre_cred.gravar_com_validacao_ig(cred, dados)
    except certificados.CertificadoInvalido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    except FalhaInstrumento as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"O Instagram não aceitou o token: {e}. Gere um token novo no painel da "
            "Meta (Instagram → API setup → Gerar token) e cole aqui.",
        )


def _bloquear_se_em_uso(sessao: Session, cred: Credencial) -> None:
    n = cofre_cred.usado_por(sessao, cred.id)
    if n > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Credencial em uso por {n} instrumento(s). Troque-os antes de apagá-la.",
        )


# ─────────────────────────── Catálogo de tipos ──────────────────────────
# Declarado antes de qualquer /credenciais/{id} para "tipos" não virar UUID.


@rotas.get("/credenciais/tipos", response_model=list[TipoCredencialLer])
def listar_tipos(usuario: Usuario = Depends(usuario_atual)):
    """Os tipos de credencial e seus campos — a interface monta o formulário."""
    return [
        TipoCredencialLer(
            tipo=t.tipo,
            nome_exibicao=t.nome_exibicao,
            campos=[
                CampoCredencialLer(nome=c.nome, rotulo=c.rotulo, secreto=c.secreto)
                for c in t.campos
            ],
        )
        for t in tc.tipos_disponiveis()
    ]


# ─────────────────────── Credenciais da organização ─────────────────────


@rotas.get(
    "/organizacoes/{organizacao_id}/credenciais",
    response_model=list[CredencialLer],
)
def listar_org(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """As credenciais da organização MAIS as da consultoria marcadas como
    compartilháveis (estas o instrumento pode escolher). Operador+."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="operador")
    linhas = sessao.scalars(
        select(Credencial)
        .where(
            or_(
                Credencial.organizacao_id == organizacao_id,
                and_(
                    Credencial.organizacao_id.is_(None),
                    Credencial.compartilhavel.is_(True),
                ),
            )
        )
        .order_by(Credencial.nome)
    ).all()
    return [_ler(sessao, c) for c in linhas]


@rotas.post(
    "/organizacoes/{organizacao_id}/credenciais",
    response_model=CredencialLer,
    status_code=status.HTTP_201_CREATED,
)
def criar_org(
    organizacao_id: uuid.UUID,
    dados: CredencialCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Cria uma credencial nomeada da organização (operador+)."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="operador")
    _exigir_tipo_valido(dados.tipo)
    _exigir_nome_livre(sessao, organizacao_id, dados.nome)
    # `compartilhavel` é irrelevante numa credencial da organização: fica False.
    cred = Credencial(
        organizacao_id=organizacao_id, nome=dados.nome, tipo=dados.tipo,
        compartilhavel=False,
    )
    _gravar(cred, dados.dados)
    sessao.add(cred)
    sessao.flush()
    auditoria.registrar(
        sessao, usuario=usuario, acao="credencial.criada",
        recurso_tipo="credencial", recurso_id=cred.id, organizacao_id=organizacao_id,
        detalhe={"tipo": cred.tipo, "nome": cred.nome},
    )
    sessao.commit()
    sessao.refresh(cred)
    return _ler(sessao, cred)


def _credencial_da_org(
    sessao: Session, usuario: Usuario, credencial_id: uuid.UUID, minimo: str
) -> Credencial:
    """Uma credencial DA ORGANIZAÇÃO acessível ao usuário (as da consultoria são
    geridas só pelos endpoints /credenciais-consultoria)."""
    cred = sessao.get(Credencial, credencial_id)
    if cred is None or cred.organizacao_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credencial não encontrada.")
    organizacao_acessivel(sessao, usuario, cred.organizacao_id, minimo=minimo)
    return cred


@rotas.put("/credenciais/{credencial_id}", response_model=CredencialLer)
def editar_org(
    credencial_id: uuid.UUID,
    dados: CredencialEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Edita/rotaciona uma credencial da organização (operador+). Campo secreto em
    branco preserva o atual."""
    cred = _credencial_da_org(sessao, usuario, credencial_id, minimo="operador")
    if dados.nome != cred.nome:
        _exigir_nome_livre(sessao, cred.organizacao_id, dados.nome, exceto=cred.id)
    cred.nome = dados.nome
    _gravar(cred, dados.dados)  # `compartilhavel` não vale p/ org
    auditoria.registrar(
        sessao, usuario=usuario, acao="credencial.editada",
        recurso_tipo="credencial", recurso_id=cred.id,
        organizacao_id=cred.organizacao_id, detalhe={"nome": cred.nome},
    )
    sessao.commit()
    sessao.refresh(cred)
    return _ler(sessao, cred)


@rotas.delete(
    "/credenciais/{credencial_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remover_org(
    credencial_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Apaga uma credencial da organização (operador+). Bloqueada se estiver em uso."""
    cred = _credencial_da_org(sessao, usuario, credencial_id, minimo="operador")
    _bloquear_se_em_uso(sessao, cred)
    auditoria.registrar(
        sessao, usuario=usuario, acao="credencial.removida",
        recurso_tipo="credencial", recurso_id=cred.id,
        organizacao_id=cred.organizacao_id, detalhe={"nome": cred.nome},
    )
    sessao.delete(cred)
    sessao.commit()


# ─────────────────────── Credenciais da consultoria ─────────────────────


@rotas.get("/credenciais-consultoria", response_model=list[CredencialLer])
def listar_consultoria(
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """As credenciais da consultoria (compartilháveis ou não). Só admin da consultoria."""
    exigir_admin_consultoria(usuario)
    linhas = sessao.scalars(
        select(Credencial)
        .where(Credencial.organizacao_id.is_(None))
        .order_by(Credencial.nome)
    ).all()
    return [_ler(sessao, c) for c in linhas]


@rotas.post(
    "/credenciais-consultoria",
    response_model=CredencialLer,
    status_code=status.HTTP_201_CREATED,
)
def criar_consultoria(
    dados: CredencialCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Cria uma credencial da consultoria (só admin da consultoria). O toggle
    `compartilhavel` decide se as organizações podem escolhê-la."""
    exigir_admin_consultoria(usuario)
    _exigir_tipo_valido(dados.tipo)
    _exigir_nome_livre(sessao, None, dados.nome)
    cred = Credencial(
        organizacao_id=None, nome=dados.nome, tipo=dados.tipo,
        compartilhavel=dados.compartilhavel,
    )
    _gravar(cred, dados.dados)
    sessao.add(cred)
    sessao.flush()
    auditoria.registrar(
        sessao, usuario=usuario, acao="credencial_consultoria.criada",
        recurso_tipo="credencial", recurso_id=cred.id, organizacao_id=None,
        detalhe={"tipo": cred.tipo, "nome": cred.nome, "compartilhavel": cred.compartilhavel},
    )
    sessao.commit()
    sessao.refresh(cred)
    return _ler(sessao, cred)


def _credencial_consultoria(sessao: Session, credencial_id: uuid.UUID) -> Credencial:
    cred = sessao.get(Credencial, credencial_id)
    if cred is None or cred.organizacao_id is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credencial não encontrada.")
    return cred


@rotas.put("/credenciais-consultoria/{credencial_id}", response_model=CredencialLer)
def editar_consultoria(
    credencial_id: uuid.UUID,
    dados: CredencialEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Edita/rotaciona uma credencial da consultoria e seu toggle (admin consultoria)."""
    exigir_admin_consultoria(usuario)
    cred = _credencial_consultoria(sessao, credencial_id)
    if dados.nome != cred.nome:
        _exigir_nome_livre(sessao, None, dados.nome, exceto=cred.id)
    cred.nome = dados.nome
    cred.compartilhavel = dados.compartilhavel
    _gravar(cred, dados.dados)
    auditoria.registrar(
        sessao, usuario=usuario, acao="credencial_consultoria.editada",
        recurso_tipo="credencial", recurso_id=cred.id, organizacao_id=None,
        detalhe={"nome": cred.nome, "compartilhavel": cred.compartilhavel},
    )
    sessao.commit()
    sessao.refresh(cred)
    return _ler(sessao, cred)


@rotas.delete(
    "/credenciais-consultoria/{credencial_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_consultoria(
    credencial_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Apaga uma credencial da consultoria (admin consultoria). Bloqueada se em uso."""
    exigir_admin_consultoria(usuario)
    cred = _credencial_consultoria(sessao, credencial_id)
    _bloquear_se_em_uso(sessao, cred)
    auditoria.registrar(
        sessao, usuario=usuario, acao="credencial_consultoria.removida",
        recurso_tipo="credencial", recurso_id=cred.id, organizacao_id=None,
        detalhe={"nome": cred.nome},
    )
    sessao.delete(cred)
    sessao.commit()
