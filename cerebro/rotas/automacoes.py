"""Endpoints de Automações e Execuções.

Uma automação é a definição de um fluxo: o gatilho e a cadeia (o grafo de
agentes com bifurcação). Aqui se monta a automação (CRUD), dispara-se
manualmente (Etapa 1), e cada passo é gravado em `passos_execucao` para a tela
de inspeção (Tarefas 4.3, 4.4 e 4.5).
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from esquemas import (
    AutomacaoCriar,
    AutomacaoEditar,
    AutomacaoLer,
    DispararAutomacao,
    ExecucaoComPassos,
    ExecucaoLer,
    PassoExecucaoLer,
)
from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao.cadeia import executar_cadeia, validar_cadeia
from rotas._comum import time_do_dono
from sessao import obter_sessao

rotas = APIRouter(tags=["automacoes"])


def _automacao_do_dono(sessao: Session, automacao_id: uuid.UUID) -> Automacao:
    auto = sessao.get(Automacao, automacao_id)
    if auto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Automação não encontrada")
    time_do_dono(sessao, auto.time_id)
    return auto


def _ids_dos_agentes(sessao: Session, time_id: uuid.UUID) -> set[str]:
    return {
        str(i)
        for i in sessao.scalars(
            select(Agente.id).where(Agente.time_id == time_id)
        ).all()
    }


def _validar_cadeia_ou_422(sessao: Session, time_id: uuid.UUID, cadeia: dict) -> None:
    try:
        validar_cadeia(cadeia or {}, _ids_dos_agentes(sessao, time_id))
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


# ───────────────────────── CRUD de automações ────────────────────


@rotas.get("/times/{time_id}/automacoes", response_model=list[AutomacaoLer])
def listar(time_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    time_do_dono(sessao, time_id)
    return sessao.scalars(
        select(Automacao)
        .where(Automacao.time_id == time_id)
        .order_by(Automacao.criado_em)
    ).all()


@rotas.post(
    "/times/{time_id}/automacoes",
    response_model=AutomacaoLer,
    status_code=status.HTTP_201_CREATED,
)
def criar(
    time_id: uuid.UUID,
    dados: AutomacaoCriar,
    sessao: Session = Depends(obter_sessao),
):
    time_do_dono(sessao, time_id)
    _validar_cadeia_ou_422(sessao, time_id, dados.cadeia)
    auto = Automacao(time_id=time_id, **dados.model_dump())
    sessao.add(auto)
    sessao.commit()
    sessao.refresh(auto)
    return auto


@rotas.get("/automacoes/{automacao_id}", response_model=AutomacaoLer)
def obter(automacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    return _automacao_do_dono(sessao, automacao_id)


@rotas.put("/automacoes/{automacao_id}", response_model=AutomacaoLer)
def editar(
    automacao_id: uuid.UUID,
    dados: AutomacaoEditar,
    sessao: Session = Depends(obter_sessao),
):
    auto = _automacao_do_dono(sessao, automacao_id)
    _validar_cadeia_ou_422(sessao, auto.time_id, dados.cadeia)
    for campo, valor in dados.model_dump().items():
        setattr(auto, campo, valor)
    sessao.commit()
    sessao.refresh(auto)
    return auto


@rotas.delete("/automacoes/{automacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(automacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    auto = _automacao_do_dono(sessao, automacao_id)
    sessao.delete(auto)
    sessao.commit()


# ─────────────────────── Disparo e inspeção ──────────────────────


def _montar_com_passos(sessao: Session, execucao: Execucao) -> ExecucaoComPassos:
    passos = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem)
    ).all()
    base = ExecucaoLer.model_validate(execucao).model_dump()
    return ExecucaoComPassos(
        **base, passos=[PassoExecucaoLer.model_validate(p) for p in passos]
    )


@rotas.post(
    "/automacoes/{automacao_id}/disparar", response_model=ExecucaoComPassos
)
def disparar(
    automacao_id: uuid.UUID,
    dados: DispararAutomacao,
    sessao: Session = Depends(obter_sessao),
):
    auto = _automacao_do_dono(sessao, automacao_id)

    execucao = Execucao(
        automacao_id=auto.id,
        estado="em_andamento",
        entrada={"texto": dados.entrada},
        iniciada_em=datetime.now(timezone.utc),
    )
    sessao.add(execucao)
    sessao.commit()
    sessao.refresh(execucao)

    def registrar(passo: dict, ordem: int) -> None:
        sessao.add(
            PassoExecucao(
                execucao_id=execucao.id,
                ordem=ordem,
                agente_id=uuid.UUID(passo["agente_id"]),
                entrada={"texto": passo["entrada"]},
                saida={
                    "texto": passo["saida"],
                    "instrumentos_acionados": passo["instrumentos_acionados"],
                    "saida_escolhida": passo["saida_escolhida"],
                },
                estado="concluido",
                iniciado_em=passo["iniciado_em"],
                finalizado_em=passo["finalizado_em"],
            )
        )
        sessao.commit()

    try:
        r = executar_cadeia(
            sessao, auto.cadeia or {}, dados.entrada, registrar_passo=registrar
        )
        execucao.estado = "concluida"
        execucao.resultado = {"texto": r["resultado"]}
    except Exception as e:  # falha de LLM/rede/cadeia inválida — registra e segue
        execucao.estado = "falhou"
        execucao.resultado = {"erro": str(e)}
    execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(execucao)
    return _montar_com_passos(sessao, execucao)


@rotas.get(
    "/automacoes/{automacao_id}/execucoes", response_model=list[ExecucaoLer]
)
def listar_execucoes(
    automacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao)
):
    _automacao_do_dono(sessao, automacao_id)
    return sessao.scalars(
        select(Execucao)
        .where(Execucao.automacao_id == automacao_id)
        .order_by(Execucao.criado_em.desc())
    ).all()


@rotas.get("/execucoes/{execucao_id}", response_model=ExecucaoComPassos)
def obter_execucao(execucao_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    execucao = sessao.get(Execucao, execucao_id)
    if execucao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execução não encontrada")
    _automacao_do_dono(sessao, execucao.automacao_id)
    return _montar_com_passos(sessao, execucao)
