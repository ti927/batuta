"""Instrumento "Disparar webhook de saída" (PRODUTO §13).

Avisa/aciona um sistema externo: faz um POST a uma URL configurada, enviando o
conteúdo que a IA montar. É o par "de saída" do "Chamar API REST" — enquanto o
REST costuma consultar, este notifica/dispara.

Segue a mesma política de falha do encaixe (Tarefa 5.1): falha de transporte e
erros de servidor (5xx/429) são retentáveis; 401/403 não.
"""

from typing import Any

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 15.0
MAX_CORPO = 2_000


class ConfigWebhook(BaseModel):
    """Configuração fixa, preenchida por quem monta o agente. `token_bearer` é
    SEGREDO (cofre, Fase 7-B): se preenchido, vira o cabeçalho
    `Authorization: Bearer <token>`."""

    url: str = Field(min_length=1, description="Endereço que receberá o POST.")
    cabecalhos: dict[str, str] = Field(
        default_factory=dict,
        description="Cabeçalhos fixos não-secretos (não coloque segredos aqui).",
    )
    token_bearer: str = Field(
        default="",
        description="Token de autenticação (segredo) → cabeçalho Authorization Bearer.",
    )


class ArgsWebhook(BaseModel):
    """O que a IA envia ao acionar: o corpo (payload) do webhook."""

    payload: dict[str, Any] = Field(
        default_factory=dict, description="Dados JSON enviados ao sistema externo."
    )


class DispararWebhook(TipoInstrumento):
    tipo = "disparar_webhook"
    nome_exibicao = "Disparar webhook de saída"
    descricao = (
        "Avisa um sistema externo enviando um POST com dados a uma URL "
        "configurada. Use para notificar, acionar ou registrar algo em outro "
        "sistema."
    )
    Config = ConfigWebhook
    Args = ArgsWebhook
    campos_secretos = ("token_bearer",)
    acao_irreversivel = True  # aciona sistema externo

    def executar(self, config: ConfigWebhook, args: ArgsWebhook) -> dict:
        cabecalhos = dict(config.cabecalhos or {})
        if config.token_bearer:
            cabecalhos["Authorization"] = f"Bearer {config.token_bearer}"
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(
                    config.url,
                    headers=cabecalhos or None,
                    json=args.payload,
                )
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível chamar {config.url}: {e}", retentavel=True
            )

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

        return {
            "ok": resposta.is_success,
            "status": status,
            "resposta": resposta.text[:MAX_CORPO],
        }


registrar(DispararWebhook())
