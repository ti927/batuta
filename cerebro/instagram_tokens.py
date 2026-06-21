"""Tokens da API do Instagram (Instagram API with Instagram Login).

Funções puras de token — sem sessão nem banco: validar o token colado (e descobrir
o ID da conta) e renovar o token de longa duração antes dos 60 dias. As chamadas
vão para `graph.instagram.com`, no mesmo padrão httpx/`FalhaInstrumento` dos
instrumentos (ver `instrumentos/busca_web.py`).

Fluxo da conexão (decisão do maestro): o token gerado no PAINEL do app já nasce de
longa duração (60 dias); o maestro só o cola. Aqui validamos esse token, achamos o
`ig_user_id` (via /me) e, mais tarde, o agendador chama `renovar` para esticar a
validade — o refresh exige token com ≥24h e <60 dias de vida e NÃO usa app secret.
"""

from datetime import datetime, timedelta, timezone

import httpx

from instrumentos.base import FalhaInstrumento

GRAPH = "https://graph.instagram.com"
TIMEOUT_S = 20.0
# Validade dos tokens de longa duração do Instagram (estimativa quando a resposta
# não traz `expires_in`, como no token recém-colado do painel).
VALIDADE_PADRAO_S = 60 * 24 * 3600


def _detalhe_erro(resposta: httpx.Response) -> str:
    """O motivo que a Meta devolveu (campo `error.message`), para a mensagem ser
    útil em vez de só 'HTTP 400'. Cai no texto cru se não for JSON."""
    try:
        dados = resposta.json()
        if isinstance(dados, dict):
            erro = dados.get("error")
            if isinstance(erro, dict):
                return str(erro.get("message") or erro)[:200]
            return str(dados.get("message") or dados)[:200]
    except Exception:
        pass
    return (resposta.text or "sem detalhe").strip()[:200]


def _expira_em(dados: dict) -> datetime:
    """Quando o token expira, a partir do `expires_in` (segundos) da resposta.
    Sem `expires_in`, assume 60 dias (validade dos tokens de longa duração)."""
    segundos = int(dados.get("expires_in") or VALIDADE_PADRAO_S)
    return datetime.now(timezone.utc) + timedelta(seconds=segundos)


def _tratar_falha(resposta: httpx.Response) -> None:
    """Política de falha do encaixe: 400/401/403 = não-retentável (token recusado);
    429/5xx = retentável (oscilação); demais 4xx = não-retentável."""
    status = resposta.status_code
    if status in (400, 401, 403):
        raise FalhaInstrumento(
            f"o Instagram recusou o token (HTTP {status}): {_detalhe_erro(resposta)}",
            retentavel=False,
        )
    if status == 429 or 500 <= status < 600:
        raise FalhaInstrumento(f"o Instagram respondeu HTTP {status}.", retentavel=True)
    if not resposta.is_success:
        raise FalhaInstrumento(
            f"a chamada ao Instagram falhou (HTTP {status}): {_detalhe_erro(resposta)}",
            retentavel=False,
        )


def validar(token: str) -> dict:
    """Valida o token e descobre o ID da conta (GET /me?fields=user_id,username).

    Devolve `{ig_user_id, username}`. Levanta `FalhaInstrumento` se o Instagram
    recusar o token (não-retentável) ou se a rede oscilar (retentável)."""
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            resposta = cliente.get(
                f"{GRAPH}/me",
                params={"fields": "user_id,username", "access_token": token},
            )
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível falar com o Instagram: {e}", retentavel=True
        )
    _tratar_falha(resposta)
    dados = resposta.json()
    return {
        "ig_user_id": str(dados.get("user_id") or dados.get("id") or ""),
        "username": dados.get("username") or "",
    }


def renovar(token: str) -> dict:
    """Renova um token de longa duração (GET /refresh_access_token,
    grant_type=ig_refresh_token) — sem app secret. O token deve ter ≥24h e <60
    dias de vida (regra da Meta). Devolve `{token, expira_em}`."""
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            resposta = cliente.get(
                f"{GRAPH}/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": token},
            )
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível renovar o token do Instagram: {e}", retentavel=True
        )
    _tratar_falha(resposta)
    dados = resposta.json()
    novo = dados.get("access_token")
    if not novo:
        raise FalhaInstrumento(
            "o Instagram não devolveu um token novo na renovação.", retentavel=False
        )
    return {"token": novo, "expira_em": _expira_em(dados)}
