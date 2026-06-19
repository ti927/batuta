"""Instrumento "Busca na web (Exa)" — busca SEMÂNTICA (PRODUTO §13).

Alternativa ao `busca_web` (Tavily): a Exa busca por SIGNIFICADO (não só
palavra-chave), então tende a trazer ângulos mais diversos — útil quando a busca
por palavra-chave fica presa sempre no mesmo topo (a "mesma pauta"). Mesma forma
do `busca_web`: a IA passa só a `consulta`; quem PADRONIZA a busca (tipo, recência,
categoria, domínios) é o usuário, na `Config`. Rótulos em português → parâmetros
da Exa via mapas (fonte única); o `executar` monta o corpo condicionalmente.

A chave é segredo do cofre, reusando o pool da organização (`chave_compartilhada`
→ serviço "exa"); sem chave cadastrada, falha com recado claro (sem fallback de
ambiente). Política de falha do encaixe (Tarefa 5.1): transporte/5xx/429 são
retentáveis; chave recusada (401/403) e 4xx não.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 25.0
URL_EXA = "https://api.exa.ai/search"
MAX_CONSULTA = 400

# ── FONTE ÚNICA: rótulos PT (na config/tela) → valores da API Exa ──
TIPOS_BUSCA = {"rapida": "fast", "equilibrada": "auto", "profunda": "deep"}
CATEGORIAS = {
    "": None,
    "noticias": "news",
    "pesquisa": "research paper",
    "empresa": "company",
    "relatorio_financeiro": "financial report",
}
# Recência → quantos dias atrás começa (vira `startPublishedDate`).
RECENCIAS_DIAS = {"": None, "24h": 1, "semana": 7, "mes": 30, "ano": 365}
MAX_DOMINIOS = 100


class ConfigBuscaExa(BaseModel):
    """Configuração fixa da busca semântica (definida por quem monta o instrumento).
    Conjuntos fechados são `Literal` (Pydantic valida; a UI vira dropdown). `chave_api`
    é SEGREDO; vazia, usa a chave Exa do pool da organização."""

    tipo_busca: Literal["rapida", "equilibrada", "profunda"] = Field(
        default="equilibrada",
        title="Tipo de busca",
        description="rápida = direta; equilibrada = a Exa decide; profunda = pesquisa "
        "mais a fundo (mais cara e lenta).",
    )
    categoria: Literal[
        "", "noticias", "pesquisa", "empresa", "relatorio_financeiro"
    ] = Field(
        default="",
        title="Categoria",
        description="Foca o tipo de fonte. Vazio = qualquer fonte.",
    )
    recencia: Literal["", "24h", "semana", "mes", "ano"] = Field(
        default="",
        title="Recência",
        description="Só fontes publicadas dentro da janela. Use para trazer material "
        "atual e variar os resultados.",
    )
    max_resultados: int = Field(
        default=5, ge=1, le=20, title="Qtd. de resultados",
        description="Quantos resultados trazer (1 a 20).",
    )
    incluir_dominios: list[str] = Field(
        default_factory=list,
        title="Sites a incluir",
        description='Consultar SÓ estes sites (lista de domínios, ex.: '
        '["g1.globo.com"]). Vazio = sem restrição.',
    )
    excluir_dominios: list[str] = Field(
        default_factory=list,
        title="Sites a excluir",
        description="Nunca usar estes sites (lista de domínios). Vazio = não exclui nada.",
    )
    chave_api: str = Field(
        default="", title="Chave da API (opcional)",
        description="Chave da API da Exa — segredo.",
    )


class ArgsBuscaExa(BaseModel):
    """O que a IA passa ao acionar: a consulta a buscar."""

    consulta: str = Field(min_length=1, description="O que buscar na web.")


def _detalhe_erro(resposta: httpx.Response) -> str:
    """O motivo que a Exa devolveu (corpo do erro), para a mensagem ser útil."""
    try:
        dados = resposta.json()
        if isinstance(dados, dict):
            motivo = dados.get("error") or dados.get("message") or dados.get("detail")
            return str(motivo or dados)[:200]
    except Exception:
        pass
    return (resposta.text or "sem detalhe").strip()[:200]


class BuscaExa(TipoInstrumento):
    tipo = "busca_exa"
    nome_exibicao = "Busca na web (Exa — semântica)"
    descricao = (
        "Busca na internet por SIGNIFICADO (busca semântica) e devolve uma lista de "
        "resultados (título, link e um trecho). Boa para achar ângulos e fontes "
        "diversas, além do óbvio."
    )
    Config = ConfigBuscaExa
    Args = ArgsBuscaExa
    campos_secretos = ("chave_api",)
    chave_compartilhada = ("chave_api", "exa")

    def executar(self, config: ConfigBuscaExa, args: ArgsBuscaExa) -> dict:
        chave = config.chave_api
        if not chave:
            raise FalhaInstrumento(
                "a busca (Exa) não está configurada — cadastre a chave da Exa em "
                "Chaves e credenciais da organização.",
                retentavel=False,
            )
        consulta = args.consulta.strip()[:MAX_CONSULTA]
        if not consulta:
            raise FalhaInstrumento(
                "a consulta de busca veio vazia — diga em poucas palavras o que buscar.",
                retentavel=False,
            )

        corpo: dict[str, Any] = {
            "query": consulta,
            "type": TIPOS_BUSCA.get(config.tipo_busca, "auto"),
            "numResults": config.max_resultados,
            # Pede o texto da página para vir o trecho (como o busca_web).
            "contents": {"text": True},
        }
        categoria = CATEGORIAS.get(config.categoria)
        if categoria:
            corpo["category"] = categoria
        dias = RECENCIAS_DIAS.get(config.recencia)
        if dias:
            inicio = datetime.now(timezone.utc) - timedelta(days=dias)
            corpo["startPublishedDate"] = inicio.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if config.incluir_dominios:
            corpo["includeDomains"] = config.incluir_dominios[:MAX_DOMINIOS]
        if config.excluir_dominios:
            corpo["excludeDomains"] = config.excluir_dominios[:MAX_DOMINIOS]

        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(
                    URL_EXA, json=corpo, headers={"x-api-key": chave}
                )
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível buscar na web (Exa): {e}", retentavel=True
            )

        status = resposta.status_code
        if status in (401, 403):
            raise FalhaInstrumento(
                "a chave da Exa foi recusada — verifique-a.", retentavel=False
            )
        if status == 429 or 500 <= status < 600:
            raise FalhaInstrumento(
                f"o serviço de busca (Exa) respondeu HTTP {status}.", retentavel=True
            )
        if not resposta.is_success:
            raise FalhaInstrumento(
                f"a busca (Exa) falhou (HTTP {status}): {_detalhe_erro(resposta)}",
                retentavel=False,
            )

        dados: dict[str, Any] = resposta.json()
        resultados = [
            {
                "titulo": r.get("title"),
                "url": r.get("url"),
                "trecho": (r.get("text") or "")[:500],
                "data": r.get("publishedDate"),
            }
            for r in dados.get("results", [])
        ]
        return {"ok": True, "consulta": args.consulta, "resultados": resultados}


registrar(BuscaExa())
