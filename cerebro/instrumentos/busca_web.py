"""Instrumento "Busca na web" (PRODUTO §13).

Dá ao agente informação atualizada da internet. Usa a API da Tavily, feita para
IA (resultados já resumidos). A chave é segredo (cofre/pool da organização); o
`TAVILY_API_KEY` do ambiente segue como queda de legado.

Quem monta o instrumento PADRONIZA a busca pela `Config` (tipo, recência,
profundidade, país, sites a incluir/excluir, quantidade) — é o que evita a "mesma
pauta sempre" por falta de recência/tópico. Os rótulos ficam em português e são
traduzidos para os parâmetros da Tavily no `executar` (mapas no topo do módulo).
A IA só passa a `consulta`; os parâmetros são do usuário, não do agente.

Segue a política de falha do encaixe (Tarefa 5.1): transporte/5xx/429 são
retentáveis; chave ausente/ inválida não.
"""

import os
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 20.0
URL_TAVILY = "https://api.tavily.com/search"
# A Tavily recusa (HTTP 400) consultas acima de 400 caracteres. Truncamos para
# não estourar — uma consulta de busca não precisa ser maior que isso.
MAX_CONSULTA = 400

# ── FONTE ÚNICA: rótulos em português (na config/tela) → valores da API Tavily ──
# Os campos da config guardam o valor PT (dropdowns amigáveis); o `executar` traduz
# para o que a Tavily entende. Vazio ("") = "sem preferência" → não vai no corpo.
TOPICOS = {"geral": "general", "noticias": "news", "financas": "finance"}
PROFUNDIDADES = {"rapida": "basic", "aprofundada": "advanced"}
RECENCIAS = {"": None, "24h": "day", "semana": "week", "mes": "month", "ano": "year"}
PAISES = {
    "": None,
    "brasil": "brazil",
    "portugal": "portugal",
    "estados unidos": "united states",
    "reino unido": "united kingdom",
    "espanha": "spain",
}
# Tetos da Tavily para as listas de domínios (recusa acima disso).
MAX_DOMINIOS_INCLUIR = 300
MAX_DOMINIOS_EXCLUIR = 150


def _detalhe_erro(resposta: httpx.Response) -> str:
    """O motivo que a Tavily devolveu (corpo do erro), para a mensagem ser útil em
    vez de só 'HTTP 400'. Cai no texto cru se não for JSON."""
    try:
        dados = resposta.json()
        if isinstance(dados, dict):
            motivo = dados.get("detail") or dados.get("error") or dados.get("message")
            return str(motivo or dados)[:200]
    except Exception:
        pass
    return (resposta.text or "sem detalhe").strip()[:200]


class ConfigBuscaWeb(BaseModel):
    """Configuração fixa da busca, definida por quem monta o instrumento (padroniza
    e otimiza as buscas daquele instrumento). Os conjuntos fechados são `Literal`:
    o Pydantic valida e a UI os mostra como dropdown automaticamente. Os DEFAULTS
    reproduzem o comportamento de antes (geral, rápida, sem recência/país/domínios)
    — instrumento existente não muda de comportamento. `chave_api` é SEGREDO (cofre,
    Fase 7-B); se vazia, cai na chave Tavily da organização (pool) e, por fim, na
    TAVILY_API_KEY do .env (fallback legado)."""

    topico: Literal["geral", "noticias", "financas"] = Field(
        default="geral",
        title="Tipo de busca",
        description="geral = web ampla; notícias = conteúdo recente/jornalístico; "
        "finanças = fontes financeiras.",
    )
    recencia: Literal["", "24h", "semana", "mes", "ano"] = Field(
        default="",
        title="Recência",
        description="Janela de tempo das fontes. Use para fugir de resultados "
        "repetidos/antigos e trazer material atual (ex.: 'semana' ou 'mes').",
    )
    profundidade: Literal["rapida", "aprofundada"] = Field(
        default="rapida",
        title="Profundidade",
        description="rápida = mais barata e direta; aprofundada = busca mais a fundo "
        "(custa o dobro de créditos na Tavily).",
    )
    max_resultados: int = Field(
        default=5, ge=1, le=20, title="Qtd. de resultados",
        description="Quantos resultados trazer (1 a 20).",
    )
    pais: Literal[
        "", "brasil", "portugal", "estados unidos", "reino unido", "espanha"
    ] = Field(
        default="",
        title="País",
        description="Impulsiona resultados de um país. Só vale para o tipo 'geral'.",
    )
    incluir_dominios: list[str] = Field(
        default_factory=list,
        title="Sites a incluir",
        description='Consultar SÓ estes sites (lista de domínios, ex.: '
        '["g1.globo.com", "valor.globo.com"]). Vazio = sem restrição.',
    )
    excluir_dominios: list[str] = Field(
        default_factory=list,
        title="Sites a excluir",
        description='Nunca usar estes sites (lista de domínios). Vazio = não exclui '
        "nada.",
    )
    chave_api: str = Field(
        default="", title="Chave da API (opcional)",
        description="Chave da API de busca (Tavily) — segredo.",
    )


