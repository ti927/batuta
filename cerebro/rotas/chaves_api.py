"""Endpoints do cofre de chaves de API (Fase 7.4, PRODUTO §26, MIGRACAO Virada 5).

Duas frentes:
- **Chaves da organização** (o cliente): geridas pelo ADMIN da própria org.
- **Chave-mãe da consultoria** (`organizacao_id` nulo, o fallback): gerida só
  pelos ADMINS DA CONSULTORIA (lista de e-mails no `.env`; ver `consultoria.py`).

O valor da chave é cifrado ao salvar (`cofre.py`) e NUNCA é reexibido: a leitura
mostra só os últimos 4 dígitos. `PUT` faz upsert — cadastra a primeira vez,
substitui (troca de chave) nas seguintes, respeitando o índice único
(organização, tipo de IA, provedor). Toda troca/remoção é auditada (MIGRACAO §6.4).

Nesta fase só o provedor Anthropic é suportado (MIGRACAO: o campo `provedor` já
existe para o futuro, mas o motor só consome Anthropic) — cadastrar outro seria
chave morta, então é recusado com 422.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import cofre
from auth import usuario_atual
from consultoria import exigir_admin_consultoria
from esquemas import ChaveApiCriar, ChaveApiLer
from modelos import ChaveApi, Usuario
from rotas._comum import organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["chaves"])

PROVEDORES_SUPORTADOS = {"anthropic"}


def _validar_provedor(provedor: str) -> None:
    if provedor not in PROVEDORES_SUPORTADOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Provedor '{provedor}' ainda não é suportado. Disponível nesta fase: "
            f"{', '.join(sorted(PROVEDORES_SUPORTADOS))}.",
        )


def _buscar(
    sessao: Session, organizacao_id: uuid.UUID | None, tipo_ia: str, provedor: str
) -> ChaveApi | None:
    """A chave de (organização, tipo, provedor) — a única que o índice permite."""
    condicao_org = (
        ChaveApi.organizacao_id.is_(None)
        if organizacao_id is None
        else ChaveApi.organizacao_id == organizacao_id
    )
    return sessao.scalars(
        select(ChaveApi).where(
            condicao_org,
            ChaveApi.tipo_ia == tipo_ia,
            ChaveApi.provedor == provedor,
        )
    ).first()


def _upsert(
    sessao: Session, organizacao_id: uuid.UUID | None, dados: ChaveApiCriar
) -> tuple[ChaveApi, bool]:
    """Cadastra a chave, ou substitui o valor se já existe uma para aquele
    (organização, tipo, provedor). Devolve (chave, era_nova)."""
    existente = _buscar(sessao, organizacao_id, dados.tipo_ia, dados.provedor)
    nova = existente is None
    chave = existente or ChaveApi(
        organizacao_id=organizacao_id, tipo_ia=dados.tipo_ia, provedor=dados.provedor
    )
    chave.valor_cifrado = cofre.cifrar(dados.valor)
    chave.ultimos4 = cofre.ultimos4(dados.valor)
    chave.apelido = dados.apelido
    chave.ativa = True
    if nova:
        sessao.add(chave)
    sessao.flush()
    return chave, nova


# ─────────────────────────── Chaves da organização ──────────────────────────


@rotas.get(
    "/organizacoes/{organizacao_id}/chaves", response_model=list[ChaveApiLer]
)
def listar_chaves_org(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Lista (mascaradas) as chaves da organização. Gerir chave é ação de admin."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    return sessao.scalars(
        select(ChaveApi)
        .where(ChaveApi.organizacao_id == organizacao_id)
        .order_by(ChaveApi.tipo_ia, ChaveApi.provedor)
    ).all()


@rotas.put(
    "/organizacoes/{organizacao_id}/chaves", response_model=ChaveApiLer
)
def salvar_chave_org(
    organizacao_id: uuid.UUID,
    dados: ChaveApiCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Cadastra ou troca a chave de IA da organização (só admin)."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    _validar_provedor(dados.provedor)
    chave, nova = _upsert(sessao, organizacao_id, dados)
    auditoria.registrar(
        sessao, usuario=usuario,
        acao="chave.cadastrada" if nova else "chave.trocada",
        recurso_tipo="chave_api", recurso_id=chave.id, organizacao_id=organizacao_id,
        detalhe={"tipo_ia": chave.tipo_ia, "provedor": chave.provedor, "ultimos4": chave.ultimos4},
    )
    sessao.commit()
    sessao.refresh(chave)
    return chave


@rotas.delete(
    "/organizacoes/{organizacao_id}/chaves/{chave_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_chave_org(
    organizacao_id: uuid.UUID,
    chave_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Remove uma chave da organização (só admin)."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    chave = sessao.get(ChaveApi, chave_id)
    if chave is None or chave.organizacao_id != organizacao_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chave não encontrada")
    auditoria.registrar(
        sessao, usuario=usuario, acao="chave.removida",
        recurso_tipo="chave_api", recurso_id=chave.id, organizacao_id=organizacao_id,
        detalhe={"tipo_ia": chave.tipo_ia, "provedor": chave.provedor},
    )
    sessao.delete(chave)
    sessao.commit()


# ──────────────────────── Chave-mãe da consultoria ──────────────────────────


@rotas.get("/chaves-consultoria", response_model=list[ChaveApiLer])
def listar_chaves_consultoria(
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Lista (mascaradas) as chaves-mãe da consultoria. Só admin da consultoria."""
    exigir_admin_consultoria(usuario)
    return sessao.scalars(
        select(ChaveApi)
        .where(ChaveApi.organizacao_id.is_(None))
        .order_by(ChaveApi.tipo_ia, ChaveApi.provedor)
    ).all()


@rotas.put("/chaves-consultoria", response_model=ChaveApiLer)
def salvar_chave_consultoria(
    dados: ChaveApiCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Cadastra ou troca a chave-mãe da consultoria (só admin da consultoria)."""
    exigir_admin_consultoria(usuario)
    _validar_provedor(dados.provedor)
    chave, nova = _upsert(sessao, None, dados)
    auditoria.registrar(
        sessao, usuario=usuario,
        acao="chave_mae.cadastrada" if nova else "chave_mae.trocada",
        recurso_tipo="chave_api", recurso_id=chave.id, organizacao_id=None,
        detalhe={"tipo_ia": chave.tipo_ia, "provedor": chave.provedor, "ultimos4": chave.ultimos4},
    )
    sessao.commit()
    sessao.refresh(chave)
    return chave


@rotas.delete(
    "/chaves-consultoria/{chave_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remover_chave_consultoria(
    chave_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Remove uma chave-mãe da consultoria (só admin da consultoria)."""
    exigir_admin_consultoria(usuario)
    chave = sessao.get(ChaveApi, chave_id)
    if chave is None or chave.organizacao_id is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chave não encontrada")
    auditoria.registrar(
        sessao, usuario=usuario, acao="chave_mae.removida",
        recurso_tipo="chave_api", recurso_id=chave.id, organizacao_id=None,
        detalhe={"tipo_ia": chave.tipo_ia, "provedor": chave.provedor},
    )
    sessao.delete(chave)
    sessao.commit()
