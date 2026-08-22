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


def garantir_material(material: dict, guardar) -> str:
    """O NÚCLEO: dado o material de uma conexão, devolve um `access_token` válido,
    renovando sob demanda. Uma fonte só para os dois caminhos que existem hoje —
    a credencial da caixa-forte e o instrumento que traz o OAuth em si mesmo.

    `material` usa as chaves canônicas `url_token`, `client_id`, `client_secret`,
    `escopo`, `certificado`, `chave_privada`, `access_token`, `token_expira_em`
    (quem chama traduz os nomes de casa para estes). `guardar(token, expira)`
    persiste o token renovado onde ele mora.

    Sem OAuth configurado (sem `url_token`/`client_id`) devolve `""` — a conexão
    usa só o certificado, ou nenhuma autenticação: cenários legítimos.

    **Nunca levanta**: numa falha de renovação devolve o token atual (o
    instrumento trata o 401 com recado claro), para não derrubar o carregamento do
    cinto inteiro por causa de uma conexão."""
    if not (material.get("url_token") or "").strip():
        return ""
    if not (material.get("client_id") or "").strip():
        return ""

    atual = material.get("access_token", "")
    vence = _vencimento(material)
    if atual and vence and vence > datetime.now(timezone.utc) + MARGEM_RENOVACAO:
        return atual

    try:
        token, expira = obter_token(
            url_token=material["url_token"],
            client_id=material["client_id"],
            client_secret=material.get("client_secret", ""),
            escopo=material.get("escopo", ""),
            certificado=material.get("certificado", ""),
            chave_privada=material.get("chave_privada", ""),
        )
    except FalhaInstrumento:
        return atual

    guardar(token, expira)
    return token


def garantir_token(credencial) -> str:
    """Token de uma credencial `certificado_mtls` da caixa-forte."""
    import credenciais_cofre

    dados = credenciais_cofre.decifrar(credencial)
    return garantir_material(
        dados, lambda token, expira: _persistir_token(credencial.id, token, expira)
    )


def garantir_token_instrumento(instrumento_id, config: dict, segredos: dict) -> str:
    """Token de um instrumento que traz o OAuth EM SI MESMO (montado no
    Construtor, sem passar pela caixa-forte).

    Traduz os nomes de casa do conector para as chaves canônicas: `auth_usuario`
    é o Client ID e `auth_segredo` é o Client Secret — o mesmo par que serve o
    Basic, para o Construtor ter um campo só de cada."""
    material = {
        "url_token": config.get("url_token", ""),
        "escopo": config.get("escopo", ""),
        "client_id": config.get("auth_usuario", ""),
        "client_secret": segredos.get("auth_segredo", ""),
        "certificado": segredos.get("certificado", ""),
        "chave_privada": segredos.get("chave_privada", ""),
        "access_token": segredos.get("access_token", ""),
        "token_expira_em": segredos.get("token_expira_em", ""),
    }
    return garantir_material(
        material,
        lambda token, expira: _persistir_no_instrumento(instrumento_id, token, expira),
    )


def _persistir_no_instrumento(instrumento_id, token: str, expira_em: datetime) -> None:
    """Guarda o token do instrumento no cofre dele (upsert campo a campo — não
    encosta no certificado nem no segredo da autenticação). Sessão própria e
    curta, best-effort: falhar aqui só significa não cachear."""
    import segredos_instrumento
    from sessao import CriadorDeSessao

    sessao = CriadorDeSessao()
    try:
        segredos_instrumento.salvar_segredos(
            sessao,
            instrumento_id,
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
