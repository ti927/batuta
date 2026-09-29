"""OAuth do instrumento MCP: entrar com a conta (código + PKCE) e OAuth entre sistemas
(client credentials) — Fase 2 de 2026-09-29.

Segue a especificação de autorização do MCP:
1. **Descoberta**: o servidor MCP responde 401 com `WWW-Authenticate:
   resource_metadata=...` (RFC 9728). Esse documento aponta o servidor de
   autorização, cujos metadados (RFC 8414 ou OpenID) trazem os endereços.
2. **Registro do cliente**, nesta ordem:
   - client_id informado à mão, se houver;
   - CIMD, quando o servidor anuncia `client_id_metadata_document_supported`: o
     client_id É a URL pública do documento do Batuta (`/mcp/oauth/cliente.json`),
     que precisa ser HTTPS — em ambiente local cai para o registro dinâmico;
   - registro dinâmico (RFC 7591) no `registration_endpoint`.
3. **Login** com PKCE (S256) e o parâmetro `resource` (RFC 8707). O `code_verifier`
   viaja DENTRO do `state` cifrado (com prazo): não fica guardado em lugar nenhum.
4. **Renovação** antes de vencer, com TRAVA POR INSTRUMENTO (advisory lock do
   Postgres): duas execuções ao mesmo tempo não renovam juntas. Isso importa porque
   muitos servidores GIRAM o refresh token — quem renovasse em segundo lugar usaria um
   refresh token já morto e derrubaria a conexão.

Onde cada coisa mora:
- tokens e client_secret: no COFRE do instrumento (`oauth_access_token`,
  `oauth_refresh_token`, `oauth_client_secret`);
- o resto (endereço do token, client_id, recurso, vencimento, estado): em
  `instrumentos.conexao["oauth"]` — nunca segredo.

Falha definitiva na renovação (o servidor recusou o refresh token) marca o estado
"precisa_reconectar", registra `mcp.oauth_renovacao_falhou` no banco de logs e faz o
instrumento falhar com `mcp.precisa_conectar` — o diagnóstico da execução diz o que
fazer. Falha passageira (rede, 5xx) não marca nada: segue com o token atual.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from instrumentos.base import FalhaInstrumento

TIMEOUT_S = 20.0
MARGEM_RENOVACAO = timedelta(minutes=5)
VALIDADE_PADRAO_S = 3600
TTL_STATE_S = 600
MODOS_OAUTH = ("oauth_login", "oauth_cliente")

CAMPO_ACCESS = "oauth_access_token"
CAMPO_REFRESH = "oauth_refresh_token"
CAMPO_CLIENT_SECRET = "oauth_client_secret"


# ───────────────────────────── endereços do Batuta ─────────────────────────────

def base_publica() -> str:
    return os.environ.get("CEREBRO_PUBLIC_URL", "http://localhost:8000").rstrip("/")


def redirect_uri() -> str:
    """O endereço FIXO para onde o servidor devolve o navegador depois do login."""
    return f"{base_publica()}/mcp/oauth/callback"


def url_documento_cliente() -> str:
    """O client_id do CIMD: a URL do documento que descreve o Batuta como cliente."""
    return f"{base_publica()}/mcp/oauth/cliente.json"


def documento_cliente() -> dict:
    """O Client ID Metadata Document. O servidor de autorização o BAIXA para saber
    quem é o cliente — por isso precisa estar numa URL HTTPS pública."""
    return {
        "client_id": url_documento_cliente(),
        "client_name": "Batuta",
        "client_uri": os.environ.get("URL_INTERFACE", "https://batuta.team"),
        "redirect_uris": [redirect_uri()],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


# ───────────────────────────── descoberta ─────────────────────────────

@dataclass
class Descoberta:
    recurso: str
    url_autorizacao: str
    url_token: str
    url_registro: str
    aceita_cimd: bool
    metodos_token: list[str]
    escopo: str


def _falha(msg: str, codigo: str, *, retentavel: bool = False) -> FalhaInstrumento:
    return FalhaInstrumento(msg, retentavel=retentavel, codigo=codigo)


def _get_json(cliente: httpx.Client, url: str) -> dict | None:
    try:
        r = cliente.get(url, headers={"Accept": "application/json"})
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        dados = r.json()
    except ValueError:
        return None
    return dados if isinstance(dados, dict) else None


def descobrir(url_mcp: str, cabecalhos: dict[str, str] | None = None) -> Descoberta:
    """Descobre o servidor de autorização de um servidor MCP (sem segredo nenhum)."""
    from mcp.client.auth.utils import (
        build_oauth_authorization_server_metadata_discovery_urls,
        build_protected_resource_metadata_discovery_urls,
        extract_field_from_www_auth,
    )

    with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True) as cliente:
        meta_recurso_url = None
        escopo_401 = None
        try:
            r = cliente.post(
                url_mcp,
                headers={
                    **(cabecalhos or {}),
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                json={
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25", "capabilities": {},
                        "clientInfo": {"name": "Batuta", "version": "1"},
                    },
                },
            )
            if r.status_code == 401:
                meta_recurso_url = extract_field_from_www_auth(r, "resource_metadata")
                escopo_401 = extract_field_from_www_auth(r, "scope")
        except httpx.HTTPError:
            raise _falha(
                "não foi possível alcançar o servidor MCP para descobrir o login — ele "
                "pode estar fora do ar, ou o endereço está errado.",
                "mcp.fora_do_ar", retentavel=True,
            )

        recurso: dict | None = None
        for u in build_protected_resource_metadata_discovery_urls(meta_recurso_url, url_mcp):
            recurso = _get_json(cliente, u)
            if recurso and recurso.get("authorization_servers"):
                break
            recurso = None
        servidor_aut = (recurso or {}).get("authorization_servers", [None])[0]

        meta: dict | None = None
        for u in build_oauth_authorization_server_metadata_discovery_urls(servidor_aut, url_mcp):
            meta = _get_json(cliente, u)
            if meta and meta.get("authorization_endpoint") and meta.get("token_endpoint"):
                break
            meta = None
    if meta is None:
        raise _falha(
            "este servidor não anuncia login por OAuth (não achei os endereços de "
            "autorização). Confira o endereço, ou use outro modo de identificação.",
            "mcp.oauth_sem_descoberta",
        )
    escopo = escopo_401 or " ".join(
        (recurso or {}).get("scopes_supported") or meta.get("scopes_supported") or []
    )
    return Descoberta(
        recurso=str((recurso or {}).get("resource") or url_mcp),
        url_autorizacao=meta["authorization_endpoint"],
        url_token=meta["token_endpoint"],
        url_registro=str(meta.get("registration_endpoint") or ""),
        aceita_cimd=meta.get("client_id_metadata_document_supported") is True,
        metodos_token=list(meta.get("token_endpoint_auth_methods_supported") or []),
        escopo=escopo,
    )


def _registrar_cliente(d: Descoberta) -> tuple[str, str, str, str]:
    """Registro dinâmico (RFC 7591). Devolve (client_id, client_secret, metodo, registro)."""
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            r = cliente.post(d.url_registro, json={
                "client_name": "Batuta",
                "redirect_uris": [redirect_uri()],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                **({"scope": d.escopo} if d.escopo else {}),
            })
    except httpx.HTTPError:
        raise _falha("o servidor de login não respondeu ao registro do Batuta.",
                     "mcp.oauth_registro_falhou", retentavel=True)
    if r.status_code >= 400:
        raise _falha(
            f"o servidor de login recusou o registro automático do Batuta ({r.status_code}). "
            "Informe um Client ID próprio em “Avançado”.",
            "mcp.oauth_registro_falhou",
        )
    dados = r.json()
    return (
        str(dados.get("client_id") or ""),
        str(dados.get("client_secret") or ""),
        str(dados.get("token_endpoint_auth_method") or ("client_secret_post" if dados.get("client_secret") else "none")),
        "dcr",
    )


def _pkce() -> tuple[str, str]:
    verificador = secrets.token_urlsafe(64)[:96]
    desafio = base64.urlsafe_b64encode(
        hashlib.sha256(verificador.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    return verificador, desafio


def _metodo_manual(d: Descoberta, tem_segredo: bool) -> str:
    if not tem_segredo:
        return "none"
    if "client_secret_post" in d.metodos_token or not d.metodos_token:
        return "client_secret_post"
    return "client_secret_basic"


def iniciar_login(inst, config, segredos: dict, usuario_id) -> tuple[str, dict, dict]:
    """Monta o endereço de login. Devolve (url, oauth_para_conexao, segredos_novos).

    Quem chama grava `oauth_para_conexao` em `inst.conexao["oauth"]` e os segredos no
    cofre do instrumento — só depois disso manda o navegador para a URL."""
    import cofre
    from mcp.client.auth.utils import is_valid_client_metadata_url

    from instrumentos import mcp_conexao

    url_mcp = (getattr(config, "url", "") or "").strip()
    if not url_mcp:
        raise _falha("preencha e salve o endereço do servidor antes de conectar.",
                     "mcp.sem_endereco")
    extras = dict(getattr(config, "cabecalhos", None) or {})
    extras.update(mcp_conexao.cabecalhos_secretos(config))
    d = descobrir(url_mcp, extras)
    escopo = (getattr(config, "oauth_escopo", "") or "").strip() or d.escopo

    novos: dict[str, str] = {}
    manual = (getattr(config, "oauth_client_id", "") or "").strip()
    if manual:
        segredo_manual = (getattr(config, "auth_segredo", "") or "").strip()
        client_id, metodo, registro = manual, _metodo_manual(d, bool(segredo_manual)), "manual"
    elif d.aceita_cimd and is_valid_client_metadata_url(url_documento_cliente()):
        client_id, metodo, registro = url_documento_cliente(), "none", "cimd"
    elif d.url_registro:
        client_id, client_secret, metodo, registro = _registrar_cliente(d)
        if client_secret:
            novos[CAMPO_CLIENT_SECRET] = client_secret
    else:
        raise _falha(
            "este servidor não aceita registro automático do Batuta. Informe um Client "
            "ID (e, se o servidor der, o Client Secret) em “Avançado”.",
            "mcp.oauth_sem_registro",
        )

    verificador, desafio = _pkce()
    state = cofre.cifrar(json.dumps({"i": str(inst.id), "u": str(usuario_id), "v": verificador}))
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri(),
        "code_challenge": desafio,
        "code_challenge_method": "S256",
        "state": state,
        "resource": d.recurso,
    }
    if escopo:
        params["scope"] = escopo
    separador = "&" if "?" in d.url_autorizacao else "?"
    oauth = {
        "url_token": d.url_token,
        "client_id": client_id,
        "recurso": d.recurso,
        "escopo": escopo,
        "metodo": metodo,
        "registro": registro,
    }
    return d.url_autorizacao + separador + urlencode(params), oauth, novos


def ler_state(state: str) -> dict:
    import cofre

    try:
        return json.loads(cofre.decifrar_temporario(state, TTL_STATE_S))
    except Exception:  # noqa: BLE001
        raise _falha(
            "o pedido de login expirou ou não é válido. Clique em “Conectar” de novo.",
            "mcp.oauth_state_invalido",
        )


# ───────────────────────────── chamadas ao endpoint de token ─────────────────────

def _pedir_token(oauth: dict, corpo: dict, client_secret: str) -> dict:
    """POST no endpoint de token com o método de autenticação do cliente. Levanta
    FalhaInstrumento com o CÓDIGO OAuth que o servidor deu (nunca com segredo)."""
    corpo = {k: v for k, v in corpo.items() if v}
    auth = None
    metodo = oauth.get("metodo") or "none"
    if metodo == "client_secret_basic" and client_secret:
        auth = (oauth["client_id"], client_secret)
    else:
        corpo["client_id"] = oauth["client_id"]
        if metodo == "client_secret_post" and client_secret:
            corpo["client_secret"] = client_secret
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            r = cliente.post(oauth["url_token"], data=corpo, auth=auth,
                             headers={"Accept": "application/json"})
    except httpx.HTTPError:
        raise _falha("o servidor de login não respondeu.", "mcp.oauth_fora_do_ar",
                     retentavel=True)
    try:
        dados = r.json()
    except ValueError:
        dados = {}
    if r.status_code >= 400 or not isinstance(dados, dict) or not dados.get("access_token"):
        erro = str((dados or {}).get("error") or r.status_code) if isinstance(dados, dict) else str(r.status_code)
        definitivo = r.status_code in (400, 401, 403)
        raise _falha(
            f"o servidor de login recusou o pedido de token ({erro}).",
            "mcp.oauth_recusado" if definitivo else "mcp.oauth_fora_do_ar",
            retentavel=not definitivo,
        )
    return dados


def _vencimento(dados: dict) -> str:
    try:
        segundos = int(dados.get("expires_in") or VALIDADE_PADRAO_S)
    except (TypeError, ValueError):
        segundos = VALIDADE_PADRAO_S
    return (datetime.now(timezone.utc) + timedelta(seconds=segundos)).isoformat()


def trocar_codigo(oauth: dict, codigo: str, verificador: str, client_secret: str) -> tuple[dict, dict]:
    """Troca o código do login por tokens. Devolve (segredos_novos, oauth_atualizado)."""
    dados = _pedir_token(oauth, {
        "grant_type": "authorization_code",
        "code": codigo,
        "redirect_uri": redirect_uri(),
        "code_verifier": verificador,
        "resource": oauth.get("recurso"),
    }, client_secret)
    novos = {CAMPO_ACCESS: dados["access_token"]}
    if dados.get("refresh_token"):
        novos[CAMPO_REFRESH] = dados["refresh_token"]
    agora = datetime.now(timezone.utc).isoformat()
    return novos, {**oauth, "estado": "conectado", "expira_em": _vencimento(dados),
                   "conectado_em": agora, "motivo": None}


# ───────────────────────────── renovação com trava ─────────────────────────────

def _chave_trava(instrumento_id) -> int:
    """Chave do advisory lock: 63 bits do hash do id (o Postgres usa bigint)."""
    h = hashlib.sha256(f"mcp-oauth:{instrumento_id}".encode()).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


def _valido(oauth: dict, token: str) -> bool:
    if not token:
        return False
    bruto = (oauth or {}).get("expira_em") or ""
    try:
        quando = datetime.fromisoformat(bruto)
    except ValueError:
        return False
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    return quando > datetime.now(timezone.utc) + MARGEM_RENOVACAO


def _renovar(modo: str, oauth: dict, segredos: dict) -> tuple[dict, dict]:
    client_secret = segredos.get(CAMPO_CLIENT_SECRET) or segredos.get("auth_segredo") or ""
    if modo == "oauth_login":
        refresh = segredos.get(CAMPO_REFRESH) or ""
        if not refresh:
            raise _falha("a conexão da conta venceu e o servidor não deu como renovar.",
                         "mcp.oauth_recusado")
        dados = _pedir_token(oauth, {
            "grant_type": "refresh_token", "refresh_token": refresh,
            "resource": oauth.get("recurso"),
        }, client_secret)
    else:
        dados = _pedir_token(oauth, {
            "grant_type": "client_credentials", "scope": oauth.get("escopo"),
            "resource": oauth.get("recurso"),
        }, client_secret)
    novos = {CAMPO_ACCESS: dados["access_token"]}
    if dados.get("refresh_token"):  # servidores que GIRAM o refresh token
        novos[CAMPO_REFRESH] = dados["refresh_token"]
    return novos, {**oauth, "estado": "conectado", "expira_em": _vencimento(dados),
                   "motivo": None}


def _oauth_cliente_inicial(inst, config) -> dict:
    """Client credentials: o endereço do token vem da configuração ou é descoberto."""
    url_token = (getattr(config, "oauth_url_token", "") or "").strip()
    recurso = ""
    escopo = (getattr(config, "oauth_escopo", "") or "").strip()
    metodo = "client_secret_post"
    if not url_token:
        d = descobrir((getattr(config, "url", "") or "").strip())
        url_token, recurso, escopo = d.url_token, d.recurso, escopo or d.escopo
        if d.metodos_token and "client_secret_post" not in d.metodos_token:
            metodo = "client_secret_basic"
    return {"url_token": url_token, "client_id": (getattr(config, "oauth_client_id", "") or "").strip(),
            "recurso": recurso, "escopo": escopo, "metodo": metodo, "registro": "manual"}


def garantir_token(
    instrumento_id, modo: str, config, *, conexao: dict | None = None, criar_sessao=None
) -> str:
    """Devolve um access token válido para o instrumento, renovando se preciso.

    A renovação roda sob um advisory lock POR INSTRUMENTO, numa sessão própria: quem
    chega em segundo espera, relê o cofre e usa o token que o primeiro acabou de
    gravar. Nunca levanta: falha definitiva marca "precisa_reconectar" e devolve "";
    falha passageira devolve o token atual."""
    from sqlalchemy import text

    import segredos_instrumento
    from modelos import Instrumento

    # Caminho curto: o token que já veio do cofre ainda vale — nem sessão, nem trava.
    atual_rapido = (getattr(config, "oauth_access_token", "") or "").strip()
    if conexao is not None and _valido((conexao or {}).get("oauth") or {}, atual_rapido):
        return atual_rapido

    if criar_sessao is None:
        from sessao import CriadorDeSessao as criar_sessao

    sessao = criar_sessao()
    try:
        sessao.execute(text("select pg_advisory_xact_lock(:k)"), {"k": _chave_trava(instrumento_id)})
        inst = sessao.get(Instrumento, instrumento_id)
        if inst is None:
            return ""
        sessao.refresh(inst)
        segredos = segredos_instrumento.decifrar(sessao, instrumento_id)
        conexao = dict(inst.conexao or {})
        oauth = dict(conexao.get("oauth") or {})
        atual = segredos.get(CAMPO_ACCESS, "")
        if _valido(oauth, atual):
            return atual
        if modo == "oauth_cliente" and not oauth.get("url_token"):
            oauth = _oauth_cliente_inicial(inst, config)
        if not oauth.get("url_token") or not oauth.get("client_id"):
            return atual  # nunca conectado: o instrumento acusa "precisa conectar"
        try:
            novos, oauth_novo = _renovar(modo, oauth, segredos)
        except FalhaInstrumento as e:
            if e.retentavel:
                _avisar(instrumento_id, inst.nome, e, nivel="warning")
                return atual
            conexao["oauth"] = {**oauth, "estado": "precisa_reconectar",
                                "motivo": str(e)[:200],
                                "desde": datetime.now(timezone.utc).isoformat()}
            inst.conexao = conexao
            sessao.commit()
            _avisar(instrumento_id, inst.nome, e, nivel="error")
            return ""
        segredos_instrumento.salvar_segredos(sessao, instrumento_id, novos)
        conexao["oauth"] = oauth_novo
        inst.conexao = conexao
        sessao.commit()
        return novos[CAMPO_ACCESS]
    except Exception:  # noqa: BLE001 — renovar nunca derruba o cinto inteiro
        sessao.rollback()
        return ""
    finally:
        sessao.close()


def _avisar(instrumento_id, nome: str, erro: FalhaInstrumento, *, nivel: str) -> None:
    try:
        from observabilidade.escritor import registrar_evento

        registrar_evento(
            categoria="instrumento",
            acao="mcp.oauth_renovacao_falhou",
            nivel=nivel,
            resultado="falha",
            erro=erro,
            recurso_tipo="instrumento",
            recurso_id=str(instrumento_id),
            persistir=True,
            detalhe={
                "instrumento": nome,
                "codigo": erro.codigo,
                "o_que_fazer": (
                    "Abra o instrumento e clique em “Conectar” para entrar com a conta "
                    "de novo." if nivel == "error"
                    else "Falha passageira do servidor de login; o Batuta tenta de novo."
                ),
            },
        )
    except Exception:  # noqa: BLE001 — avisar nunca derruba
        pass
