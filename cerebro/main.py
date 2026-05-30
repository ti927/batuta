from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import agendador
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
    """Sobe o relógio dos gatilhos por agendamento ao iniciar; desliga ao parar."""
    agendador.iniciar()
    yield
    agendador.desligar()


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
