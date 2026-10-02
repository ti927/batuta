"""Gasto REAL dos instrumentos que chamam uma IA paga por fora (2026-10-02).

Até aqui o custo de um instrumento era estimado pela configuração, um valor fixo por
chamada (`medicao_instrumentos`). Serve para imagem (o preço é por imagem), mas não
para busca na web ou leitura de documento: o custo depende dos tokens e de quantas
buscas a IA fez. Esses instrumentos devolvem o uso informado pela própria empresa da
IA na chave `uso` do resultado; a ferramenta do agente (`agente._ferramenta_unica`)
anota aqui, e o `executar_agente` junta ao uso do turno — o mesmo caminho que leva o
custo dos tokens do agente ao banco.

Mesmo padrão do `atividade`/`usar_chaves`: um ContextVar atravessa o motor sem mudar
a assinatura de nada. Folha (só contextvars): pode ser importada de qualquer lugar.
"""

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager

_coletor: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar(
    "gasto_instrumentos", default=None
)


@contextmanager
def coletar() -> Iterator[list[dict]]:
    """Abre um coletor para o turno do agente e o entrega; sai sempre limpando."""
    lista: list[dict] = []
    token = _coletor.set(lista)
    try:
        yield lista
    finally:
        _coletor.reset(token)


def registrar(entrada: dict) -> None:
    """Anota um gasto, se há coletor aberto (fora de um turno — no "Testar" da tela —
    não há o que anotar, e não é erro)."""
    lista = _coletor.get()
    if lista is not None:
        lista.append(entrada)
