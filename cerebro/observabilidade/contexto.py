"""Contexto de log da requisição/execução em curso (ContextVar).

Mesmo molde de `orquestracao.llm.usar_chaves` e `orquestracao.atividade.usar_atividade`:
um ContextVar atravessa todo o stack — inclusive as threads dos workers da fila (via
`copy_context` que o LangChain já usa) — carregando "quem fez, de onde, em qual
requisição", sem mudar a assinatura de nenhuma função.

Quem fixa o contexto:
- o middleware HTTP (por requisição): request_id, ip_cliente, rota, tela, http_metodo;
- a dependência de auth completa o `usuario_id` quando o usuário é resolvido;
- os workers (fila/fila_turnos/agendador), que rodam FORA de um request, fixam o seu
  próprio contexto por tarefa (execucao_id, automacao_id, origem, request_id próprio).

`registrar_evento` (escritor.py) e o `FormatadorJSON` (log.py) leem `contexto_atual()`.
"""

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

# Dict imutável-por-token com o contexto do momento. Default vazio: fora de qualquer
# bloco (testes, chamadas soltas) não há contexto e tudo funciona sem carimbo.
_ctx: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "log_ctx", default={}
)


def _sem_nulos(campos: dict[str, Any]) -> dict[str, Any]:
    """Só propaga fatos CONHECIDOS — um campo None nunca sobrescreve um valor já sabido."""
    return {k: v for k, v in campos.items() if v is not None}


@contextmanager
def usar_contexto(**campos: Any) -> Iterator[None]:
    """Fixa/mescla campos de contexto durante o bloco. Sai sempre limpando (try/finally),
    para um worker reutilizado não vazar o contexto de uma tarefa para a próxima."""
    token = _ctx.set({**_ctx.get(), **_sem_nulos(campos)})
    try:
        yield
    finally:
        _ctx.reset(token)


def completar(**campos: Any) -> None:
    """Acrescenta campos ao contexto atual SEM abrir/fechar bloco (ex.: a auth descobre
    o `usuario_id` no meio do request). Cria um novo dict (não muta o anterior), para
    threads que já copiaram o contexto não serem afetadas."""
    novos = _sem_nulos(campos)
    if novos:
        _ctx.set({**_ctx.get(), **novos})


def contexto_atual() -> dict[str, Any]:
    """Cópia do contexto do momento (lida pelo escritor e pelo formatador)."""
    return dict(_ctx.get())
