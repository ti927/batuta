"""Endpoints de execução da orquestração.

Acionar um agente sozinho (Tarefa 4.2): recebe uma entrada, carrega o cinto do
agente e executa. Acesso por papel (Fase 6): executar é ação de operador.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import usuario_atual
from esquemas import ExecutarAgente
from modelos import AgenteInstrumento, Instrumento, Usuario
from orquestracao.agente import executar_agente
from rotas._comum import agente_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["execucao"])


@rotas.post("/agentes/{agente_id}/executar")
def executar(
    agente_id: uuid.UUID,
    dados: ExecutarAgente,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    agente = agente_acessivel(sessao, usuario, agente_id, minimo="operador")
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
