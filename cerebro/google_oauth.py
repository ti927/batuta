"""OAuth do Google — conectar uma conta Google (Gmail/Agenda/Drive/Search Console)
SEM colar token, com refresh automático.

Espelha o `instagram_oauth.py`, mas para o Google, cuja autorização é diferente em
um ponto central: o `access_token` dura ~1h e o que PERSISTE é o `refresh_token`.
Por isso, além de `conectar` (troca o code por tokens), há `renovar` (troca o
refresh_token por um access_token novo) e `garantir_token` (usado pela BORDA na
execução: devolve um access_token válido, renovando sob demanda).

Fluxo (Google OAuth 2.0, "Authorization Code"):
  1. navegador → https://accounts.google.com/o/oauth2/v2/auth  (consentimento),
     com `access_type=offline` + `prompt=consent` para VIR o refresh_token.
  2. callback recebe `code` → POST https://oauth2.googleapis.com/token
     (grant_type=authorization_code) → {access_token (~1h), refresh_token, expires_in}.
  3. descobre o `email` da conta em https://www.googleapis.com/oauth2/v3/userinfo.
  4. depois, sob demanda: POST .../token (grant_type=refresh_token) → access_token novo.

Config (variáveis de ambiente do cérebro, nunca na interface):
  GOOGLE_CLIENT_ID       — o "Client ID" do OAuth (Google Cloud → Credenciais).
  GOOGLE_CLIENT_SECRET   — o "Client secret".
  GOOGLE_REDIRECT_URI    — o endereço de retorno, idêntico ao cadastrado no console
                           (ex.: https://api.batuta.team/google/oauth/callback).
"""

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from instrumentos.base import FalhaInstrumento

AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"
TIMEOUT_S = 20.0

# Renova o access_token quando falta menos que isto para expirar (folga sobre o ~1h).
MARGEM_RENOVACAO = timedelta(minutes=5)
# Validade assumida quando a resposta não traz `expires_in` (o Google costuma mandar 3600).
VALIDADE_PADRAO_S = 3600

# ── Escopos por serviço (os MAIS ESTREITOS — nível "sensível", evitando "restrito").
# Adicionar um serviço = uma entrada aqui. `openid`+`email` sempre (descobrir a conta).
ESCOPOS_IDENTIDADE = ("openid", "https://www.googleapis.com/auth/userinfo.email")
ESCOPOS_POR_SERVICO: dict[str, tuple[str, ...]] = {
    "search_console": ("https://www.googleapis.com/auth/webmasters.readonly",),
    "gmail": (
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ),
    "agenda": (
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ),
    "drive": (
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file",
    ),
}


def escopos_padrao() -> list[str]:
    """A união dos escopos de todos os serviços do primeiro lote (+ identidade). É o
    que se pede na conexão — conectar o Google uma vez cobre os serviços habilitados.
    Sem repetir, ordem estável (identidade primeiro)."""
    vistos: list[str] = list(ESCOPOS_IDENTIDADE)
    for escopos in ESCOPOS_POR_SERVICO.values():
        for e in escopos:
            if e not in vistos:
                vistos.append(e)
    return vistos


def _config() -> tuple[str, str, str]:
    """(client_id, client_secret, redirect_uri) do ambiente — vazios se não configurado."""
    return (
        os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
        os.environ.get("GOOGLE_REDIRECT_URI", "").strip(),
    )


def configurado() -> bool:
    """True quando as três variáveis estão presentes (sem elas, a rota responde 503
    claro em vez de redirecionar quebrado)."""
    return all(_config())


def montar_url_autorizacao(state: str, escopos: list[str] | None = None) -> str:
    """A URL de consentimento do Google, com o `state` opaco (cifrado pelo cofre).

    `access_type=offline` + `prompt=consent` garantem que o Google devolva o
    `refresh_token` (sem isso, só o access_token de ~1h vem, e não dá para renovar).
    `include_granted_scopes=true` permite consentimento incremental (somar escopos
    numa reconexão sem perder os antigos)."""
    client_id, _, redirect = _config()
    consulta = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": " ".join(escopos or escopos_padrao()),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
    )
    return f"{AUTORIZAR}?{consulta}"


def _detalhe_erro(resposta: httpx.Response) -> str:
    """O motivo que o Google devolveu (`error`/`error_description`), para a mensagem
    ser útil em vez de só 'HTTP 400'."""
    try:
        dados = resposta.json()
        if isinstance(dados, dict):
            motivo = dados.get("error_description") or dados.get("error")
            return str(motivo or dados)[:200]
    except Exception:
        pass
    return (resposta.text or "sem detalhe").strip()[:200]


def _tratar_falha(resposta: httpx.Response) -> None:
    """Política de falha do encaixe: 400/401/403 = não-retentável (recusa);
    429/5xx = retentável (oscilação); demais 4xx = não-retentável."""
    status = resposta.status_code
    if status in (400, 401, 403):
        raise FalhaInstrumento(
            f"o Google recusou a autorização (HTTP {status}): {_detalhe_erro(resposta)}",
            retentavel=False,
        )
    if status == 429 or 500 <= status < 600:
        raise FalhaInstrumento(f"o Google respondeu HTTP {status}.", retentavel=True)
    if not resposta.is_success:
        raise FalhaInstrumento(
            f"a chamada ao Google falhou (HTTP {status}): {_detalhe_erro(resposta)}",
            retentavel=False,
        )


