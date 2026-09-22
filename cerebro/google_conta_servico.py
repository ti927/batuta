"""Conta de serviço do Google — a autenticação que NÃO passa por consentimento.

Existe por causa de uma noite inteira gasta em 2026-09-21. O Search Console do blog
ficou dois meses em HTTP 401 porque a conta Google conectada por OAuth parou de
renovar. Consertar a conta é um minuto; o que não é minuto é o resto: para publicar o
app OAuth do Batuta, o Google exige verificação completa (os escopos de Gmail e Drive
são *restritos*, com auditoria de segurança anual), e enquanto o app fica em *Testing*
o token de renovação morre a cada 7 dias.

A **conta de serviço** pula tudo isso. Ela é uma identidade da máquina, não de uma
pessoa: não tem tela de consentimento, não depende de app verificado, não expira em 7
dias. Você cria a conta no Google Cloud, baixa a chave em JSON e dá acesso a ela onde
quiser — no Search Console, adicionando o e-mail dela como usuário da propriedade.

**Por que isto precisa ser código, e não um campo de formulário.** O token não vem de
"mandar a chave e receber de volta": é preciso ASSINAR uma afirmação (JWT, RS256) com a
chave privada e trocá-la por um token de acesso. Isso é criptografia — nenhuma tela
expressa "assine esta afirmação com esta chave". É a única parte do caminho que o
Construtor de Instrumentos não poderia montar sozinho; feita aqui, ele monta o resto
(qualquer API do Google) sem código nenhum.

O token dura ~1h e é guardado em memória enquanto vale — um par de chamadas seguidas
não vai assinar duas vezes.
"""

import hashlib
import json
import threading
import time

from instrumentos.base import FalhaInstrumento

# Escopo usado quando o instrumento não declara nenhum. `cloud-platform` seria cômodo
# e é exatamente o que não se deve fazer: ele dá acesso amplo. Sem escopo declarado,
# recusamos — quem monta o instrumento diz o que precisa.
FOLGA_SEGUNDOS = 120  # renova um pouco antes de vencer, não em cima da hora

_CACHE: dict[str, tuple[float, str]] = {}
_TRAVA = threading.Lock()


def _chave_cache(info_json: str, escopos: tuple[str, ...]) -> str:
    """Identidade em HASH — a chave privada nunca vira chave de dicionário."""
    cru = f"{info_json}|{','.join(escopos)}"
    return hashlib.sha256(cru.encode("utf-8")).hexdigest()


def _escopos(escopo: str) -> tuple[str, ...]:
    """Os escopos pedidos, separados por espaço ou vírgula."""
    partes = [p.strip() for p in escopo.replace(",", " ").split() if p.strip()]
    return tuple(partes)


def token(chave_json: str, escopo: str) -> str:
    """Um access_token válido para esta conta de serviço e estes escopos.

    Levanta `FalhaInstrumento` com recado humano — quem lê é o consultor na tela do
    instrumento, não um desenvolvedor lendo stack trace."""
    bruto = (chave_json or "").strip()
    if not bruto:
        raise FalhaInstrumento(
            "falta a chave da conta de serviço do Google. Baixe o arquivo JSON no "
            "Google Cloud (Contas de serviço → Chaves → Criar chave → JSON) e cole o "
            "conteúdo dele no campo do segredo.",
            retentavel=False,
        )
    escopos = _escopos(escopo)
    if not escopos:
        raise FalhaInstrumento(
            "falta dizer QUAL permissão esta conexão usa (o escopo). Para o Search "
            "Console é https://www.googleapis.com/auth/webmasters.readonly. Pedir "
            "acesso amplo seria pior: a conta de serviço só deve poder o que você usa.",
            retentavel=False,
        )

    chave = _chave_cache(bruto, escopos)
    agora = time.monotonic()
    with _TRAVA:
        guardado = _CACHE.get(chave)
        if guardado and guardado[0] > agora:
            return guardado[1]

    try:
        info = json.loads(bruto)
    except ValueError:
        raise FalhaInstrumento(
            "a chave da conta de serviço não é um JSON válido. Cole o conteúdo do "
            "arquivo inteiro, do '{' ao '}'.",
            retentavel=False,
        ) from None
    if info.get("type") != "service_account":
        raise FalhaInstrumento(
            "esse JSON não é de uma conta de serviço (falta \"type\": "
            "\"service_account\"). Baixe a chave em Contas de serviço → Chaves, não "
            "as credenciais de OAuth.",
            retentavel=False,
        )

    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        credencial = service_account.Credentials.from_service_account_info(
            info, scopes=list(escopos)
        )
        credencial.refresh(Request())
    except FalhaInstrumento:
        raise
    except Exception as e:  # chave inválida, relógio fora, rede
        raise FalhaInstrumento(
            f"o Google recusou a chave desta conta de serviço: {e}. Confira se a chave "
            "não foi apagada no Google Cloud e se a conta de serviço tem acesso ao "
            "recurso (no Search Console, o e-mail dela precisa ser usuário da "
            "propriedade).",
            retentavel=True,
        ) from None

    if not credencial.token:
        raise FalhaInstrumento(
            "o Google não devolveu token para esta conta de serviço.", retentavel=True
        )
    # A validade real do token; sem ela, guardamos por pouco tempo e renovamos cedo.
    vence = getattr(credencial, "expiry", None)
    if vence is not None:
        from datetime import datetime, timezone

        restante = (
            vence.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
        ).total_seconds()
    else:
        restante = 600.0
    with _TRAVA:
        _CACHE[chave] = (agora + max(0.0, restante - FOLGA_SEGUNDOS), credencial.token)
    return credencial.token


def email_da_chave(chave_json: str) -> str:
    """O e-mail da conta de serviço, para a tela dizer QUEM precisa ser autorizado no
    Search Console. Vazio se a chave não presta — quem valida é o `token`."""
    try:
        return str(json.loads(chave_json or "{}").get("client_email") or "")
    except ValueError:
        return ""
