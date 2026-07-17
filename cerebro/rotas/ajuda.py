"""Rotas da Central de Conhecimento (leitura humana, em `/ajuda`).

Servem os capítulos que vivem em `cerebro/central/` (via `conhecimento.py`, a mesma
fonte que a ferramenta da IA usa). Conteúdo genérico do produto — exige só estar
logado (sem escopo de organização). O front renderiza o markdown.
"""

from fastapi import APIRouter, Depends, HTTPException, status

import conhecimento
from auth import usuario_atual
from modelos import Usuario

rotas = APIRouter(tags=["ajuda"])


@rotas.get("/ajuda/indice")
def indice(_: Usuario = Depends(usuario_atual)):
    """Lista os capítulos (resumo, sem o corpo), para o menu/busca da Central."""
    return {"capitulos": conhecimento.indice()}


@rotas.get("/ajuda/{slug:path}")
def capitulo(slug: str, _: Usuario = Depends(usuario_atual)):
    """Um capítulo pelo slug (caminho relativo, ex.: `instrumentos/publicar-instagram`)."""
    cap = conhecimento.obter(slug)
    if cap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capítulo não encontrado.")
    return {
        "slug": cap.slug,
        "titulo": cap.titulo,
        "area": cap.area,
        "tags": list(cap.tags),
        "revisado_em": cap.revisado_em,
        "fontes": list(cap.fontes),
        "corpo": cap.corpo,
    }