def _expira_em(dados: dict) -> datetime:
    segundos = int(dados.get("expires_in") or VALIDADE_PADRAO_S)
    return datetime.now(timezone.utc) + timedelta(seconds=segundos)


def conectar(code: str) -> dict:
    """Troca o `code` do retorno por access_token + refresh_token e descobre o email.

    Devolve `{access_token, refresh_token, email, escopos, expira_em}`. Levanta
    `FalhaInstrumento` se o Google recusar (não-retentável) ou a rede oscilar."""
    client_id, client_secret, redirect = _config()

    # 1. code → tokens. O refresh_token só vem com access_type=offline + prompt=consent.
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            resposta = cliente.post(
                TOKEN,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect,
                    "code": code,
                },
            )
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível falar com o Google: {e}", retentavel=True
        )
    _tratar_falha(resposta)
    dados = resposta.json()
    access = dados.get("access_token")
    refresh = dados.get("refresh_token")
    if not access:
        raise FalhaInstrumento(
            "o Google não devolveu o token de acesso.", retentavel=False
        )
    if not refresh:
        # Sem refresh_token não há como renovar (o access_token vence em ~1h). Isso
        # acontece quando a conta já tinha um consentimento e o prompt não foi de
        # consentimento — por isso sempre mandamos prompt=consent.
        raise FalhaInstrumento(
            "o Google não devolveu o token de renovação (refresh token). Remova o "
            "acesso do Batuta na conta Google e conecte de novo.",
            retentavel=False,
        )
    escopos = dados.get("scope") or " ".join(escopos_padrao())
    return {
        "access_token": access,
        "refresh_token": refresh,
        "email": _descobrir_email(access),
        "escopos": escopos,
        "expira_em": _expira_em(dados),
    }


def _descobrir_email(access_token: str) -> str:
    """O email da conta conectada (GET userinfo com o access_token). Best-effort: se
    falhar, devolve vazio — a conexão não depende disso para funcionar."""
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            resposta = cliente.get(
                USERINFO, headers={"Authorization": f"Bearer {access_token}"}
            )
        if resposta.is_success:
            return str((resposta.json() or {}).get("email") or "")
    except httpx.HTTPError:
        pass
    return ""


def renovar(refresh_token: str) -> dict:
    """Troca o refresh_token por um access_token novo (grant_type=refresh_token). O
    refresh_token não muda. Devolve `{access_token, expira_em}`."""
    client_id, client_secret, _ = _config()
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            resposta = cliente.post(
                TOKEN,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível renovar o token do Google: {e}", retentavel=True
        )
    _tratar_falha(resposta)
    dados = resposta.json()
    novo = dados.get("access_token")
    if not novo:
        raise FalhaInstrumento(
            "o Google não devolveu um token novo na renovação.", retentavel=False
        )
    return {"access_token": novo, "expira_em": _expira_em(dados)}


def garantir_token(credencial) -> str:
    """Devolve um access_token VÁLIDO da credencial `google`, renovando sob demanda.

    Chamado pela BORDA na resolução de credenciais (a execução sempre recebe um token
    fresco). Se o token guardado ainda tem folga, devolve-o; senão, usa o
    refresh_token para obter um novo e o PERSISTE numa sessão própria (durável,
    independente da transação da execução — como faz o job de refresh do Instagram).

    Nunca levanta: numa falha de renovação, devolve o token atual (o instrumento
    trata o 401 com recado claro), para não derrubar o carregamento do cinto."""
    import credenciais_cofre

    dados = credenciais_cofre.decifrar(credencial)
    access = dados.get("access_token", "")
    expira = credencial.expira_em
    agora = datetime.now(timezone.utc)
    if access and expira and expira > agora + MARGEM_RENOVACAO:
        return access
    refresh = dados.get("refresh_token", "")
    if not refresh:
        return access
    try:
        res = renovar(refresh)
    except FalhaInstrumento:
        return access
    _persistir_token(credencial.id, res["access_token"], res["expira_em"])
    return res["access_token"]


def _persistir_token(credencial_id, access_token: str, expira_em: datetime) -> None:
    """Grava o access_token renovado numa sessão própria (curta), por id — não toca a
    transação da execução. Best-effort: uma falha de escrita não impede o uso do token
    recém-obtido nesta execução (só não fica cacheado)."""
    import credenciais_cofre
    from modelos import Credencial
    from sessao import CriadorDeSessao

    sessao = CriadorDeSessao()
    try:
        cred = sessao.get(Credencial, credencial_id)
        if cred is not None:
            credenciais_cofre.gravar(cred, {"access_token": access_token})
            cred.expira_em = expira_em
            sessao.commit()
    except Exception:
        sessao.rollback()
    finally:
        sessao.close()
