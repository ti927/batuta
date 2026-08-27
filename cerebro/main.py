import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import agendador
import fila
import fila_turnos
import saude_elos
from arquivos import DIRETORIO_ARQUIVOS
from orquestracao import memoria_conversa
from observabilidade.log import configurar_logging
from observabilidade.middleware import MiddlewareLog
from rotas import (
    agentes,
    ajuda,
    automacoes,
    chaves_api,
    cinto,
    credenciais,
    criacao,
    elos,
    google,
    instagram,
    instagram_webhook,
    instrumentos,
    logs,
    membros,
    mensageria,
    organizacoes,
    times,
    webhooks,
)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Sobe a fila de execuções, a fila de turnos da IA criadora (ambas pools de
    trabalhadores) e o relógio dos gatilhos por agendamento ao iniciar; desliga tudo
    ao parar."""
    configurar_logging()  # logs estruturados (JSON) com identidade de servidor
    # Memória entre turnos da conversa (Fatia 4.3/P2a): cria/garante as tabelas de
    # checkpoint. À prova de falha — se não subir, a conversa cai no modo legado.
    memoria_conversa.preparar()
    fila.iniciar()
    fila_turnos.iniciar()
    agendador.iniciar()
    yield
    agendador.desligar()
    fila_turnos.desligar()
    fila.desligar()
    memoria_conversa.desligar()


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

# Observabilidade: adicionado por ÚLTIMO para ser o mais externo — envolve todo request
# (inclusive o CORS), fixando o contexto de log e registrando status/latência.
app.add_middleware(MiddlewareLog)


# Momento em que ESTE processo subiu (UTC). Na Railway, um deploy novo = contêiner
# novo = novo boot — então serve de "no ar desde" para o selo de versão da barra
# lateral (a interface lê daqui, sem precisar do painel do Railway).
INICIADO_EM = datetime.now(timezone.utc).isoformat()


@app.get("/saude")
def saude():
    """Sinal de vida do cérebro — e dos seus ÓRGÃOS.

    Até 2026-08-26 esta rota só dizia "estou no ar", e foi assim que ela enganou:
    o app respondia normalmente enquanto a memória de conversa estava caída havia
    dias (levando junto a trava de ação irreversível). Um subsistema morto não
    derruba o HTTP — só faz o produto perder capacidade em silêncio. Por isso o
    `/saude` agora responde por cada peça de segundo plano, e a barra lateral usa
    isso para avisar. Público e barato: só lê estado em memória, sem tocar o banco.
    """
    subsistemas = {
        # Memória entre turnos da conversa (checkpointer). Degradado = conversa
        # recomeça do texto a cada turno e o portão nativo não segura o irreversível.
        "memoria_conversa": memoria_conversa.esta_saudavel(),
        # Pool que tira execução da fila. Parado = nada roda, nem gatilho nem botão.
        "fila": fila.esta_saudavel(),
        # Relógio dos gatilhos de agendamento. Parado = automação agendada nunca dispara.
        "agendador": agendador.esta_saudavel(),
    }
    degradados = sorted(nome for nome, ok in subsistemas.items() if not ok)
    # Resumo do vigia dos ELOS (sondas ativas — `saude_elos`): um elo caído entra
    # nos degradados para o selo da sidebar avisar; o detalhe fica em /saude/elos.
    elos_resumo = saude_elos.resumo()
    return {
        "mensagem": "Batuta cérebro no ar",
        # `versao` = commit no ar (a Railway injeta RAILWAY_GIT_COMMIT_SHA). Serve para
        # confirmar, sem adivinhação, qual código produção está realmente rodando.
        "versao": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev"),
        "iniciado_em": INICIADO_EM,
        "subsistemas": subsistemas,
        "degradados": sorted(set(degradados) | set(elos_resumo["elos_caidos"])),
        "elos_caidos": elos_resumo["elos_caidos"],
        "elos_degradados": elos_resumo["elos_degradados"],
        "saudavel": not degradados and not elos_resumo["elos_caidos"],
    }


app.include_router(elos.rotas)
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
app.include_router(logs.rotas)

# Arquivos gerados (ex.: PDFs do instrumento gerar_pdf), servidos localmente.
app.mount("/arquivos", StaticFiles(directory=DIRETORIO_ARQUIVOS), name="arquivos")
