"""Tipos de credencial da caixa-forte (Passo 2 da FASE Caixa-forte).

Cada tipo de credencial declara os CAMPOS que ela carrega — o "saco" de uma
conexão (ex.: WordPress = usuario + senha_app). Os nomes dos campos batem com os
nomes na `Config` do instrumento, de propósito: assim a borda (Passo 4) mescla os
valores direto na configuração, sem tradução. Um campo `secreto` é mascarado na
interface (mostra só os últimos 4); um campo de identidade (ex.: usuario) pode
ser exibido.

É o paralelo, para credenciais, do registro de `TipoInstrumento`
(`instrumentos/base.py`): leve e declarativo. Aqui NÃO se cifra nem se resolve
nada — isso é dos Passos 3 (cofre) e 4 (resolução na borda).

`expira_em`/OAuth (balde 3) entram aqui no futuro como um `tipo` novo, sem mudar
este contrato.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CampoCredencial:
    """Um campo do saco de uma credencial."""

    nome: str  # bate com o nome do campo na Config do instrumento
    rotulo: str  # rótulo para a interface
    secreto: bool = True  # True = mascarado (últimos 4); False = identidade visível
    # Campo que NÃO vai para a Config de instrumento nenhum — ou porque é dado de
    # exibição derivado do segredo (o titular e a validade lidos do certificado),
    # ou porque só a BORDA o usa (a URL do token OAuth, o escopo, o cache do
    # token). Como não é injetado, não precisa ter campo correspondente na Config
    # de quem aceita este tipo (ver test_tipos_credencial).
    interno: bool = False


@dataclass(frozen=True)
class TipoCredencial:
    """Um tipo de credencial nomeada (o formato de uma conexão)."""

    tipo: str
    nome_exibicao: str
    campos: tuple[CampoCredencial, ...]

    @property
    def campos_secretos(self) -> tuple[str, ...]:
        return tuple(c.nome for c in self.campos if c.secreto)

    @property
    def nomes_campos(self) -> tuple[str, ...]:
        return tuple(c.nome for c in self.campos)

    @property
    def nomes_injetaveis(self) -> tuple[str, ...]:
        """Os campos que viram configuração de um instrumento — todos menos os
        internos. É esta lista que precisa ter correspondência na Config de quem
        aceita o tipo (o `nomes_campos` inteiro segue sendo o saco guardado)."""
        return tuple(c.nome for c in self.campos if not c.interno)


_REGISTRO: dict[str, TipoCredencial] = {}


def registrar(t: TipoCredencial) -> None:
    _REGISTRO[t.tipo] = t


def obter_tipo(tipo: str) -> TipoCredencial | None:
    return _REGISTRO.get(tipo)


def tipos_disponiveis() -> list[TipoCredencial]:
    return list(_REGISTRO.values())


# ───────────────────────── Tipos concretos (v1) ─────────────────────────
# Mapeiam os instrumentos atuais que pedem segredo. Um instrumento declara em
# `tipos_credencial_aceitos` quais destes ele aceita (filtra o seletor da UI).
# O par usuario+senha de uma conexão anda JUNTO na mesma credencial (decisão do
# maestro): evita o segredo apontar para uma identidade de outra conta.

registrar(
    TipoCredencial(
        "wordpress",
        "WordPress (usuário + senha de aplicativo)",
        (
            CampoCredencial("usuario", "Usuário", secreto=False),
            CampoCredencial("senha_app", "Senha de aplicativo"),
        ),
    )
)
registrar(
    TipoCredencial(
        "sql",
        "Banco de dados SQL (usuário + senha)",
        (
            CampoCredencial("usuario", "Usuário", secreto=False),
            CampoCredencial("senha", "Senha"),
        ),
    )
)
registrar(
    TipoCredencial(
        "telegram_bot",
        "Bot do Telegram (token)",
        (CampoCredencial("token_bot", "Token do bot"),),
    )
)
registrar(
    TipoCredencial(
        "token_bearer",
        "Token de API (Bearer)",
        (CampoCredencial("token_bearer", "Token"),),
    )
)
# Instagram (API com login do Instagram). O maestro cola o token de longa duração
# gerado no painel da Meta (Instagram → API setup → Gerar token); a borda valida,
# descobre o `ig_user_id` sozinho (via /me) e o agendador o renova antes dos 60
# dias. `ig_user_id` é identidade (não-secreto, preenchido automaticamente).
registrar(
    TipoCredencial(
        "instagram",
        "Instagram (token de acesso)",
        (
            CampoCredencial(
                "token", "Token de acesso (gerado no painel da Meta)"
            ),
            CampoCredencial(
                "ig_user_id", "ID da conta (preenchido automaticamente)",
                secreto=False,
            ),
        ),
    )
)
# Certificado digital de cliente (mTLS) — fundação das integrações bancárias
# (Pix, boleto) e de qualquer API que exija certificado. O consultor SOBE o arquivo
# (.pfx/.p12 ou .pem/.crt) na tela; a borda normaliza para PEM e guarda cifrado — a
# IA NUNCA recebe o segredo (decisão do maestro). `certificado`/`chave_privada` não
# são digitados: vêm do arquivo. `titular`/`validade` são derivados do próprio
# certificado (preenchidos automaticamente), como o `ig_user_id` do Instagram.
#
# OAuth (opcional, mas é o que um banco de verdade exige): preenchidos
# `client_id`/`client_secret`/`url_token`, a borda troca essas credenciais por um
# `access_token` no endpoint do banco — apresentando o MESMO certificado — e o
# renova sozinha antes de vencer. O `access_token` é o único desses campos que
# chega ao instrumento; a URL, o escopo e o vencimento do token são internos.
registrar(
    TipoCredencial(
        "certificado_mtls",
        "Certificado digital (mTLS) — Pix, boleto e APIs bancárias",
        (
            CampoCredencial("certificado", "Certificado (arquivo)"),
            CampoCredencial("chave_privada", "Chave privada"),
            CampoCredencial("client_id", "Client ID (OAuth, se houver)", secreto=False),
            CampoCredencial("client_secret", "Client Secret (OAuth, se houver)"),
            CampoCredencial(
                "url_token", "URL do token OAuth (se houver)",
                secreto=False, interno=True,
            ),
            CampoCredencial(
                "escopo", "Escopo do token (se houver)", secreto=False, interno=True,
            ),
            CampoCredencial(
                "titular", "Titular (preenchido automaticamente)",
                secreto=False, interno=True,
            ),
            CampoCredencial(
                "validade", "Validade (preenchida automaticamente)",
                secreto=False, interno=True,
            ),
            # Cache do token de acesso: obtido e renovado pela borda, nunca
            # digitado. O `access_token` é injetado no instrumento (vira o
            # cabeçalho Authorization); o vencimento é só bookkeeping da borda.
            # O vencimento do CERTIFICADO segue no `Credencial.expira_em` — são
            # relógios diferentes (o certificado dura ~1 ano; o token, ~1 hora).
            CampoCredencial("access_token", "Token de acesso (automático)"),
            CampoCredencial(
                "token_expira_em", "Vencimento do token (automático)",
                secreto=False, interno=True,
            ),
        ),
    )
)
# Google (Gmail/Agenda/Drive/Search Console) — conta conectada por OAuth (balde 3).
# O usuário NÃO cola nada: o fluxo "Conectar Google" preenche todos os campos. O
# `access_token` (~1h) é renovado sob demanda pela borda a partir do `refresh_token`
# (durável); `email` e `escopos` são identidade (preenchidos automaticamente).
registrar(
    TipoCredencial(
        "google",
        "Google (Gmail/Agenda/Drive/Search Console)",
        (
            CampoCredencial("access_token", "Token de acesso (renovado automaticamente)"),
            CampoCredencial("refresh_token", "Token de renovação"),
            CampoCredencial(
                "email", "Conta Google (preenchida automaticamente)", secreto=False
            ),
            CampoCredencial(
                "escopos", "Permissões concedidas (preenchidas automaticamente)",
                secreto=False,
            ),
        ),
    )
)
