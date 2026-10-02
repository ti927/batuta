"""Ciclo de vida dos modelos de IA — FONTE ÚNICA de quais modelos o Batuta usa e de
quando cada um sai do ar.

Por que existe (2026-10-01): a OpenAI desligou o vídeo (Sora) em 24/09/2026 e o
Batuta só descobriu dias depois, por acaso. As empresas de IA desligam modelos com
data marcada; o que dá para evitar é descobrir pela boca do cliente. Por isso cada
modelo que o Batuta oferece mora AQUI, com a situação e a data de saída lidas da
página oficial de descontinuação de cada empresa (campo `fonte`):

- a lista de modelos dos agentes (`modelos_ia.MODELOS_POR_PROVEDOR`) e os catálogos
  dos instrumentos saem daqui;
- um teste falha quando um modelo PADRÃO está perto de sair (`JANELA_ALERTA_DIAS`);
- a tela marca o que vai sair e esconde o que já saiu (rota `/modelos`);
- o vigia diário (`vigia_modelos.py`) confere, na própria IA, se cada modelo em uso
  ainda existe.

Folha de propósito (só dados e funções puras): `modelos_ia`, os instrumentos e a
interface importam daqui sem risco de ciclo.

Datas da Anthropic: para modelos ATIVOS ela publica só um "não antes de" e promete
avisar 60 dias antes de marcar a saída de verdade. Esse "não antes de" NÃO entra em
`sai_em` (viraria alarme falso); quando ela anunciar a descontinuação, o modelo passa
a `descontinuado` com a data firme.
"""

from dataclasses import dataclass
from datetime import date

ATIVO = "ativo"
DESCONTINUADO = "descontinuado"  # ainda funciona, com data de saída marcada
DESLIGADO = "desligado"  # a empresa já tirou do ar: chamar dá erro

TEXTO = "texto"  # agentes, IA de conversa, roteamento, ler imagem
IMAGEM = "imagem"
VIDEO = "video"
TRANSCRICAO = "transcricao"

# Quanto antes da saída o Batuta começa a avisar (selo na tela, teste que falha).
JANELA_ALERTA_DIAS = 60

FONTE_ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/model-deprecations"
FONTE_OPENAI = "https://developers.openai.com/api/docs/deprecations"
FONTE_GOOGLE = "https://ai.google.dev/gemini-api/docs/deprecations"

_EMPRESA = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google"}
# Com o artigo certo, para a frase sair em português ("a OpenAI", "o Google").
_COM_ARTIGO = {"anthropic": "a Anthropic", "openai": "a OpenAI", "google": "o Google"}
_FONTE = {"anthropic": FONTE_ANTHROPIC, "openai": FONTE_OPENAI, "google": FONTE_GOOGLE}


@dataclass(frozen=True)
class Modelo:
    id: str
    provedor: str
    uso: str
    situacao: str = ATIVO
    sai_em: date | None = None
    substituto: str | None = None
    # Outros nomes pelos quais o mesmo modelo é chamado (ex.: o apelido e a versão
    # datada da Anthropic). O vigia aceita qualquer um deles como "existe".
    apelidos: tuple[str, ...] = ()

    @property
    def fonte(self) -> str:
        return _FONTE[self.provedor]

    @property
    def empresa(self) -> str:
        return _EMPRESA[self.provedor]

    @property
    def a_empresa(self) -> str:
        """"a OpenAI" / "o Google" — minúsculo; use `.capitalize()` só no 1º caractere."""
        return _COM_ARTIGO[self.provedor]


