from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rotas import agentes, organizacoes, times

app = FastAPI(title="Batuta — Cérebro")

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
