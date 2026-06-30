"""OAuth "Business Login for Instagram" — conectar uma conta SEM colar token.

Complementa o `instagram_tokens.py` (que valida/renova um token já obtido). Aqui
vive o fluxo de autorização: montar a URL de consentimento da Meta e trocar o
`code` de retorno por um token de LONGA duração (60 dias). Mesmo padrão
httpx/`FalhaInstrumento` dos instrumentos.

Fluxo (Instagram API with Instagram Login):
  1. navegador → https://www.instagram.com/oauth/authorize  (tela de consentimento)
  2. callback recebe `code` → POST https://api.instagram.com/oauth/access_token
     (code → token CURTO, ~1h). Exige `client_secret` → só no servidor.
  3. GET https://graph.instagram.com/access_token?grant_type=ig_exchange_token
     (token curto → token LONGO, ~60 dias).
  4. descobre `ig_user_id`/`username` via `instagram_tokens.validar` (/me).
O agendador (`instagram_tokens.renovar`) estica a validade antes dos 60 dias.

Config (variáveis de ambiente do cérebro, nunca na interface):
  INSTAGRAM_APP_ID       — o "ID do app do Instagram" (painel da Meta →
                           Configuração da API com login do Instagram). É o
                           `client_id` do OAuth (≠ App ID da Meta).
  INSTAGRAM_APP_SECRET   — a "Chave secreta do app do Instagram".
  INSTAGRAM_REDIRECT_URI — o endereço de retorno, idêntico ao cadastrado no
                           painel (ex.: https://api.batuta.team/instagram/oauth/callback).
"""

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

import instagram_tokens
from instrumentos.base import FalhaInstrumento

AUTORIZAR = "https://www.instagram.com/oauth/authorize"
TOKEN_CURTO = "https://api.instagram.com/oauth/access_token"
TOKEN_LONGO = "https://graph.instagram.com/access_token"
TIMEOUT_S = 20.0

# As 4 permissões que o Batuta usa (sem DM/mensagens). Vão no `scope` do
# consentimento — bate com o que foi enviado ao App Review da Meta.
ESCOPOS = (
    "instagram_business_basic",
    "instagram_business_content_publish",
    "instagram_business_manage_comments",
    "instagram_business_manage_insights",
)


def _config() -> tuple[str, str, str]:
    """(app_id, app_secret, redirect_uri) do ambiente — vazios se não configurado."""
    return (
        os.environ.get("INSTAGRAM_APP_ID", "").strip(),
        os.environ.get("INSTAGRAM_APP_SECRET", "").strip(),
        os.environ.get("INSTAGRAM_REDIRECT_URI", "").strip(),
    )


def configurado() -> bool:
    """True quando as três variáveis estão presentes (sem elas, não há como
    iniciar o fluxo — a rota responde 503 claro em vez de redirecionar quebrado)."""
    return all(_config())


def montar_url_autorizacao(state: str) -> str:
    """A URL de consentimento da Meta, com o `state` opaco (assinado pelo cofre)
    para o callback reconhecer de qual organização/usuário é o pedido."""
    app_id, _, redirect = _config()
    consulta = urlencode(
        {
            "client_id": app_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": ",".join(ESCOPOS),
            "state": state,
        }
    )
    return f"{AUTORIZAR}?{consulta}"


def conectar(code: str) -> dict:
    """Troca o `code` do retorno pelo token de 60 dias e descobre a identidade.

    Devolve `{token, ig_user_id, username, expira_em}`. Levanta `FalhaInstrumento`
    se a Meta recusar (não-retentável) ou a rede oscilar (retentável). A política
    de falha (4xx vs 5xx) é a mesma do `instagram_tokens` — fonte única."""
    app_id, app_secret, redirect = _config()

    # 1. code → token curto (~1h). client_secret só no servidor (nunca no navegador).
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            resposta = cliente.post(
                TOKEN_CURTO,
                data={
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect,
                    "code": code,
                },
            )
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível falar com o Instagram: {e}", retentavel=True
        )
    instagram_tokens._tratar_falha(resposta)
    token_curto = resposta.json().get("access_token")
    if not token_curto:
        raise FalhaInstrumento(
            "o Instagram não devolveu o token na troca do código.", retentavel=False
        )

    # 2. token curto → token longo (~60 dias).
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            resposta = cliente.get(
                TOKEN_LONGO,
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": app_secret,
                    "access_token": token_curto,
                },
            )
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível obter o token de longa duração: {e}", retentavel=True
        )
    instagram_tokens._tratar_falha(resposta)
    dados = resposta.json()
    token_longo = dados.get("access_token")
    if not token_longo:
        raise FalhaInstrumento(
            "o Instagram não devolveu o token de longa duração.", retentavel=False
        )
    segundos = int(dados.get("expires_in") or instagram_tokens.VALIDADE_PADRAO_S)
    expira_em = datetime.now(timezone.utc) + timedelta(seconds=segundos)

    # 3. identidade da conta (reusa /me do instagram_tokens).
    info = instagram_tokens.validar(token_longo)
    return {
        "token": token_longo,
        "ig_user_id": info["ig_user_id"],
        "username": info["username"],
        "expira_em": expira_em,
    }
