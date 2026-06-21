"""Instrumento "Ler site (Tavily)" — extração de página (PRODUTO §13).

Capacidade distinta da BUSCA: dada uma URL, devolve o CONTEÚDO LIMPO daquela
página (não só o trecho da busca, nem o HTML cru do `rest`). Usa o endpoint
`/extract` da Tavily, REUSANDO a mesma chave Tavily do pool (`chave_compartilhada`
→ "tavily"); a auth segue o padrão documentado (Bearer). Limitação: não renderiza
páginas feitas em JavaScript — para essas, use "Ler site (Firecrawl)".

Política de falha do encaixe (Tarefa 5.1): transporte/5xx/429 são retentáveis;
chave recusada (401/403), chave ausente e 4xx não.
"""

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 30.0
URL_TAVILY_EXTRACT = "https://api.tavily.com/extract"

PROFUNDIDADES = {"rapida": "basic", "aprofundada": "advanced"}
FORMATOS = {"markdown": "markdown", "texto": "text"}


class ConfigLerSite(BaseModel):
    """Configuração fixa. `chave_api` é SEGREDO; vazia, usa a chave Tavily do pool
    da organização (a MESMA do `busca_web`)."""

    profundidade: Literal["rapida", "aprofundada"] = Field(
        default="rapida",
        title="Profundidade",
        description="rápida = extração direta; aprofundada = tenta recuperar mais do "
        "conteúdo (mais cara).",
    )
    formato: Literal["markdown", "texto"] = Field(
        default="markdown",
        title="Formato",
        description="markdown preserva títulos/listas; texto é puro.",
    )
    max_caracteres: int = Field(
        default=20000, ge=500, le=100000, title="Tamanho máximo (caracteres)",
        description="Corta o conteúdo neste tamanho para não estourar o contexto do agente.",
    )
    chave_api: str = Field(
        default="", title="Chave da API (opcional)",
        description="Chave da API de busca (Tavily) — segredo. Em branco usa a do pool.",
    )


class ArgsLerSite(BaseModel):
    """O que a IA passa ao acionar: a URL a ler."""

    url: str = Field(min_length=1, description="O endereço (URL) da página a ler.")


class LerSite(TipoInstrumento):
    tipo = "ler_site"
    categoria = "Web (busca e leitura)"
    nome_exibicao = "Ler site (Tavily)"
    descricao = (
        "Abre uma URL e devolve o conteúdo limpo da página (texto do artigo, sem o "
        "lixo de menus e scripts). Use depois de achar um link na busca, para ler o "
        "conteúdo completo. Não lê páginas feitas em JavaScript."
    )
    Config = ConfigLerSite
    Args = ArgsLerSite
    campos_secretos = ("chave_api",)
    chave_compartilhada = ("chave_api", "tavily")

    def executar(self, config: ConfigLerSite, args: ArgsLerSite) -> dict:
        chave = config.chave_api
        if not chave:
            raise FalhaInstrumento(
                "a leitura de site (Tavily) não está configurada — cadastre a chave "
                "Tavily em Chaves e credenciais da organização.",
                retentavel=False,
            )
        url = args.url.strip()
        if not url:
            raise FalhaInstrumento(
                "a URL veio vazia — informe o endereço da página a ler.",
                retentavel=False,
            )

        corpo: dict[str, Any] = {
            "urls": [url],
            "extract_depth": PROFUNDIDADES.get(config.profundidade, "basic"),
            "format": FORMATOS.get(config.formato, "markdown"),
        }
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(
                    URL_TAVILY_EXTRACT,
                    json=corpo,
                    headers={"Authorization": f"Bearer {chave}"},
                )
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível ler a página: {e}", retentavel=True
            )

        status = resposta.status_code
        if status in (401, 403):
            raise FalhaInstrumento(
                "a chave de leitura (Tavily) foi recusada — verifique-a.",
                retentavel=False,
            )
        if status == 429 or 500 <= status < 600:
            raise FalhaInstrumento(
                f"o serviço de leitura respondeu HTTP {status}.", retentavel=True
            )
        if not resposta.is_success:
            raise FalhaInstrumento(
                f"a leitura falhou (HTTP {status}).", retentavel=False
            )

        dados: dict[str, Any] = resposta.json()
        resultados = dados.get("results") or []
        if not resultados:
            # A Tavily reporta URLs que não conseguiu abrir em `failed_results`.
            return {
                "ok": False,
                "url": url,
                "erro": "não consegui extrair o conteúdo desta página (talvez exija "
                "JavaScript — tente 'Ler site (Firecrawl)').",
            }
        conteudo = (resultados[0].get("raw_content") or "")[: config.max_caracteres]
        return {"ok": True, "url": url, "conteudo": conteudo}


registrar(LerSite())