# Conferido nas três páginas oficiais em 2026-10-02. Ao mexer, reconfira a `fonte`.
# A ORDEM importa: é a ordem em que os modelos aparecem nos seletores.
REGISTRO: tuple[Modelo, ...] = (
    # ── Anthropic (texto) — todos ativos; menor "não antes de": Haiku 4.5, 15/10/2026 ──
    Modelo("claude-sonnet-5-5", "anthropic", TEXTO),
    Modelo("claude-opus-5-5", "anthropic", TEXTO),
    Modelo("claude-opus-5", "anthropic", TEXTO),
    Modelo("claude-opus-4-8", "anthropic", TEXTO),
    Modelo("claude-sonnet-5", "anthropic", TEXTO),
    Modelo("claude-sonnet-4-6", "anthropic", TEXTO),
    Modelo("claude-haiku-4-5", "anthropic", TEXTO, apelidos=("claude-haiku-4-5-20251001",)),
    # ── OpenAI (texto) — sem data de saída publicada ──
    Modelo("gpt-5.6-luna", "openai", TEXTO),
    Modelo("gpt-5.6-terra", "openai", TEXTO),
    Modelo("gpt-5.6-sol", "openai", TEXTO),
    Modelo("gpt-4.1", "openai", TEXTO),
    Modelo("gpt-4o", "openai", TEXTO),
    Modelo("gpt-4o-mini", "openai", TEXTO),
    # ── Google (texto) — os 1.5 e o 2.0 já saíram (2.0 em 01/06/2026) ──
    Modelo("gemini-3.8-flash", "google", TEXTO),
    Modelo("gemini-3.6-flash", "google", TEXTO),
    Modelo("gemini-3.5-flash-lite", "google", TEXTO),
    Modelo("gemini-3.1-pro-preview", "google", TEXTO),
    Modelo("gemini-2.0-flash", "google", TEXTO, DESLIGADO, date(2026, 6, 1), "gemini-3.6-flash"),
    Modelo("gemini-1.5-pro", "google", TEXTO, DESLIGADO, None, "gemini-3.8-flash"),
    Modelo("gemini-1.5-flash", "google", TEXTO, DESLIGADO, None, "gemini-3.5-flash-lite"),
    # ── OpenAI (imagem) ──
    Modelo("gpt-image-2", "openai", IMAGEM),
    Modelo("gpt-image-2.5-flare", "openai", IMAGEM),
    Modelo("gpt-image-2.5-sunburst", "openai", IMAGEM),
    Modelo("gpt-image-1", "openai", IMAGEM, DESCONTINUADO, date(2026, 10, 23), "gpt-image-2"),
    Modelo("gpt-image-1-mini", "openai", IMAGEM, DESCONTINUADO, date(2026, 12, 1), "gpt-image-2.5-flare"),
    Modelo("gpt-image-1.5", "openai", IMAGEM, DESCONTINUADO, date(2026, 12, 1), "gpt-image-2.5-sunburst"),
    # ── OpenAI (vídeo) — desligado sem substituto ──
    Modelo("sora-2", "openai", VIDEO, DESLIGADO, date(2026, 9, 24)),
    Modelo("sora-2-pro", "openai", VIDEO, DESLIGADO, date(2026, 9, 24)),
    # ── OpenAI (transcrição) ──
    Modelo("whisper-1", "openai", TRANSCRICAO, DESCONTINUADO, date(2027, 2, 26), "gpt-transcribe"),
)

_POR_ID: dict[str, Modelo] = {}
for _m in REGISTRO:
    for _nome in (_m.id, *_m.apelidos):
        _POR_ID[_nome] = _m


def obter(modelo_id: str | None) -> Modelo | None:
    """O registro de um modelo (pelo id ou por um apelido). None = desconhecido."""
    return _POR_ID.get((modelo_id or "").strip())


def modelos(uso: str, provedor: str | None = None, *, com_desligados: bool = False) -> list[str]:
    """Os ids de um uso (e provedor), na ordem do registro. Sem os desligados por
    padrão: é a lista do que se pode ESCOLHER."""
    return [
        m.id for m in REGISTRO
        if m.uso == uso
        and (provedor is None or m.provedor == provedor)
        and (com_desligados or m.situacao != DESLIGADO)
    ]


def dias_para_sair(modelo_id: str | None, hoje: date | None = None) -> int | None:
    """Quantos dias faltam para o modelo sair (negativo = já saiu). None = sem data."""
    m = obter(modelo_id)
    if m is None or m.sai_em is None:
        return None
    return (m.sai_em - (hoje or date.today())).days


def _maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def alerta(modelo_id: str | None, hoje: date | None = None) -> str | None:
    """O aviso para quem usa este modelo, em português de gente — ou None se não há
    nada a dizer (ativo, desconhecido, ou saída ainda além da janela de alerta)."""
    m = obter(modelo_id)
    if m is None:
        return None
    troca = f" Troque para {m.substituto}." if m.substituto else ""
    if m.situacao == DESLIGADO:
        quando = f" em {_data(m.sai_em)}" if m.sai_em else ""
        return f"{_maiuscula(m.a_empresa)} desligou o modelo {m.id}{quando}.{troca}"
    dias = dias_para_sair(m.id, hoje)
    if m.situacao == DESCONTINUADO and dias is not None and dias <= JANELA_ALERTA_DIAS:
        return f"{_maiuscula(m.a_empresa)} desliga o modelo {m.id} em {_data(m.sai_em)}.{troca}"
    return None


def como_dado(hoje: date | None = None) -> list[dict]:
    """O registro para a tela (rota `/modelos`): cada modelo com situação, data de
    saída, substituto e o aviso já pronto."""
    return [
        {
            "id": m.id,
            "provedor": m.provedor,
            "uso": m.uso,
            "situacao": m.situacao,
            "sai_em": m.sai_em.isoformat() if m.sai_em else None,
            "substituto": m.substituto,
            "alerta": alerta(m.id, hoje),
            "fonte": m.fonte,
        }
        for m in REGISTRO
    ]
