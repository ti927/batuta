"""Instrumento "Chamar API REST" (PRODUTO.md §13).

Faz uma requisição HTTP a um endereço configurado e devolve a resposta. A
configuração fixa (endereço, método, cabeçalhos) é definida por quem monta o
agente; os argumentos variáveis (parâmetros de query e corpo) são o que a IA
passa na hora de acionar.
"""

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import (
    FalhaInstrumento,
    TipoInstrumento,
    registrar,
    validar_cabecalhos_ascii,
)

# Limites de segurança para uma resposta — evita estourar memória/contexto.
TIMEOUT_S = 15.0
MAX_CORPO = 10_000


class ConfigRest(BaseModel):
    """Configuração fixa do instrumento, preenchida por quem monta o agente.
    `token_bearer` é SEGREDO (cofre, Fase 7-B): se preenchido, vira o cabeçalho
    `Authorization: Bearer <token>` — a forma segura de autenticar, em vez de
    deixar o segredo em claro em `cabecalhos`."""

    url: str = Field(min_length=1, description="Endereço do endpoint.")
    metodo: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    cabecalhos: dict[str, str] = Field(
        default_factory=dict,
        description="Cabeçalhos fixos não-secretos (não coloque segredos aqui).",
    )
    token_bearer: str = Field(
        default="",
        description="Token de autenticação (segredo) → cabeçalho Authorization Bearer.",
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
    categoria = "Integrações e dados"
    nome_exibicao = "Chamar API REST"
    descricao = (
        "Faz uma requisição HTTP a uma API e devolve a resposta. Use para "
        "consultar ou enviar dados a um sistema externo pelo endereço configurado."
    )
    Config = ConfigRest
    Args = ArgsRest
    campos_secretos = ("token_bearer",)
    tipos_credencial_aceitos = ("token_bearer",)
    # Baseline irreversível (default seguro), mas a irreversibilidade REAL depende
    # do método: uma leitura (GET/HEAD/OPTIONS) não muda nada e não exige portão.
    acao_irreversivel = True

    # Métodos HTTP que só LEEM — não mudam o estado do sistema externo.
    _METODOS_LEITURA = {"GET", "HEAD", "OPTIONS"}

    def irreversivel_para(self, configuracao: dict) -> bool:
        metodo = str((configuracao or {}).get("metodo", "GET")).upper()
        return metodo not in self._METODOS_LEITURA

    def executar(self, config: ConfigRest, args: ArgsRest) -> dict:
        cabecalhos = dict(config.cabecalhos or {})
        if config.token_bearer:
            cabecalhos["Authorization"] = f"Bearer {config.token_bearer}"
        validar_cabecalhos_ascii(cabecalhos)
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.request(
                    config.metodo,
                    config.url,
                    headers=cabecalhos or None,
                    params=args.parametros_query or None,
                    json=args.corpo,
                )
        except httpx.HTTPError as e:
            # Transporte: conexão recusada, DNS, timeout — transitório, vale retentar.
            raise FalhaInstrumento(
                f"não foi possível chamar {config.url}: {e}", retentavel=True
            )

        # Falhas de operação do sistema externo (PRODUTO §16) viram falha do
        # instrumento; respostas legítimas (2xx e demais 4xx, ex.: 404) voltam
        # ao agente como dado.
        status = resposta.status_code
        if status in (401, 403):
            raise FalhaInstrumento(
                f"acesso negado por {config.url} (HTTP {status}) — "
                "verifique a autenticação/chave.",
                retentavel=False,
            )
        if status == 429 or 500 <= status < 600:
            raise FalhaInstrumento(
                f"o sistema em {config.url} respondeu HTTP {status}.", retentavel=True
            )

        # Tenta interpretar como JSON; se não der, devolve o texto truncado.
        try:
            corpo: Any = resposta.json()
        except ValueError:
            corpo = resposta.text[:MAX_CORPO]

        return {
            "ok": resposta.is_success,
            "status": status,
            "corpo": corpo,
        }


registrar(ChamarApiRest())
