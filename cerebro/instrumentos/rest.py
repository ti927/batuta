"""Instrumento "Chamar API REST" (PRODUTO.md §13).

Faz uma requisição HTTP a um endereço configurado e devolve a resposta. A
configuração fixa (endereço, método, cabeçalhos) é definida por quem monta o
agente; os argumentos variáveis (parâmetros de query e corpo) são o que a IA
passa na hora de acionar.
"""

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import TipoInstrumento, registrar

# Limites de segurança para uma resposta — evita estourar memória/contexto.
TIMEOUT_S = 15.0
MAX_CORPO = 10_000


class ConfigRest(BaseModel):
    """Configuração fixa do instrumento, preenchida por quem monta o agente."""

    url: str = Field(min_length=1, description="Endereço do endpoint.")
    metodo: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    cabecalhos: dict[str, str] = Field(
        default_factory=dict, description="Cabeçalhos fixos (ex.: autenticação)."
    )


class ArgsRest(BaseModel):
    """Argumentos variáveis que a IA passa ao acionar o instrumento."""

    parametros_query: dict[str, Any] = Field(
        default_factory=dict, description="Parâmetros adicionados à query string."
    )
    corpo: dict[str, Any] | None = Field(
        default=None, description="Corpo JSON enviado (para POST/PUT/PATCH)."
    )


class ChamarApiRest(TipoInstrumento):
    tipo = "chamar_api_rest"
    nome_exibicao = "Chamar API REST"
    descricao = (
        "Faz uma requisição HTTP a uma API e devolve a resposta. Use para "
        "consultar ou enviar dados a um sistema externo pelo endereço configurado."
    )
    Config = ConfigRest
    Args = ArgsRest

    def executar(self, config: ConfigRest, args: ArgsRest) -> dict:
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.request(
                    config.metodo,
                    config.url,
                    headers=config.cabecalhos or None,
                    params=args.parametros_query or None,
                    json=args.corpo,
                )
        except httpx.HTTPError as e:
            return {"ok": False, "erro": f"Falha na requisição: {e}"}

        # Tenta interpretar como JSON; se não der, devolve o texto truncado.
        try:
            corpo: Any = resposta.json()
        except ValueError:
            corpo = resposta.text[:MAX_CORPO]

        return {
            "ok": resposta.is_success,
            "status": resposta.status_code,
            "corpo": corpo,
        }


registrar(ChamarApiRest())
