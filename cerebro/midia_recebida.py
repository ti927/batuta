"""Contexto por-turno das IMAGENS que o contato acabou de enviar numa conversa.

A borda da mensageria — que recebe e já BAIXA a imagem para lê-la (visão) — deposita
aqui os bytes da(s) imagem(ns) do turno; o instrumento `arquivar_imagem` os lê para
GUARDAR sob demanda (quando o markdown do agente mandar) e devolver a URL pública. É o
elo que deixa o "guardar" ser decidido pelo agente, caso a caso, sem a borda persistir
tudo.

Padrão de `ContextVar`, igual ao `usar_chaves` — vazio fora de um turno. Módulo de nível
superior e SEM imports do projeto, de propósito: instrumentos e mensageria importam daqui
sem criar ciclo.
"""

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager

_imagens: contextvars.ContextVar[list[dict]] = contextvars.ContextVar(
    "imagens_recebidas", default=[]
)


@contextmanager
def usar_imagens_recebidas(imagens: list[dict] | None) -> Iterator[None]:
    """Fixa as imagens recebidas no turno durante o bloco (sempre limpa ao sair, para
    um trabalhador reutilizado não vazar imagens de uma conversa para a próxima)."""
    token = _imagens.set(list(imagens or []))
    try:
        yield
    finally:
        _imagens.reset(token)


def imagens_recebidas_atuais() -> list[dict]:
    """As imagens que o contato enviou no turno atual — cada uma `{bytes, mime, legenda}`.
    Vazio fora de um turno de conversa (ex.: numa execução de cadeia comum)."""
    return _imagens.get()
