"""Endpoints de execução da orquestração.

Por enquanto, acionar um agente sozinho (Tarefa 4.2) — recebe uma entrada,
carrega o cinto do agente e executa. A execução de uma cadeia inteira
(automação) entra nas tarefas seguintes da Fase 4.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from esquemas import ExecutarAgente
from modelos import AgenteInstrumento, Instrumento
from orquestracao.agente import executar_agente
from rotas._comum import agente_do_dono
from sessao import obter_sessao

rotas = APIRouter(tags=["execucao"])


@rotas.post("/agentes/{agente_id}/executar")
def executar(
    agente_id: uuid.UUID,
    dados: ExecutarAgente,
    sessao: Session = Depends(obter_sessao),
):
    agente = agente_do_dono(sessao, agente_id)
    cinto = sessao.scalars(
        select(Instrumento)
        .join(AgenteInstrumento, AgenteInstrumento.instrumento_id == Instrumento.id)
        .where(AgenteInstrumento.agente_id == agente_id)
    ).all()
    try:
        return executar_agente(agente, list(cinto), dados.entrada)
    except Exception as e:  # falha de LLM/rede/instrumento — traduz para o cliente
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Falha na execução do agente: {e}"
        )
