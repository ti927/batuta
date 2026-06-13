"""Endpoints dos canais de mensageria (PRODUTO §10).

Um canal pende da ORGANIZAÇÃO e é gerido pelo ADMIN (carrega o segredo do token,
no cofre). As IDENTIDADES (quem fala, pelo identificador do canal) são gestão
operacional (operador+). Observador vê. O envio/recebimento entra nos próximos
passos — aqui é só cadastro e gestão.

O token (e futuros segredos) é cifrado no cofre (`segredos_canal`), separado da
`canais.config` (JSONB em claro), e NUNCA reexibido: a leitura mostra só os 4
últimos dígitos.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import canais as encaixe
import segredos_canal
from auth import usuario_atual
from esquemas import (
    CanalCriar,
    CanalEditar,
    CanalLer,
    IdentidadeCanalCriar,
    IdentidadeCanalEditar,
    IdentidadeCanalLer,
)
from modelos import Canal, IdentidadeCanal, Usuario
from rotas._comum import organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["canais"])


def _validar_tipo(tipo: str) -> None:
    if encaixe.obter_tipo(tipo) is None:
        disponiveis = ", ".join(sorted(t.tipo for t in encaixe.tipos_disponiveis()))
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Tipo de canal '{tipo}' não é suportado. Disponível: {disponiveis}.",
        )


def _com_segredos(sessao: Session, canal: Canal) -> Canal:
    """Anexa o resumo dos segredos (campo → ultimos4) ao canal, para a CanalLer.
    Atributo transitório (o SQLAlchemy não o persiste)."""
    canal.segredos = segredos_canal.resumo(sessao, canal.id)
    return canal


def _canal_da_org(
    sessao: Session, organizacao_id: uuid.UUID, canal_id: uuid.UUID
) -> Canal:
    canal = sessao.get(Canal, canal_id)
    if canal is None or canal.organizacao_id != organizacao_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Canal não encontrado")
    return canal


# ─────────────────────────────── Canais ──────────────────────────────────────


@rotas.get("/organizacoes/{organizacao_id}/canais", response_model=list[CanalLer])
def listar_canais(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Lista os canais da organização (observador+). Segredo nunca reexibido."""
    organizacao_acessivel(sessao, usuario, organizacao_id)
    canais = sessao.scalars(
        select(Canal)
        .where(Canal.organizacao_id == organizacao_id)
        .order_by(Canal.criado_em)
    ).all()
    return [_com_segredos(sessao, c) for c in canais]


