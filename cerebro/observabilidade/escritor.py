"""Escritor central de eventos: `registrar_evento(...)`.

Duas saídas para cada evento:
1. **stdout JSON** — SEMPRE (barato, vai para os logs do Railway/terminal).
2. **banco (`evento_log`)** — CONDICIONAL (política de volume), em transação PRÓPRIA e
   curta (molde `disparo._escrever_atividade`), dentro de um `try/except` que engole
   qualquer erro: um log NUNCA pode derrubar o request/execução.

Regras:
- Um cérebro `local` (banco compartilhado com produção) **não persiste** — só stdout, para
  dev não poluir a tabela de produção. O carimbo `ambiente` distingue os dois.
- Segredos são redigidos (`log.redigir`) antes de sair.
- O contexto do momento (`contexto_atual()`) preenche quem/requisição/origem sem o chamador
  repetir tudo.
"""

import logging
import traceback
import uuid
from typing import Any

from observabilidade.contexto import contexto_atual
from observabilidade.log import EH_LOCAL, IDENTIDADE_SERVIDOR, redigir

logger = logging.getLogger("batuta.evento")

# Categorias cujos eventos (mesmo `info`) valem persistência — ações e efeitos, não leitura.
CATEGORIAS_PERSISTENTES = {
    "auth",
    "disparo",
    "execucao",
    "agendador",
    "fila",
    "mensageria",
    "criacao",
    "escrita",
    "instrumento",
    "cliente",
    "sistema",
}
NIVEIS_PERSISTENTES = {"WARNING", "ERROR", "CRITICAL"}

_NIVEIS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _deve_persistir(categoria: str, nivel: str, persistir: bool | None) -> bool:
    if EH_LOCAL:
        return False  # cérebro local nunca escreve no banco (compartilhado com produção)
    if persistir is not None:
        return persistir
    if nivel in NIVEIS_PERSISTENTES:
        return True
    return categoria in CATEGORIAS_PERSISTENTES


def _texto_do_erro(erro: Any) -> str | None:
    if erro is None:
        return None
    if isinstance(erro, BaseException):
        return "".join(
            traceback.format_exception(type(erro), erro, erro.__traceback__)
        )[:8000]
    return str(erro)[:8000]


def _uuid(valor: Any) -> uuid.UUID | None:
    """Aceita UUID ou string; devolve UUID ou None (nunca levanta — logar não pode falhar)."""
    if valor is None:
        return None
    if isinstance(valor, uuid.UUID):
        return valor
    try:
        return uuid.UUID(str(valor))
    except (ValueError, AttributeError, TypeError):
        return None


def registrar_evento(
    *,
    categoria: str,
    acao: str,
    nivel: str = "info",
    resultado: str | None = None,
    erro: Any = None,
    persistir: bool | None = None,
    detalhe: dict | None = None,
    **campos: Any,
) -> None:
    """Registra um evento. `categoria`/`acao` são obrigatórios; `campos` sobrescrevem o
    contexto (ex.: `organizacao_id`, `time_id`, `origem`, `recurso_tipo`, `recurso_id`,
    `http_status`, `latencia_ms`, `ip_cliente`). Best-effort: nunca levanta."""
    nivel_up = nivel.upper()
    ctx = contexto_atual()
    erro_texto = _texto_do_erro(erro)
    detalhe_red = redigir(detalhe) if detalhe else None

    def _campo(nome: str) -> Any:
        return campos.get(nome) if campos.get(nome) is not None else ctx.get(nome)

    # 1) stdout JSON — sempre.
    try:
        logger.log(
            _NIVEIS.get(nivel_up, logging.INFO),
            acao,
            extra={
                "categoria": categoria,
                **({"resultado": resultado} if resultado else {}),
                **({"erro_texto": erro_texto} if erro_texto else {}),
                **{k: v for k, v in campos.items() if v is not None},
            },
        )
    except Exception:  # noqa: BLE001 — logar nunca pode falhar
        pass

    # 2) banco — condicional e best-effort (transação própria e curta).
    if not _deve_persistir(categoria, nivel_up, persistir):
        return
    try:
        from modelos import EventoLog
        from sessao import CriadorDeSessao

        s = CriadorDeSessao()
        try:
            s.add(
                EventoLog(
                    nivel=nivel_up.lower()[:10],
                    categoria=categoria[:30],
                    acao=acao[:80],
                    resultado=resultado,
                    usuario_id=_uuid(_campo("usuario_id")),
                    organizacao_id=_uuid(_campo("organizacao_id")),
                    time_id=_uuid(_campo("time_id")),
                    recurso_tipo=(_campo("recurso_tipo") or None),
                    recurso_id=_uuid(_campo("recurso_id")),
                    request_id=(str(_campo("request_id"))[:36] if _campo("request_id") else None),
                    host=IDENTIDADE_SERVIDOR["host"],
                    pid=IDENTIDADE_SERVIDOR["pid"],
                    commit=IDENTIDADE_SERVIDOR["commit"],
                    ambiente=IDENTIDADE_SERVIDOR["ambiente"],
                    ip_cliente=(_campo("ip_cliente") or None),
                    origem=(_campo("origem") or None),
                    http_metodo=(_campo("http_metodo") or None),
                    rota=(str(_campo("rota"))[:200] if _campo("rota") else None),
                    http_status=_campo("http_status"),
                    latencia_ms=_campo("latencia_ms"),
                    erro_texto=erro_texto,
                    detalhe=detalhe_red,
                )
            )
            s.commit()
        finally:
            s.close()
    except Exception:  # noqa: BLE001 — persistir log nunca pode derrubar o chamador
        logger.debug("Falha ao persistir evento_log (ignorada).", exc_info=True)
