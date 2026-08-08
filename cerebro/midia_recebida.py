"""Contexto por-turno das IMAGENS que o contato acabou de enviar numa conversa.

A borda da mensageria — que recebe e já BAIXA a imagem para lê-la (visão) — deposita
aqui os bytes da(s) imagem(ns) do turno; o instrumento `arquivar_imagem` os lê para
GUARDAR sob demanda (quando o markdown do agente mandar) e devolver a URL pública. É o
elo que deixa o "guardar" ser decidido pelo agente, caso a caso, sem a borda persistir
tudo.

Fallback entre turnos: se o agente arquiva NUM TURNO POSTERIOR ao do envio (ex.: recebe
o recibo, identifica o projeto e só então guarda), não há foto fresca no turno. Aí entra
o `resgatar` — um callable opcional que RE-BAIXA a imagem mais recente pelo `file_id`
salvo (o Telegram guarda o arquivo). Chamado só quando não há foto fresca (lazy), para
não baixar à toa em todo turno.

Padrão de `ContextVar`, igual ao `usar_chaves` — vazio fora de um turno. Módulo de nível
superior e SEM imports do projeto, de propósito: instrumentos e mensageria importam daqui
sem criar ciclo (o `resgatar` carrega a lógica de rede, injetada pela mensageria).
"""

import contextvars
from collections.abc import Callable, Iterator
from contextlib import contextmanager

_imagens: contextvars.ContextVar[list[dict]] = contextvars.ContextVar(
    "imagens_recebidas", default=[]
)
_resgatar: contextvars.ContextVar[Callable[[], list[dict]] | None] = contextvars.ContextVar(
    "resgatar_imagens", default=None
)


@contextmanager
def usar_imagens_recebidas(
    imagens: list[dict] | None, resgatar: Callable[[], list[dict]] | None = None
) -> Iterator[None]:
    """Fixa as imagens recebidas no turno durante o bloco (sempre limpa ao sair, para
    um trabalhador reutilizado não vazar imagens de uma conversa para a próxima).
    `resgatar` (opcional): re-baixa a imagem mais recente da conversa quando não há foto
    fresca no turno — o fallback que deixa o agente GUARDAR num turno posterior ao envio."""
    t1 = _imagens.set(list(imagens or []))
    t2 = _resgatar.set(resgatar)
    try:
        yield
    finally:
        _imagens.reset(t1)
        _resgatar.reset(t2)


def imagens_recebidas_atuais() -> list[dict]:
    """As imagens que o contato enviou no turno atual — cada uma `{bytes, mime, legenda}`.
    Se não houver foto fresca, tenta RESGATAR a mais recente da conversa (re-baixando pelo
    file_id) — para arquivar num turno posterior. Vazio fora de um turno de conversa."""
    frescas = _imagens.get()
    if frescas:
        return frescas
    resgatar = _resgatar.get()
    if resgatar is not None:
        try:
            return resgatar() or []
        except Exception:
            return []
    return []
