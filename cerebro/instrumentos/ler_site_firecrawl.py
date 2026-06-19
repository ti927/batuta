"""Instrumento "Ler site (Firecrawl)" — extração robusta de página (PRODUTO §13).

Como o `ler_site` (Tavily), mas usando o Firecrawl, que RENDERIZA páginas feitas
em JavaScript (sites modernos, SPAs) e devolve markdown limpo. É a opção robusta
quando o Tavily não consegue ler a página. A chave é segredo do cofre, reusando o
pool da organização (`chave_compartilhada` → "firecrawl"); sem chave cadastrada,
falha com recado claro (sem fallback de ambiente).

Política de falha do encaixe (Tarefa 5.1): transporte/5xx/429 são retentáveis;
chave recusada (401/403), chave ausente e 4xx não.
"""

from typing import Any

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 60.0  # Firecrawl pode renderizar JS — damos folga.
URL_FIRECRAWL_SCRAPE = "https://api.firecrawl.dev/v2/scrape"


class ConfigLerSiteFirecrawl(BaseModel):
    """Configuração fixa. `chave_api` é SEGREDO; vazia, usa a chave Firecrawl do
    pool da organização."""

    apenas_conteudo_principal: bool = Field(
        default=True,
        title="Só o conteúdo principal",
        description="Remove menus, rodapés e barras laterais, deixando só o artigo. "
        "Recomendado.",
    )
    max_caracteres: int = Field(
        default=20000, ge=500, le=100000, title="Tamanho máximo (caracteres)",
        description="Corta o conteúdo neste tamanho para não estourar o contexto do agente.",
    )
    chave_api: str = Field(
        default="", title="Chave da API (opcional)",
        description="Chave da API do Firecrawl — segredo. Em branco usa a do pool.",
    )


class ArgsLerSiteFirecrawl(BaseModel):
    """O que a IA passa ao acionar: a URL a ler."""

    url: str = Field(min_length=1, description="O endereço (URL) da página a ler.")


class LerSiteFirecrawl(TipoInstrumento):
    tipo = "ler_site_firecrawl"
    nome_exibicao = "Ler site (Firecrawl)"
    descricao = (
        "Abre uma URL e devolve o conteúdo limpo da página em markdown, inclusive de "
        "sites modernos feitos em JavaScript. Use para ler o conteúdo completo de uma "
        "página quando precisar de robustez."
    )
    Config = ConfigLerSiteFirecrawl
    Args = ArgsLerSiteFirecrawl
    campos_secretos = ("chave_api",)
    chave_compartilhada = ("chave_api", "firecrawl")

    def executar(self, config: ConfigLerSiteFirecrawl, args: ArgsLerSiteFirecrawl) -> dict:
        chave = config.chave_api
        if not chave:
            raise FalhaInstrumento(
                "a leitura de site (Firecrawl) não está configurada — cadastre a chave "
                "Firecrawl em Chaves e credenciais da organização.",
                retentavel=False,
            )
        url = args.url.strip()
        if not url:
            raise FalhaInstrumento(
                "a URL veio vazia — informe o endereço da página a ler.",
                retentavel=False,
            )

        corpo: dict[str, Any] = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": config.apenas_conteudo_principal,
        }
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(
                    URL_FIRECRAWL_SCRAPE,
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
                "a chave do Firecrawl foi recusada — verifique-a.", retentavel=False
            )
        if status == 429 or 500 <= status < 600:
            raise FalhaInstrumento(
                f"o serviço de leitura (Firecrawl) respondeu HTTP {status}.",
                retentavel=True,
            )
        if not resposta.is_success:
            raise FalhaInstrumento(
                f"a leitura (Firecrawl) falhou (HTTP {status}).", retentavel=False
            )

        dados: dict[str, Any] = resposta.json()
        bloco = dados.get("data") or {}
        conteudo = (bloco.get("markdown") or "")[: config.max_caracteres]
        if not conteudo:
            return {
                "ok": False,
                "url": url,
                "erro": "não consegui extrair o conteúdo desta página.",
            }
        titulo = (bloco.get("metadata") or {}).get("title")
        return {"ok": True, "url": url, "titulo": titulo, "conteudo": conteudo}


registrar(LerSiteFirecrawl())
