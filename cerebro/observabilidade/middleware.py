"""Middleware HTTP: carimba cada requisição e a correlaciona ponta a ponta.

Fixa o contexto do request (`request_id`, `ip_cliente`, `rota`, `tela`, `http_metodo`)
ANTES de chamar o endpoint — assim todo evento emitido lá dentro (e nas threads de worker
que ele dispara) herda a correlação. Ao fim, registra um evento `categoria="http"` com
status + latência (persistido só em erro; GET 2xx fica só no stdout, para não inflar o
banco). Devolve `X-Request-Id` na resposta, fechando a correlação com o cliente.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from observabilidade.contexto import usar_contexto
from observabilidade.escritor import registrar_evento


def _ip_cliente(request: Request) -> str | None:
    """IP real do cliente. Railway/Cloudflare põem o IP de origem em X-Forwarded-For
    (o primeiro da lista); fallback para o peer direto."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


class MiddlewareLog(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        tela = request.headers.get("x-batuta-tela")
        ip = _ip_cliente(request)
        inicio = time.perf_counter()
        status = 500
        erro: BaseException | None = None
        with usar_contexto(
            request_id=request_id,
            ip_cliente=ip,
            rota=request.url.path,
            tela=tela,
            http_metodo=request.method,
        ):
            try:
                resposta = await call_next(request)
                status = resposta.status_code
                resposta.headers["X-Request-Id"] = request_id
                return resposta
            except BaseException as e:  # noqa: BLE001 — captura p/ logar, depois repropaga
                erro = e
                raise
            finally:
                latencia = int((time.perf_counter() - inicio) * 1000)
                # A auth resolve o usuário e o guarda em request.state (o contexto do
                # endpoint roda num filho e não volta até aqui).
                usuario_id = getattr(request.state, "usuario_id", None)
                falhou = erro is not None or status >= 400
                registrar_evento(
                    categoria="http",
                    acao=f"{request.method} {request.url.path}",
                    nivel="error" if erro else ("warning" if status >= 500 else "info"),
                    resultado="falha" if falhou else "sucesso",
                    # 2xx/3xx de leitura → só stdout; erros e 4xx/5xx → banco.
                    persistir=falhou,
                    erro=erro,
                    http_status=status,
                    latencia_ms=latencia,
                    usuario_id=usuario_id,
                )
