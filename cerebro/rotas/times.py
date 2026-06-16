"""Endpoints CRUD de Times.

Acesso por papel (Fase 6): membro vê (observador); operador cria/edita; só admin
apaga ou cria um time novo na organização (MIGRACAO §3.7: criar projetos/times = admin).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import auditoria
import precos
from auth import usuario_atual
from esquemas import TimeCriar, TimeEditar, TimeLer, TimeResumoLer
from modelos import (
    Agente,
    Automacao,
    Conversa,
    Execucao,
    Instrumento,
    MensagemConversa,
    PassoExecucao,
    Time,
    Usuario,
)
from rotas._comum import organizacao_acessivel, time_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["times"])


@rotas.get("/organizacoes/{organizacao_id}/times", response_model=list[TimeLer])
def listar(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id)
    consulta = (
        select(Time)
        .where(Time.organizacao_id == organizacao_id)
        .order_by(Time.criado_em)
    )
    return sessao.scalars(consulta).all()


@rotas.post(
    "/organizacoes/{organizacao_id}/times",
    response_model=TimeLer,
    status_code=status.HTTP_201_CREATED,
)
def criar(
    organizacao_id: uuid.UUID,
    dados: TimeCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="admin")
    time = Time(
        organizacao_id=organizacao_id, nome=dados.nome, descricao=dados.descricao
    )
    sessao.add(time)
    sessao.flush()
    auditoria.registrar(
        sessao, usuario=usuario, acao="time.criado", recurso_tipo="time",
        recurso_id=time.id, organizacao_id=organizacao_id,
    )
    sessao.commit()
    sessao.refresh(time)
    return time


@rotas.get("/times/{time_id}", response_model=TimeLer)
def obter(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return time_acessivel(sessao, usuario, time_id)


@rotas.get("/times/{time_id}/resumo", response_model=TimeResumoLer)
def resumo(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Visão de saúde do time: contadores das coleções + agregados para a barra de
    abas e a aba Início. Só agregação/leitura (qualquer membro) — não toca o núcleo."""
    time_acessivel(sessao, usuario, time_id)

    def _contar(modelo, condicao) -> int:
        return (
            sessao.scalar(select(func.count()).select_from(modelo).where(condicao))
            or 0
        )

    n_agentes = _contar(Agente, Agente.time_id == time_id)
    n_instrumentos = _contar(Instrumento, Instrumento.time_id == time_id)

    # Automações do time (precisamos das linhas para o gatilho principal).
    automacoes = sessao.scalars(
        select(Automacao)
        .where(Automacao.time_id == time_id)
        .order_by(Automacao.ativa.desc(), Automacao.criado_em)
    ).all()
    # Gatilho "principal" = o da primeira automação ativa (ou a primeira que houver).
    gatilho = automacoes[0].tipo_gatilho if automacoes else None
    ativo = any(a.ativa for a in automacoes)

    # Estados das execuções de todas as automações do time.
    estados_exec = sessao.scalars(
        select(Execucao.estado)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .where(Automacao.time_id == time_id)
    ).all()
    n_execucoes = len(estados_exec)
    pendencias = sum(1 for e in estados_exec if e == "aguardando_humano")
    concluidas = sum(1 for e in estados_exec if e == "concluida")
    falhou = sum(1 for e in estados_exec if e == "falhou")
    finalizadas = concluidas + falhou
    taxa_sucesso = round(concluidas / finalizadas, 4) if finalizadas else None

    # Conversas dos canais do time (estado p/ contar e detectar "em andamento").
    estados_conv = sessao.scalars(
        select(Conversa.estado)
        .join(Instrumento, Instrumento.id == Conversa.instrumento_id)
        .where(Instrumento.time_id == time_id)
    ).all()
    n_conversas = len(estados_conv)
    conversas_em_andamento = sum(1 for e in estados_conv if e != "fechada")

    # Custo acumulado: mesmo cálculo do /uso/resumo com filtro de time (passos das
    # execuções + uso de IA dos turnos de atendimento). A conversa da IA criadora é
    # da organização, não do time, então fica de fora aqui.
    passos = sessao.scalars(
        select(PassoExecucao)
        .join(Execucao, Execucao.id == PassoExecucao.execucao_id)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .where(Automacao.time_id == time_id)
    ).all()
    mensagens = sessao.scalars(
        select(MensagemConversa)
        .join(Conversa, Conversa.id == MensagemConversa.conversa_id)
        .join(Instrumento, Instrumento.id == Conversa.instrumento_id)
        .where(Instrumento.time_id == time_id)
        .where(MensagemConversa.uso.isnot(None))
    ).all()
    uso = precos.resumir_uso(passos, (), mensagens)

    return TimeResumoLer(
        agentes=n_agentes,
        instrumentos=n_instrumentos,
        automacoes=len(automacoes),
        execucoes=n_execucoes,
        conversas=n_conversas,
        ativo=ativo,
        gatilho=gatilho,
        custo_acumulado_usd=uso["custo_usd"],
        taxa_sucesso=taxa_sucesso,
        pendencias=pendencias,
        conversas_em_andamento=conversas_em_andamento,
    )


@rotas.put("/times/{time_id}", response_model=TimeLer)
def editar(
    time_id: uuid.UUID,
    dados: TimeEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time = time_acessivel(sessao, usuario, time_id, minimo="operador")
    time.nome = dados.nome
    time.descricao = dados.descricao
    sessao.commit()
    sessao.refresh(time)
    return time


@rotas.delete("/times/{time_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time = time_acessivel(sessao, usuario, time_id, minimo="admin")
    auditoria.registrar(
        sessao, usuario=usuario, acao="time.removido", recurso_tipo="time",
        recurso_id=time.id, organizacao_id=time.organizacao_id,
    )
    sessao.delete(time)
    sessao.commit()
