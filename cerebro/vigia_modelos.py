"""Vigia dos modelos de IA em uso — confere, na PRÓPRIA empresa da IA, se cada modelo
que o Batuta usa ainda existe (2026-10-02).

Por que existe: a OpenAI desligou o vídeo (Sora) em 24/09/2026 e o Batuta só soube
por acaso. O registro (`orquestracao/ciclo_modelos.py`) cobre o que foi ANUNCIADO;
este vigia cobre o que SUMIU — inclusive sem aviso, e inclusive um modelo que alguém
digitou e que nunca esteve no registro.

Como funciona: é um elo da página de status (`saude_elos`), sondado a cada
`PERIODO_S` e logo depois de cada deploy. A sonda junta os modelos em uso (agentes,
IA de conversa de cada organização, instrumentos de IA, roteamento, transcrição),
pergunta a cada empresa a lista de modelos dela (consulta gratuita, com a chave da
consultoria) e compara:
- modelo que a empresa não lista mais, ou que o registro dá como desligado → elo
  CAÍDO, com quem usa (a lista da empresa sozinha não basta: a OpenAI seguiu listando
  o `sora-2` depois de desligá-lo);
- modelo que o registro diz que sai em breve → elo DEGRADADO, com a data.
A queda e a volta do elo já viram evento no banco de logs (`elo.caiu`/`elo.voltou`);
a sonda registra também `modelo.desligado`, porque a primeira sonda depois de um
deploy não é uma "transição" e o elo, sozinho, não deixaria rastro.
"""

from collections import defaultdict

import httpx
from sqlalchemy import select

from observabilidade.escritor import registrar_evento
from orquestracao import ciclo_modelos
from orquestracao.modelos_ia import provedor_do_modelo_seguro

PERIODO_S = 12 * 3600
TIMEOUT_S = 15.0
# Quem usa: até quantos nomes citar na mensagem (o resto vira "e mais N").
MAX_NOMES = 3

_NA_EMPRESA = {"anthropic": "na Anthropic", "openai": "na OpenAI", "google": "no Google"}
# Instrumentos cuja config tem um `modelo` de IA.
_TIPOS_COM_MODELO = ("gerar_imagem", "montar_imagem", "descrever_imagem", "gerar_video")


class ModeloSumiu(Exception):
    """Um ou mais modelos em uso não existem mais na empresa da IA."""


def modelos_em_uso(sessao) -> dict[str, list[str]]:
    """{modelo: [quem usa, em palavras de gente]} de tudo que o Batuta chama."""
    from criacao.loop import MODELO_CRIADORA
    from mensageria import transcricao
    from modelos import Agente, Instrumento, Organizacao, Time
    from orquestracao.llm import MODELO_PADRAO

    uso: dict[str, list[str]] = defaultdict(list)
    for nome, modelo, time_nome in sessao.execute(
        select(Agente.nome, Agente.modelo_ia, Time.nome).join(Time, Time.id == Agente.time_id)
    ):
        uso[modelo or MODELO_PADRAO].append(f"agente {nome} ({time_nome})")
    for nome, modelo in sessao.execute(select(Organizacao.nome, Organizacao.modelo_criadora)):
        uso[modelo or MODELO_CRIADORA].append(f"IA de conversa de {nome}")
    for nome, cfg, time_nome in sessao.execute(
        select(Instrumento.nome, Instrumento.configuracao, Time.nome)
        .join(Time, Time.id == Instrumento.time_id)
        .where(Instrumento.tipo.in_(_TIPOS_COM_MODELO))
    ):
        modelo = (cfg or {}).get("modelo")
        if modelo:
            uso[modelo].append(f"instrumento {nome} ({time_nome})")
    uso[MODELO_PADRAO].append("roteamento das automações")
    uso[transcricao.MODELO].append("transcrição dos áudios do Telegram")
    return dict(uso)


def _listar_anthropic(chave: str, cli: httpx.Client) -> set[str]:
    ids: set[str] = set()
    params: dict = {"limit": 1000}
    while True:
        r = cli.get(
            "https://api.anthropic.com/v1/models", params=params,
            headers={"x-api-key": chave, "anthropic-version": "2023-06-01"},
        )
        r.raise_for_status()
        corpo = r.json()
        ids.update(m["id"] for m in corpo.get("data", []))
        if not corpo.get("has_more"):
            return ids
        params["after_id"] = corpo.get("last_id")


