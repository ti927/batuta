"""A página de status por dentro — os ELOS da corrente (§12-A).

`GET /saude/elos` — a foto completa dos elos (estado, latência, última checagem,
erro traduzido). Lê o cache do vigia (`saude_elos`), sem disparar sonda — barato o
bastante para a página de status fazer poll a cada 10 s. Requer login (a foto expõe
nomes de canais e provedores; não é para o público).

`POST /saude/elos/{elo_id}/reconectar` — o botão "Reconectar": executa a cura do
elo (derrubar o pool do banco, reconstruir o checkpointer, re-registrar o webhook,
religar um job interno) e re-sonda na hora. Restrito aos admins da consultoria —
é ação operacional, não de leitura.
"""

from fastapi import APIRouter, Depends, HTTPException, status

import saude_elos
from auth import usuario_atual
from consultoria import exigir_admin_consultoria
from modelos import Usuario

rotas = APIRouter(tags=["saude"])


@rotas.get("/saude/elos")
def listar_elos(usuario: Usuario = Depends(usuario_atual)):
    return saude_elos.foto()


@rotas.post("/saude/elos/{elo_id}/reconectar")
def reconectar(elo_id: str, usuario: Usuario = Depends(usuario_atual)):
    exigir_admin_consultoria(usuario)
    try:
        return saude_elos.reconectar_elo(elo_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Não conheço esse elo.")
    except ValueError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este elo não tem reconexão pelo Batuta — a causa está do lado de fora "
            "(rede ou serviço externo); acompanhe pela página de status.",
        )
