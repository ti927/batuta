"""Instrumento "Google Search Console: consultar" (só leitura).

Lê o desempenho do site no Google Search (cliques, impressões, CTR e posição
média), agrupado por consulta, página, país, dispositivo ou data. Usa a Search
Console API (`searchanalytics.query`) com o access_token da credencial `google`
(conectada por OAuth). O token é renovado sob demanda pela borda
(`google_oauth.garantir_token`), então o instrumento sempre recebe um válido.

Só leitura → não exige portão. Política de falha do encaixe: 401/403 não-retentável
(token/permissão), 429/5xx retentável (oscilação), demais 4xx não-retentável.
"""

from datetime import date, timedelta
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

API = "https://searchconsole.googleapis.com/webmasters/v3"
TIMEOUT_S = 30.0

# Dimensões aceitas pela API (a IA passa uma ou mais; o resto é filtrado).
DIMENSOES_VALIDAS = ("query", "page", "country", "device", "date", "searchAppearance")


def _detalhe_erro(resposta: httpx.Response) -> str:
    try:
        dados = resposta.json()
        if isinstance(dados, dict):
            erro = dados.get("error")
            if isinstance(erro, dict):
                return str(erro.get("message") or erro)[:200]
            return str(dados.get("message") or dados)[:200]
    except Exception:
        pass
    return (resposta.text or "sem detalhe").strip()[:200]


class ConfigSearchConsole(BaseModel):
    """Configuração fixa. `site_url` é a propriedade do Search Console (o humano
    escolhe qual site); os demais campos vêm da credencial `google` (a borda os
    injeta). Todos os campos da credencial precisam existir aqui, mesmo os não
    usados diretamente (refresh_token/escopos) — é o contrato da mescla na borda."""

    site_url: str = Field(
        default="",
        title="Site (propriedade do Search Console)",
        description="Como aparece no Search Console: 'sc-domain:seublog.com' (domínio "
        "inteiro) ou 'https://seublog.com/' (prefixo de URL).",
    )
    access_token: str = Field(
        default="", description="Token de acesso do Google (vem da credencial)."
    )
    refresh_token: str = Field(
        default="", description="Token de renovação do Google (vem da credencial)."
    )
    email: str = Field(default="", description="Conta Google (vem da credencial).")
    escopos: str = Field(
        default="", description="Permissões concedidas (vem da credencial)."
    )


class ArgsSearchConsole(BaseModel):
    """O que a IA passa: o período, como agrupar e quantas linhas."""

    dias: int = Field(
        default=28, ge=1, le=480,
        description="Período: os últimos N dias. O Search Console tem ~2-3 dias de "
        "atraso, então os dias mais recentes podem vir incompletos.",
    )
    dimensoes: list[str] = Field(
        default_factory=lambda: ["query"],
        description="Como agrupar os resultados: 'query' (consultas de busca), 'page' "
        "(páginas), 'country', 'device' ou 'date'. Uma ou mais.",
    )
    limite: int = Field(
        default=20, ge=1, le=1000, description="Quantas linhas trazer (1 a 1000)."
    )


class SearchConsoleConsultar(TipoInstrumento):
    tipo = "search_console"
    categoria = "Google"
    nome_exibicao = "Google Search Console: consultar"
    descricao = (
        "Lê o desempenho do site no Google (cliques, impressões, CTR e posição média), "
        "agrupado por consulta de busca, página, país, dispositivo ou data. Use para "
        "avaliar o SEO do blog. Só leitura."
    )
    Config = ConfigSearchConsole
    Args = ArgsSearchConsole
    campos_secretos = ("access_token",)
    tipos_credencial_aceitos = ("google",)

    def executar(self, config: ConfigSearchConsole, args: ArgsSearchConsole) -> dict:
        if not config.access_token:
            raise FalhaInstrumento(
                "o Google não está conectado — aponte para uma credencial 'google' "
                "(conecte a conta em Chaves e credenciais).",
                retentavel=False,
            )
        site = (config.site_url or "").strip()
        if not site:
            raise FalhaInstrumento(
                "falta informar o site (propriedade do Search Console) na configuração "
                "do instrumento — ex.: 'sc-domain:seublog.com'.",
                retentavel=False,
            )
        dims = [d for d in args.dimensoes if d in DIMENSOES_VALIDAS] or ["query"]
        fim = date.today()
        inicio = fim - timedelta(days=args.dias)
        corpo = {
            "startDate": inicio.isoformat(),
            "endDate": fim.isoformat(),
            "dimensions": dims,
            "rowLimit": args.limite,
        }
        url = f"{API}/sites/{quote(site, safe='')}/searchAnalytics/query"
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cli:
                r = cli.post(
                    url,
                    json=corpo,
                    headers={"Authorization": f"Bearer {config.access_token}"},
                )
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível falar com o Search Console: {e}", retentavel=True
            )
        status = r.status_code
        if status in (401, 403):
            raise FalhaInstrumento(
                f"o Google recusou a consulta (HTTP {status}): {_detalhe_erro(r)}. "
                "Verifique se a conta conectada tem acesso a esta propriedade no Search "
                "Console e se o Google foi conectado incluindo o Search Console.",
                retentavel=False,
            )
        if status == 429 or 500 <= status < 600:
            raise FalhaInstrumento(
                f"o Search Console respondeu HTTP {status}.", retentavel=True
            )
        if not r.is_success:
            raise FalhaInstrumento(
                f"a consulta ao Search Console falhou (HTTP {status}): {_detalhe_erro(r)}",
                retentavel=False,
            )
        dados = r.json()
        linhas = [
            {
                "chaves": dict(zip(dims, linha.get("keys") or [])),
                "cliques": linha.get("clicks"),
                "impressoes": linha.get("impressions"),
                "ctr": linha.get("ctr"),
                "posicao": linha.get("position"),
            }
            for linha in (dados.get("rows") or [])
        ]
        return {
            "ok": True,
            "site": site,
            "periodo": {"de": inicio.isoformat(), "ate": fim.isoformat()},
            "dimensoes": dims,
            "linhas": linhas,
        }


registrar(SearchConsoleConsultar())