def _listar_openai(chave: str, cli: httpx.Client) -> set[str]:
    r = cli.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {chave}"})
    r.raise_for_status()
    return {m["id"] for m in r.json().get("data", [])}


def _listar_google(chave: str, cli: httpx.Client) -> set[str]:
    ids: set[str] = set()
    params: dict = {"key": chave, "pageSize": 1000}
    while True:
        r = cli.get("https://generativelanguage.googleapis.com/v1beta/models", params=params)
        r.raise_for_status()
        corpo = r.json()
        ids.update(m["name"].removeprefix("models/") for m in corpo.get("models", []))
        if not corpo.get("nextPageToken"):
            return ids
        params["pageToken"] = corpo["nextPageToken"]


LISTAR = {"anthropic": _listar_anthropic, "openai": _listar_openai, "google": _listar_google}


def existe(modelo: str, listados: set[str]) -> bool:
    """O modelo está na lista da empresa — pelo nome, por um apelido do registro, ou
    como versão datada (a Anthropic lista `claude-haiku-4-5-20251001`, e o Batuta
    chama pelo apelido `claude-haiku-4-5`)."""
    registro = ciclo_modelos.obter(modelo)
    nomes = {modelo, *(registro.apelidos if registro else ())}
    return any(n in listados or any(x.startswith(n + "-20") for x in listados) for n in nomes)


def _quem(usos: list[str]) -> str:
    resto = len(usos) - MAX_NOMES
    texto = ", ".join(usos[:MAX_NOMES])
    return texto + (f" e mais {resto}" if resto > 0 else "")


def conferir(uso: dict[str, list[str]], chaves: dict[str, str], cli: httpx.Client) -> tuple[list[str], list[str]]:
    """(sumidos, saindo): as frases para o elo. `chaves` = {provedor: chave}; provedor
    sem chave não é conferido (não há como perguntar — e ninguém o usa de verdade sem
    chave, a chamada falharia antes)."""
    por_provedor: dict[str, list[str]] = defaultdict(list)
    for modelo in uso:
        provedor = provedor_do_modelo_seguro(modelo)
        if provedor:
            por_provedor[provedor].append(modelo)

    sumidos: list[str] = []
    for provedor, modelos in sorted(por_provedor.items()):
        chave = chaves.get(provedor)
        if not chave or provedor not in LISTAR:
            continue
        listados = LISTAR[provedor](chave, cli)
        for modelo in sorted(modelos):
            if not existe(modelo, listados):
                sumidos.append(
                    f"{modelo} não existe mais {_NA_EMPRESA[provedor]} — usado por "
                    f"{_quem(uso[modelo])}"
                )

    # O registro também derruba: a lista da empresa não basta. A OpenAI seguiu listando
    # o `sora-2` depois de desligá-lo (24/09/2026) — quem chamava recebia erro.
    saindo: list[str] = []
    for modelo in sorted(uso):
        aviso = ciclo_modelos.alerta(modelo)
        if not aviso:
            continue
        frase = f"{aviso} Usado por {_quem(uso[modelo])}."
        registro = ciclo_modelos.obter(modelo)
        if registro and registro.situacao == ciclo_modelos.DESLIGADO:
            sumidos.append(frase)
        else:
            saindo.append(frase)
    return sumidos, saindo


def sonda() -> str | None:
    """A sonda do elo "Modelos de IA". Levanta `ModeloSumiu` (caído) ou
    `EloDegradado` (algo sai em breve); devolve o resumo quando está tudo certo."""
    from chaves import resolver_chaves_por_organizacao
    from saude_elos import EloDegradado
    from sessao import CriadorDeSessao

    sessao = CriadorDeSessao()
    try:
        uso = modelos_em_uso(sessao)
        chaves, _ = resolver_chaves_por_organizacao(sessao, None)
    finally:
        sessao.close()

    with httpx.Client(timeout=TIMEOUT_S) as cli:
        sumidos, saindo = conferir(uso, chaves, cli)

    if sumidos:
        registrar_evento(
            categoria="sistema", acao="modelo.desligado", nivel="error",
            resultado="falha", persistir=True,
            detalhe={"sumidos": sumidos, "o_que_fazer": "Troque o modelo de quem usa."},
        )
        raise ModeloSumiu("; ".join(sumidos))
    if saindo:
        raise EloDegradado(" ".join(saindo))
    return f"{len(uso)} modelos em uso, todos disponíveis."
