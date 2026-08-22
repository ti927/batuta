"""Cofre da caixa-forte de credenciais (Passo 3 da FASE Caixa-forte).

Cifra o SACO inteiro de uma credencial nomeada (ex.: {usuario, senha_app}) num
único blob JSON (`Credencial.dados_cifrado`), reusando a criptografia do
`cofre.py` (a mesma chave-mestra do cofre 7-B). Mantém um `resumo` em claro
(JSONB) para a interface exibir SEM decifrar: campo de identidade aparece pleno;
campo secreto, só os últimos 4 — o valor pleno de um segredo NUNCA volta à
interface (PRODUTO §26).

A decifragem só acontece em memória, na execução (Passo 4). Aqui não há rota nem
checagem de acesso — isso é do Passo 5; este módulo é só a camada de cofre."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import cofre
import tipos_credencial as tc
from modelos import Credencial, Instrumento

# Validade assumida para o token de longa duração do Instagram recém-colado (o
# painel não devolve `expires_in` no momento da colagem). O agendador corrige a
# data com o `expires_in` real no primeiro refresh.
_VALIDADE_IG_S = 60 * 24 * 3600


def montar_resumo(tipo: str, dados: dict) -> dict:
    """Resumo para exibição (não guarda segredo em claro). Para cada campo do
    tipo: identidade → `{secreto: False, valor: <pleno>}`; secreto →
    `{secreto: True, ultimos4: <4 últimos>}`. Campo não declarado é ignorado."""
    tcred = tc.obter_tipo(tipo)
    resumo: dict = {}
    for campo in (tcred.campos if tcred else ()):
        valor = str(dados.get(campo.nome, "") or "")
        if campo.secreto:
            resumo[campo.nome] = {
                "secreto": True,
                "ultimos4": cofre.ultimos4(valor) if valor else "",
            }
        else:
            resumo[campo.nome] = {"secreto": False, "valor": valor}
    return resumo


def gravar(credencial: Credencial, dados: dict) -> None:
    """Cifra o saco em `credencial.dados_cifrado` e atualiza o `resumo`.

    Só considera os campos declarados pelo tipo (`credencial.tipo`). Um campo em
    branco PRESERVA o valor atual (padrão de campo de senha): a base é o saco
    decifrado atual (vazio na criação). Sobre o instance — quem persiste é a rota."""
    tcred = tc.obter_tipo(credencial.tipo)
    nomes = tcred.nomes_campos if tcred else ()
    base = decifrar(credencial) if credencial.dados_cifrado else {}
    for campo in nomes:
        novo = str(dados.get(campo, "") or "")
        if novo.strip():
            base[campo] = novo
    # Descarta qualquer chave que não pertença mais ao tipo.
    base = {k: v for k, v in base.items() if k in nomes}
    credencial.dados_cifrado = cofre.cifrar(json.dumps(base, ensure_ascii=False))
    credencial.resumo = montar_resumo(credencial.tipo, base)


def decifrar(credencial: Credencial) -> dict:
    """Devolve o saco decifrado {campo: valor} — usado só na execução, em
    memória. Vazio se ainda não há nada cifrado."""
    if not credencial.dados_cifrado:
        return {}
    return json.loads(cofre.decifrar(credencial.dados_cifrado))


def gravar_com_validacao_ig(credencial: Credencial, dados: dict) -> None:
    """Como `gravar`, mas trata o tipo `instagram`: valida o token colado no
    Instagram, descobre o `ig_user_id` (preenche sozinho) e fixa `expira_em` ≈ 60
    dias (o token do painel nasce de longa duração; o agendador corrige a data no
    primeiro refresh, com o `expires_in` real). Para os demais tipos, é o `gravar`
    normal. Levanta `FalhaInstrumento` se o token for recusado — a rota traduz em 422.

    Token em branco na EDIÇÃO de uma credencial instagram preserva o token atual
    (igual a campo de senha): não revalida nem mexe em `expira_em`."""
    token = str(dados.get("token", "") or "").strip()
    if credencial.tipo != "instagram" or not token:
        gravar(credencial, dados)
        return
    import instagram_tokens

    info = instagram_tokens.validar(token)
    # `ig_user_id` é DERIVADO (via /me), não colado: sobrescreve o que vier no form.
    gravar(credencial, {**dados, "ig_user_id": info["ig_user_id"]})
    credencial.expira_em = datetime.now(timezone.utc) + timedelta(seconds=_VALIDADE_IG_S)


def gravar_com_certificado(credencial: Credencial, dados: dict) -> None:
    """Grava o tipo `certificado_mtls`: o consultor SOBE um arquivo (.pfx/.p12 ou
    .pem/.crt) — a borda o normaliza para PEM (`certificados.normalizar`), guarda o
    par cifrado e deriva `titular`/`validade` + `expira_em` do próprio certificado.
    A IA nunca recebe o segredo; a senha do arquivo é usada só aqui e não é guardada.

    Campos transitórios no `dados` (não são campos do tipo, não persistem):
    - `arquivo`      — o certificado, em base64 (obrigatório na criação);
    - `chave_arquivo`— uma chave `.key` separada, em base64 (opcional);
    - `senha_certificado` — senha do .pfx/chave (opcional), usada só para abrir.

    `client_id`/`client_secret` seguem a regra de campo secreto: em branco preserva
    o atual. Levanta `certificados.CertificadoInvalido` (a rota traduz em 422)."""
    import certificados

    base = decifrar(credencial) if credencial.dados_cifrado else {}
    arquivo = str(dados.get("arquivo", "") or "").strip()

    if arquivo:
        cert_pem, chave_pem, titular, expira = certificados.normalizar(
            arquivo,
            senha=str(dados.get("senha_certificado", "") or ""),
            chave_b64=str(dados.get("chave_arquivo", "") or ""),
        )
        base["certificado"] = cert_pem
        base["chave_privada"] = chave_pem
        base["titular"] = titular
        base["validade"] = expira.astimezone(timezone.utc).strftime("%d/%m/%Y")
        credencial.expira_em = expira
    elif not base.get("certificado"):
        raise certificados.CertificadoInvalido(
            "envie o arquivo do certificado (.pfx/.p12 ou .pem/.crt)."
        )

    # OAuth do banco (opcional): em branco preserva o atual, como todo campo de
    # segredo. Com `url_token` + `client_id` preenchidos, a borda passa a trocar
    # essas credenciais por um `access_token` (ver `oauth_mtls.garantir_token`).
    for campo in ("client_id", "client_secret", "url_token", "escopo"):
        novo = str(dados.get(campo, "") or "")
        if novo.strip():
            base[campo] = novo

    # Trocar o material do OAuth invalida o token cacheado: o próximo acionamento
    # busca um novo (senão o agente seguiria usando um token da conta antiga).
    if any(str(dados.get(c, "") or "").strip() for c in
           ("client_id", "client_secret", "url_token", "escopo", "arquivo")):
        base.pop("access_token", None)
        base.pop("token_expira_em", None)

    tcred = tc.obter_tipo(credencial.tipo)
    nomes = tcred.nomes_campos if tcred else ()
    base = {k: v for k, v in base.items() if k in nomes}
    credencial.dados_cifrado = cofre.cifrar(json.dumps(base, ensure_ascii=False))
    credencial.resumo = montar_resumo(credencial.tipo, base)


def gravar_token_renovado(
    credencial: Credencial, token: str, expira_em: datetime
) -> None:
    """Escrita pelo SISTEMA (job de refresh): troca só o `token` no saco, recifra e
    atualiza `expira_em`, preservando os demais campos (ex.: `ig_user_id`). Não
    passa pela rota — quem persiste é o agendador."""
    tcred = tc.obter_tipo(credencial.tipo)
    nomes = tcred.nomes_campos if tcred else ()
    base = decifrar(credencial)
    base["token"] = token
    base = {k: v for k, v in base.items() if k in nomes}
    credencial.dados_cifrado = cofre.cifrar(json.dumps(base, ensure_ascii=False))
    credencial.resumo = montar_resumo(credencial.tipo, base)
    credencial.expira_em = expira_em


def usado_por(sessao: Session, credencial_id: uuid.UUID) -> int:
    """Quantos instrumentos apontam para esta credencial — para a interface
    avisar 'usado por N' e travar o apagar de uma credencial em uso."""
    return sessao.scalar(
        select(func.count())
        .select_from(Instrumento)
        .where(Instrumento.credencial_id == credencial_id)
    )
