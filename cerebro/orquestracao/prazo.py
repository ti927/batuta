"""PRAZO de um passo: até quando ele pode agir (Onda 3, fatia 2 — lacunas 22 e 23).

Cada instrumento tem o seu próprio limite de rede (15 s no REST, 120 s no gerar
imagem, 25 min no vídeo), e isso continua valendo: é o limite de UMA chamada. O que
faltava era um teto do PASSO INTEIRO — um agente pode encadear dez chamadas, cada uma
dentro do seu limite, e ainda assim levar quarenta minutos.

Mesmo padrão do `atividade` e do `usar_chaves`: um ContextVar atravessa o motor sem
mudar a assinatura de nenhuma função do grafo. `cadeia` fixa o prazo antes de rodar o
nó; `agente`, lá no fundo, pergunta `expirou()` antes de cada ação.

**O que este teto faz e o que NÃO faz** — e a honestidade aqui importa mais que a
funcionalidade: ele para o passo ENTRE as ações, não no meio de uma. Python não mata
uma thread com segurança, então uma chamada já em andamento vai até o fim (protegida
pelo limite do próprio instrumento) e o passo para logo depois. Na prática o estouro
fica limitado ao teto mais a duração de uma chamada — e é isso que a documentação
promete, nem uma vírgula a mais.

Fora de um bloco `usar_prazo` (testes, chamadas soltas) `expirou()` é sempre False:
sem prazo fixado, nada expira.
"""

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

# Instante em que o passo em curso deixa de poder agir. None = sem prazo.
_fim: contextvars.ContextVar[datetime | None] = contextvars.ContextVar(
    "prazo_fim", default=None
)


@contextmanager
def usar_prazo(minutos: float | None) -> Iterator[None]:
    """Fixa o prazo do passo durante o bloco. `minutos` nulo ou <= 0 = sem prazo.

    Sai sempre limpando o contexto (try/finally), para um trabalhador reutilizado não
    vazar o prazo de um passo para o próximo."""
    fim = (
        datetime.now(timezone.utc) + timedelta(minutes=float(minutos))
        if minutos
        else None
    )
    token = _fim.set(fim)
    try:
        yield
    finally:
        _fim.reset(token)


def expirou() -> bool:
    """O passo em curso já passou do prazo? False quando não há prazo fixado."""
    fim = _fim.get()
    return fim is not None and datetime.now(timezone.utc) >= fim


def restante_s() -> float | None:
    """Quantos segundos faltam, ou None quando não há prazo fixado."""
    fim = _fim.get()
    if fim is None:
        return None
    return max(0.0, (fim - datetime.now(timezone.utc)).total_seconds())