class ArgsBuscaWeb(BaseModel):
    """O que a IA passa ao acionar: a consulta a buscar."""

    consulta: str = Field(min_length=1, description="O que buscar na web.")


class BuscaWeb(TipoInstrumento):
    tipo = "busca_web"
    categoria = "Web (busca e leitura)"
    nome_exibicao = "Busca na web (Tavily)"
    descricao = (
        "Busca informação atualizada na internet e devolve uma lista de "
        "resultados (título, link e um trecho). Use quando precisar de dados "
        "recentes ou que não estão na sua memória."
    )
    Config = ConfigBuscaWeb
    Args = ArgsBuscaWeb
    campos_secretos = ("chave_api",)
    # Reusa a chave Tavily da organização ("Chaves de IA") quando o instrumento não
    # tem uma chave própria — a borda a injeta; o .env segue como queda de legado.
    chave_compartilhada = ("chave_api", "tavily")

    def executar(self, config: ConfigBuscaWeb, args: ArgsBuscaWeb) -> dict:
        # Prioriza a chave própria/pool (config); .env TAVILY_API_KEY como legado.
        chave = config.chave_api or os.environ.get("TAVILY_API_KEY")
        if not chave:
            raise FalhaInstrumento(
                "a busca na web não está configurada (falta a chave TAVILY_API_KEY "
                "no cérebro).",
                retentavel=False,
            )

        # A Tavily recusa (HTTP 400) consulta vazia. Acontecia quando o agente
        # acionava a busca sem texto útil — o erro voltava como "HTTP 400" opaco.
        # Barramos antes, com mensagem clara que o agente entende e pode corrigir.
        consulta = args.consulta.strip()[:MAX_CONSULTA]
        if not consulta:
            raise FalhaInstrumento(
                "a consulta de busca veio vazia — diga em poucas palavras o que buscar.",
                retentavel=False,
            )

        # Corpo montado a partir da config (rótulos PT → valores Tavily). Campos
        # opcionais só entram quando fazem sentido — a Tavily recusa (HTTP 400)
        # combinações inválidas (ex.: `country` fora do tópico geral).
        corpo: dict[str, Any] = {
            "api_key": chave,  # transporte atual comprovado; Bearer fica p/ depois
            "query": consulta,
            "max_results": config.max_resultados,
            "search_depth": PROFUNDIDADES.get(config.profundidade, "basic"),
            "topic": TOPICOS.get(config.topico, "general"),
        }
        recencia = RECENCIAS.get(config.recencia)
        if recencia:
            corpo["time_range"] = recencia
        # `country` só vale para o tópico geral (regra da Tavily).
        if config.topico == "geral":
            pais = PAISES.get(config.pais)
            if pais:
                corpo["country"] = pais
        if config.incluir_dominios:
            corpo["include_domains"] = config.incluir_dominios[:MAX_DOMINIOS_INCLUIR]
        if config.excluir_dominios:
            corpo["exclude_domains"] = config.excluir_dominios[:MAX_DOMINIOS_EXCLUIR]
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(URL_TAVILY, json=corpo)
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível buscar na web: {e}", retentavel=True
            )

        status = resposta.status_code
        if status in (401, 403):
            raise FalhaInstrumento(
                "a chave de busca (TAVILY_API_KEY) foi recusada — verifique-a.",
                retentavel=False,
            )
        if status == 429 or 500 <= status < 600:
            raise FalhaInstrumento(
                f"o serviço de busca respondeu HTTP {status}.", retentavel=True
            )
        if not resposta.is_success:
            raise FalhaInstrumento(
                f"a busca falhou (HTTP {status}): {_detalhe_erro(resposta)}",
                retentavel=False,
            )

        dados: dict[str, Any] = resposta.json()
        resultados = [
            {
                "titulo": r.get("title"),
                "url": r.get("url"),
                "trecho": (r.get("content") or "")[:500],
            }
            for r in dados.get("results", [])
        ]
        return {"ok": True, "consulta": args.consulta, "resultados": resultados}


registrar(BuscaWeb())
