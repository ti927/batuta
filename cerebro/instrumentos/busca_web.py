"""Instrumento "Busca na web" (PRODUTO §13).

Dá ao agente informação atualizada da internet. Usa a API da Tavily, feita para
IA (resultados já resumidos). A chave vem do ambiente do cérebro
(`TAVILY_API_KEY`) — nunca do banco (CLAUDE §8); na Etapa 2, a chave por-cliente
passa para o cofre de segredos.

Segue a política de falha do encaixe (Tarefa 5.1): transporte/5xx/429 são
retentáveis; chave ausente/ inválida não.
"""

import os
from typing import Any

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 20.0
URL_TAVILY = "https://api.tavily.com/search"
# A Tavily recusa (HTTP 400) consultas acima de 400 caracteres. Truncamos para
# não estourar — uma consulta de busca não precisa ser maior que isso.
MAX_CONSULTA = 400


class ConfigBuscaWeb(BaseModel):
    """Configuração fixa. A chave NÃO fica aqui (vem do ambiente)."""

    max_resultados: int = Field(
        default=5, ge=1, le=10, description="Quantos resultados trazer (1 a 10)."
    )


class ArgsBuscaWeb(BaseModel):
    """O que a IA passa ao acionar: a consulta a buscar."""

    consulta: str = Field(min_length=1, description="O que buscar na web.")


class BuscaWeb(TipoInstrumento):
    tipo = "busca_web"
    nome_exibicao = "Busca na web"
    descricao = (
        "Busca informação atualizada na internet e devolve uma lista de "
        "resultados (título, link e um trecho). Use quando precisar de dados "
        "recentes ou que não estão na sua memória."
    )
    Config = ConfigBuscaWeb
    Args = ArgsBuscaWeb

    def executar(self, config: ConfigBuscaWeb, args: ArgsBuscaWeb) -> dict:
        chave = os.environ.get("TAVILY_API_KEY")
        if not chave:
            raise FalhaInstrumento(
                "a busca na web não está configurada (falta a chave TAVILY_API_KEY "
                "no cérebro).",
                retentavel=False,
            )

        corpo = {
            "api_key": chave,
            "query": args.consulta.strip()[:MAX_CONSULTA],
            "max_results": config.max_resultados,
            "search_depth": "basic",
        }
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
                f"a busca falhou (HTTP {status}).", retentavel=False
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
