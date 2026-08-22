"""Token de acesso OAuth obtido COM o certificado de cliente (mTLS) — Fatia C da
fundação bancária.

Por que existe
--------------
Guardar o certificado (Fatia A) e apresentá-lo na conexão (Fatia B) não fecha uma
integração bancária. Inter, Itaú e afins exigem **duas** coisas: o certificado no
aperto de mão TLS **e** um `access_token` no cabeçalho — token que se obtém no
endpoint do banco, apresentando o mesmo certificado, e que dura pouco (~1 hora).

O agente não tem como fazer isso sozinho: os cabeçalhos de um instrumento são
configuração fixa, então um token obtido numa chamada não teria como viajar até a
chamada seguinte. Quem resolve é a BORDA — aqui —, exatamente como já se faz com
o Google (`google_oauth.garantir_token`): na hora de montar o cinto do agente, o
token é conferido e, se estiver vencendo, renovado e persistido. O instrumento
sempre recebe um token fresco e não sabe de nada disso.

Formato da requisição
---------------------
`grant_type=client_credentials` em formulário (`application/x-www-form-urlencoded`),
com `client_id`, `client_secret` e, se houver, `scope` — que é o formato dos bancos
brasileiros (Inter, Itaú). Servidores que exigem as credenciais em HTTP Basic em
vez do corpo não estão cobertos nesta fatia; seria um acréscimo pequeno.
"""

import json
from datetime import datetime, timedelta, timezone

import httpx

import certificados
from instrumentos.base import FalhaInstrumento

TIMEOUT_S = 20.0
# Renova antes de vencer de fato: um token que expira no meio de uma execução
# custaria um 401 sem motivo. Mesma ideia da margem do Google.
MARGEM_RENOVACAO = timedelta(minutes=5)
# Se o banco não disser quanto dura, assume curto — melhor renovar à toa do que
# usar um token morto.
VALIDADE_PADRAO_S = 3600


def obter_token(
    *,
    url_token: str,
    client_id: str,
    client_secret: str,
    escopo: str = "",
    certificado: str = "",
    chave_privada: str = "",
) -> tuple[str, datetime]:
    """Troca client_id/client_secret por um `access_token`, apresentando o
    certificado. Devolve `(token, expira_em)` — o vencimento já em UTC.

    Levanta `FalhaInstrumento` com mensagem humana (Lei §12-A): quem chama decide
    se derruba a execução ou segue com o token velho."""
    corpo = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if escopo.strip():
        corpo["scope"] = escopo.strip()

    try:
        with certificados.material_mtls(certificado, chave_privada) as par:
            with httpx.Client(timeout=TIMEOUT_S, cert=par) as cliente:
                resposta = cliente.post(url_token, data=corpo)
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não consegui falar com o servidor de token em {url_token}: {e}",
            retentavel=True,
        )

    if resposta.status_code >= 400:
        raise FalhaInstrumento(
            f"o servidor de token recusou as credenciais (HTTP "
            f"{resposta.status_code}) — confira client_id, client_secret, escopo e "
            "se o certificado é o da mesma conta.",
            retentavel=False,
        )

    try:
        dados = resposta.json()
    except (ValueError, json.JSONDecodeError):
        raise FalhaInstrumento(
            "o servidor de token respondeu algo que não é JSON — confira se a URL "
            "do token está certa.",
            retentavel=False,
        )

    token = str(dados.get("access_token") or "")
    if not token:
        raise FalhaInstrumento(
            "o servidor de token respondeu sem `access_token`.", retentavel=False
        )
    try:
        segundos = int(dados.get("expires_in") or VALIDADE_PADRAO_S)
    except (TypeError, ValueError):
        segundos = VALIDADE_PADRAO_S
    return token, datetime.now(timezone.utc) + timedelta(seconds=segundos)


def _vencimento(dados: dict) -> datetime | None:
    """Lê o vencimento do token guardado no saco (ISO 8601). Formato estranho ou
    ausente = tratar como vencido (renova)."""
    bruto = (dados.get("token_expira_em") or "").strip()
    if not bruto:
        return None
    try:
        quando = datetime.fromisoformat(bruto)
    except ValueError:
        return None
    return quando if quando.tzinfo else quando.replace(tzinfo=timezone.utc)


def garantir_token(credencial) -> str:
    """Devolve um `access_token` válido da credencial `certificado_mtls`,
    renovando sob demanda. Chamado pela borda ao resolver as credenciais.

    Credencial sem OAuth configurado (sem `url_token`/`client_id`) devolve `""` —
    a conexão usa só o certificado, que é um cenário legítimo.

    **Nunca levanta**: numa falha de renovação devolve o token atual (o
    instrumento trata o 401 com recado claro), para não derrubar o carregamento do
    cinto inteiro por causa de uma credencial."""
    import credenciais_cofre

    dados = credenciais_cofre.decifrar(credencial)
    if not (dados.get("url_token") or "").strip():
        return ""
    if not (dados.get("client_id") or "").strip():
        return ""

    atual = dados.get("access_token", "")
    vence = _vencimento(dados)
    if atual and vence and vence > datetime.now(timezone.utc) + MARGEM_RENOVACAO:
        return atual

    try:
        token, expira = obter_token(
            url_token=dados["url_token"],
            client_id=dados["client_id"],
            client_secret=dados.get("client_secret", ""),
            escopo=dados.get("escopo", ""),
            certificado=dados.get("certificado", ""),
            chave_privada=dados.get("chave_privada", ""),
        )
    except FalhaInstrumento:
        return atual

    _persistir_token(credencial.id, token, expira)
    return token


def _persistir_token(credencial_id, token: str, expira_em: datetime) -> None:
    """Guarda o token renovado numa sessão própria e curta — não toca a transação
    da execução. Best-effort: falhar aqui só significa não cachear (o token recém
    obtido já vai ser usado nesta execução).

    NÃO mexe em `Credencial.expira_em`: aquele campo é o vencimento do
    CERTIFICADO (~1 ano). O do token vive no saco, em `token_expira_em`."""
    import credenciais_cofre
    from modelos import Credencial
    from sessao import CriadorDeSessao

    sessao = CriadorDeSessao()
    try:
        cred = sessao.get(Credencial, credencial_id)
        if cred is not None:
            credenciais_cofre.gravar(
                cred,
                {
                    "access_token": token,
                    "token_expira_em": expira_em.astimezone(timezone.utc).isoformat(),
                },
            )
            sessao.commit()
    except Exception:  # noqa: BLE001 — cache é conveniência, nunca derruba a execução
        sessao.rollback()
    finally:
        sessao.close()