@rotas.post(
    "/organizacoes/{organizacao_id}/canais",
    response_model=CanalLer,
    status_code=status.HTTP_201_CREATED,
)
def criar_canal(
    organizacao_id: uuid.UUID,
    dados: CanalCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Cadastra um canal (só admin). O segredo (token) vai pro cofre."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    _validar_tipo(dados.tipo)
    try:
        config_publica, segredos = encaixe.preparar_config(dados.tipo, dados.config)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    canal = Canal(
        organizacao_id=organizacao_id,
        tipo=dados.tipo,
        nome=dados.nome,
        config=config_publica,
        ativo=True,
    )
    sessao.add(canal)
    sessao.flush()
    segredos_canal.salvar_segredos(sessao, canal.id, segredos)
    auditoria.registrar(
        sessao, usuario=usuario, acao="canal.criado",
        recurso_tipo="canal", recurso_id=canal.id, organizacao_id=organizacao_id,
        detalhe={"tipo": canal.tipo, "nome": canal.nome},
    )
    sessao.commit()
    sessao.refresh(canal)
    return _com_segredos(sessao, canal)


@rotas.put(
    "/organizacoes/{organizacao_id}/canais/{canal_id}", response_model=CanalLer
)
def editar_canal(
    organizacao_id: uuid.UUID,
    canal_id: uuid.UUID,
    dados: CanalEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Edita um canal (só admin). Campo secreto em branco preserva o atual."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    canal = _canal_da_org(sessao, organizacao_id, canal_id)
    try:
        config_publica, segredos = encaixe.preparar_config(canal.tipo, dados.config)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    canal.nome = dados.nome
    canal.config = config_publica
    canal.ativo = dados.ativo
    segredos_canal.salvar_segredos(sessao, canal.id, segredos)
    auditoria.registrar(
        sessao, usuario=usuario, acao="canal.editado",
        recurso_tipo="canal", recurso_id=canal.id, organizacao_id=organizacao_id,
        detalhe={"nome": canal.nome, "ativo": canal.ativo},
    )
    sessao.commit()
    sessao.refresh(canal)
    return _com_segredos(sessao, canal)


@rotas.delete(
    "/organizacoes/{organizacao_id}/canais/{canal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_canal(
    organizacao_id: uuid.UUID,
    canal_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Remove um canal e tudo que pende dele (identidades, segredos, log) — só admin."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    canal = _canal_da_org(sessao, organizacao_id, canal_id)
    auditoria.registrar(
        sessao, usuario=usuario, acao="canal.removido",
        recurso_tipo="canal", recurso_id=canal.id, organizacao_id=organizacao_id,
        detalhe={"tipo": canal.tipo, "nome": canal.nome},
    )
    sessao.delete(canal)
    sessao.commit()


# ───────────────────────────── Identidades ───────────────────────────────────


@rotas.get(
    "/organizacoes/{organizacao_id}/canais/{canal_id}/identidades",
    response_model=list[IdentidadeCanalLer],
)
def listar_identidades(
    organizacao_id: uuid.UUID,
    canal_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Lista as identidades de um canal (observador+)."""
    organizacao_acessivel(sessao, usuario, organizacao_id)
    _canal_da_org(sessao, organizacao_id, canal_id)
    return sessao.scalars(
        select(IdentidadeCanal)
        .where(IdentidadeCanal.canal_id == canal_id)
        .order_by(IdentidadeCanal.criado_em)
    ).all()


@rotas.post(
    "/organizacoes/{organizacao_id}/canais/{canal_id}/identidades",
    response_model=IdentidadeCanalLer,
    status_code=status.HTTP_201_CREATED,
)
def criar_identidade(
    organizacao_id: uuid.UUID,
    canal_id: uuid.UUID,
    dados: IdentidadeCanalCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Vincula um identificador do canal a uma pessoa (operador+)."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="operador")
    _canal_da_org(sessao, organizacao_id, canal_id)
    ja_existe = sessao.scalars(
        select(IdentidadeCanal).where(
            IdentidadeCanal.canal_id == canal_id,
            IdentidadeCanal.identificador_externo == dados.identificador_externo,
        )
    ).first()
    if ja_existe is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Já existe uma identidade com esse identificador neste canal.",
        )
    identidade = IdentidadeCanal(
        organizacao_id=organizacao_id,
        canal_id=canal_id,
        identificador_externo=dados.identificador_externo,
        rotulo=dados.rotulo,
        usuario_id=dados.usuario_id,
    )
    sessao.add(identidade)
    sessao.commit()
    sessao.refresh(identidade)
    return identidade


@rotas.put(
    "/organizacoes/{organizacao_id}/canais/{canal_id}/identidades/{identidade_id}",
    response_model=IdentidadeCanalLer,
)
def editar_identidade(
    organizacao_id: uuid.UUID,
    canal_id: uuid.UUID,
    identidade_id: uuid.UUID,
    dados: IdentidadeCanalEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Edita rótulo / vínculo de usuário de uma identidade (operador+)."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="operador")
    _canal_da_org(sessao, organizacao_id, canal_id)
    identidade = sessao.get(IdentidadeCanal, identidade_id)
    if identidade is None or identidade.canal_id != canal_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Identidade não encontrada")
    identidade.rotulo = dados.rotulo
    identidade.usuario_id = dados.usuario_id
    sessao.commit()
    sessao.refresh(identidade)
    return identidade


@rotas.delete(
    "/organizacoes/{organizacao_id}/canais/{canal_id}/identidades/{identidade_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_identidade(
    organizacao_id: uuid.UUID,
    canal_id: uuid.UUID,
    identidade_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Remove uma identidade (operador+)."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="operador")
    _canal_da_org(sessao, organizacao_id, canal_id)
    identidade = sessao.get(IdentidadeCanal, identidade_id)
    if identidade is None or identidade.canal_id != canal_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Identidade não encontrada")
    sessao.delete(identidade)
    sessao.commit()
