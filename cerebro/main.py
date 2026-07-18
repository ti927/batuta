import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import agendador
import fila
from arquivos import DIRETORIO_ARQUIVOS
from rotas import (
    agentes,
    ajuda,
    automacoes,
    chaves_api,
    cinto,
    credenciais,
    criacao,
    google,
    instagram,
    instagram_webhook,
    instrumentos,
    membros,
    mensageria,
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

# Origens do navegador autorizadas a chamar o cérebro (CORS). A interface fala com
# o cérebro a partir do navegador, então a origem dela precisa estar aqui. Vem de
# INTERFACE_ORIGINS (CSV) — em produção, a URL da interface no Railway; no dev, o
# default localhost:3000.
_origens = os.environ.get("INTERFACE_ORIGINS", "http://localhost:3000")
ORIGENS_PERMITIDAS = [o.strip() for o in _origens.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENS_PERMITIDAS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/saude")
def saude():
    # `versao` = commit no ar (a Railway injeta RAILWAY_GIT_COMMIT_SHA). Serve para
    # confirmar, sem adivinhação, qual código produção está realmente rodando.
    return {
        "mensagem": "Batuta cérebro no ar",
        "versao": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev"),
    }


app.include_router(organizacoes.rotas)
app.include_router(membros.rotas)
app.include_router(times.rotas)
app.include_router(agentes.rotas)
app.include_router(instrumentos.rotas)
app.include_router(cinto.rotas)
app.include_router(automacoes.rotas)
app.include_router(chaves_api.rotas)
app.include_router(credenciais.rotas)
app.include_router(criacao.rotas)
app.include_router(google.rotas)
app.include_router(instagram.rotas)
app.include_router(instagram_webhook.rotas)
app.include_router(webhooks.rotas)
app.include_router(mensageria.rotas)
app.include_router(ajuda.rotas)

# Arquivos gerados (ex.: PDFs do instrumento gerar_pdf), servidos localmente.
app.mount("/arquivos", StaticFiles(directory=DIRETORIO_ARQUIVOS), name="arquivos")
