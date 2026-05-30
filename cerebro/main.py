from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import agendador
import fila
from arquivos import DIRETORIO_ARQUIVOS
from rotas import (
    agentes,
    automacoes,
    cinto,
    execucao,
    instrumentos,
    organizacoes,
    times,
    webhooks,
)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Sobe a fila de execuções (pool de trabalhadores) e o relógio dos gatilhos
    por agendamento ao iniciar; desliga ambos ao parar."""
    fila.iniciar()
    agendador.iniciar()
    yield
    agendador.desligar()
    fila.desligar()


app = FastAPI(title="Batuta — Cérebro", lifespan=ciclo_de_vida)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/saude")
def saude():
    return {"mensagem": "Batuta cérebro no ar"}


app.include_router(organizacoes.rotas)
app.include_router(times.rotas)
app.include_router(agentes.rotas)
app.include_router(instrumentos.rotas)
app.include_router(cinto.rotas)
app.include_router(execucao.rotas)
app.include_router(automacoes.rotas)
app.include_router(webhooks.rotas)

# Arquivos gerados (ex.: PDFs do instrumento gerar_pdf), servidos localmente.
app.mount("/arquivos", StaticFiles(directory=DIRETORIO_ARQUIVOS), name="arquivos")
