"""Fundação de logging estruturado: identidade de servidor + formatador JSON.

- `IDENTIDADE_SERVIDOR`: carimbo fixo (host/pid/commit/ambiente) em TODO log/evento. É o
  dado que faltou no incidente do cérebro local — um evento com `ambiente=local` num banco
  de produção é o alarme.
- `redigir`: mascara segredos (Authorization, tokens, chaves) recursivamente — guardrail
  usado tanto pelo stdout quanto pela persistência.
- `FormatadorJSON`: uma linha JSON por log, com identidade + contexto (`contexto_atual()`)
  + extras do `logger.*(..., extra=...)`.
- `configurar_logging`: instala o handler JSON no logger raiz `batuta` (idempotente). Os 6
  loggers `batuta.*` já existentes herdam sem reescrever nenhuma chamada.
"""

import json
import logging
import os
import socket
import sys
from datetime import datetime, timezone
from typing import Any

from observabilidade.contexto import contexto_atual


def _detectar_ambiente() -> str:
    """`railway` se qualquer variável do Railway está presente; senão `local`. É o
    discriminador dev↔produção — o banco é o MESMO, então o carimbo é a única forma de
    saber de onde um evento veio."""
    chaves = (
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
        "RAILWAY_DEPLOYMENT_ID",
    )
    return "railway" if any(os.environ.get(k) for k in chaves) else "local"


IDENTIDADE_SERVIDOR: dict[str, Any] = {
    "host": socket.gethostname(),
    "pid": os.getpid(),
    "commit": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev"),
    "ambiente": _detectar_ambiente(),
}

# Um cérebro LOCAL não escreve logs no banco (compartilhado com produção) — só stdout.
EH_LOCAL: bool = IDENTIDADE_SERVIDOR["ambiente"] == "local"

# Fragmentos de nome que marcam um campo como SEGREDO — nunca vão para log/banco.
CHAVES_SENSIVEIS = (
    "authorization",
    "token",
    "api_key",
    "apikey",
    "chave",
    "senha",
    "password",
    "secret",
    "segredo",
    "bearer",
    "cookie",
    "valor_cifrado",
    "webhook_secret",
)


def _sensivel(nome: object) -> bool:
    n = str(nome).lower()
    return any(t in n for t in CHAVES_SENSIVEIS)


def redigir(obj: Any) -> Any:
    """Mascara recursivamente qualquer chave sensível (por nome) em dicts/listas."""
    if isinstance(obj, dict):
        return {k: ("***" if _sensivel(k) else redigir(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redigir(v) for v in obj]
    return obj


# Atributos padrão de um LogRecord — o que sobra é "extra" passado por quem loga.
_PADRAO = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


class FormatadorJSON(logging.Formatter):
    """Uma linha JSON por registro: timestamp UTC, nível, logger, mensagem, identidade
    do servidor, contexto do momento e os extras (redigidos)."""

    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **IDENTIDADE_SERVIDOR,
            **contexto_atual(),
        }
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _PADRAO and not k.startswith("_")
        }
        if extras:
            base.update(redigir(extras))
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str, ensure_ascii=False)


def configurar_logging() -> None:
    """Instala o handler JSON no logger raiz `batuta` (idempotente). Chamado no lifespan.
    Os loggers `batuta.*` (agendador, fila, fila_turnos, http, evento, …) herdam. Não mexe
    nos loggers do uvicorn (que já têm handler próprio)."""
    nivel = os.environ.get("LOG_NIVEL", "INFO").upper()
    base = logging.getLogger("batuta")
    if any(getattr(h, "_batuta_json", False) for h in base.handlers):
        base.setLevel(nivel)  # já configurado — só reafirma o nível
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatadorJSON())
    handler._batuta_json = True  # type: ignore[attr-defined]
    base.addHandler(handler)
    base.setLevel(nivel)
    base.propagate = False  # não duplica no root
