"""Inventário unificado de credenciais de instrumento (tela "Chaves e credenciais").

As chaves de IA (provedores) vivem em `chaves_api.py` (pool da organização). Aqui
fica o OUTRO lado: as credenciais POR-INSTÂNCIA dos instrumentos (senha do
WordPress, token do bot Telegram, senha do banco SQL, etc.). Esta rota agrega
todas as credenciais dos instrumentos da organização num só lugar — para ver onde
cada uma está e ROTACIONÁ-LA sem caçar o formulário de cada instrumento.

Os valores nunca são reexibidos: a leitura mostra só os 4 últimos dígitos
(`segredos_instrumento.resumo`). A rotação reusa `salvar_segredos` (cofre 7-B).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import instrumentos as encaixe
import segredos_instrumento as segredos
from auth import usuario_atual
from esquemas import CredencialCampo, CredencialInstrumento, RotacionarSegredos
from modelos import Instrumento, Time, Usuario
from rotas._comum import instrumento_acessivel, organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["credenciais"])


@rotas.get(
    "/organizacoes/{organizacao_id}/credenciais",
    response_model=list[CredencialInstrumento],
)
def inventario(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Todas as credenciais de instrumento da organização, mascaradas, com o time
    de cada uma. Só admin da organização (é uma visão de segurança)."""
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    linhas = sessao.execute(
        select(Instrumento, Time.nome)
        .join(Time, Time.id == Instrumento.time_id)
        .where(Time.organizacao_id == organizacao_id)
        .order_by(Time.nome, Instrumento.nome)
    ).all()

    inventario: list[CredencialInstrumento] = []
    for inst, time_nome in linhas:
        tipo = encaixe.obter_tipo(inst.tipo)
        if tipo is None or not tipo.campos_secretos:
            continue  # instrumento sem segredo não entra no inventário
        resumo = segredos.resumo(sessao, inst.id)
        compart = getattr(tipo, "chave_compartilhada", None)
        campo_compart = compart[0] if compart else None
        campos = [
            CredencialCampo(
                campo=campo,
                definido=campo in resumo,
                ultimos4=resumo.get(campo),
                compartilhada=(campo == campo_compart),
                servico=(compart[1] if campo == campo_compart else None),
            )
            for campo in tipo.campos_secretos
        ]
        inventario.append(
            CredencialInstrumento(
                instrumento_id=inst.id,
                instrumento_nome=inst.nome,
                time_id=inst.time_id,
                time_nome=time_nome,
                tipo=inst.tipo,
                tipo_nome=tipo.nome_exibicao,
                campos=campos,
            )
        )
    return inventario


@rotas.put("/instrumentos/{instrumento_id}/segredos", response_model=dict)
def rotacionar(
    instrumento_id: uuid.UUID,
    dados: RotacionarSegredos,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Rotaciona (troca) um ou mais segredos de um instrumento, sem mexer no resto
    da config. Operador+. Devolve o resumo mascarado atualizado."""
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="operador")
    # Aceita só os campos secretos declarados pelo tipo; ignora vazios/desconhecidos.
    tipo = encaixe.obter_tipo(inst.tipo)
    if tipo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tipo desconhecido.")
    validos = {
        campo: valor
        for campo, valor in (dados.segredos or {}).items()
        if campo in tipo.campos_secretos and str(valor).strip()
    }
    alterados = segredos.salvar_segredos(sessao, inst.id, validos)
    if alterados:
        auditoria.registrar(
            sessao, usuario=usuario, acao="instrumento.segredo_alterado",
            recurso_tipo="instrumento", recurso_id=inst.id,
            organizacao_id=auditoria.org_do_time(sessao, inst.time_id),
            detalhe={"segredos": alterados},
        )
    sessao.commit()
    return segredos.resumo(sessao, inst.id)
