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
from observabilidade.escritor import registrar_evento  # TEMP-DIAG: remover após diagnóstico

# Limites de segurança para uma resposta — evita estourar memória/contexto.
TIMEOUT_S = 15.0
MAX_CORPO = 10_000


def _projetar_registros(corpo: Any, campos: list[str]) -> Any:
    """Mantém só `campos` em cada REGISTRO de uma resposta em lista — corta o custo
    de respostas grandes (ex.: uma busca no Bubble que traz 14 registros × 30 campos,
    quando o agente usa 6). Reconhece os formatos comuns: o `response.results` do
    Bubble, uma lista no topo, ou `results` no topo. Formato não reconhecido (ou item
    que não é dict) → devolve INTACTO: nunca quebra e nunca descarta dado por engano
    (o pior caso é não economizar). Campo ausente num registro simplesmente não vem."""
    conjunto = set(campos)

    def enxuga(registro: Any) -> Any:
        if isinstance(registro, dict):
            return {k: v for k, v in registro.items() if k in conjunto}
        return registro

    def enxuga_lista(lista: list) -> list:
        return [enxuga(r) for r in lista]

    if isinstance(corpo, dict):
        resp = corpo.get("response")
        if isinstance(resp, dict) and isinstance(resp.get("results"), list):
            return {**corpo, "response": {**resp, "results": enxuga_lista(resp["results"])}}
        if isinstance(corpo.get("results"), list):
            return {**corpo, "results": enxuga_lista(corpo["results"])}
    if isinstance(corpo, list):
        return enxuga_lista(corpo)
    return corpo


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
    campos_resposta: list[str] = Field(
        default_factory=list,
        title="Campos da resposta",
        description=(
            "Opcional. Traga só estes campos de cada registro da resposta — enxuga "
            "listas grandes e corta o custo de tokens do agente. "
            'Ex.: ["_id", "cpo.NomeCliente"]. Vazio = a resposta inteira (como hoje). '
            "Aplica-se a respostas em lista, inclusive o formato \"results\" do Bubble."
        ),
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

        # Filtro de campos (corte de custo): enxuga cada registro da resposta aos
        # campos escolhidos. Vazio = resposta inteira (retrocompatível). Feito ANTES
        # do diag para o `rest.diag` medir o tamanho JÁ reduzido (prova a economia).
        if config.campos_resposta:
            corpo = _projetar_registros(corpo, config.campos_resposta)

        # TEMP-DIAG (remover após diagnóstico de custo/constraints): registra O QUE o
        # agente enviou (query com o `constraints`, corpo do POST — que mostra a data) e
        # o TAMANHO da resposta (results_count/remaining revelam se a busca veio filtrada
        # ou trouxe a tabela inteira). Best-effort: nunca derruba a chamada.
        try:
            _resp = corpo.get("response") if isinstance(corpo, dict) else None
            _results = _resp.get("results") if isinstance(_resp, dict) else None
            registrar_evento(
                categoria="instrumento",
                acao="rest.diag",
                persistir=True,
                detalhe={
                    "url": config.url,
                    "metodo": config.metodo,
                    "query": args.parametros_query or {},
                    "corpo_enviado": args.corpo,
                    "status": status,
                    "resposta_chars": len(str(corpo)),
                    "results_count": len(_results) if isinstance(_results, list) else None,
                    "remaining": _resp.get("remaining") if isinstance(_resp, dict) else None,
                },
            )
        except Exception:  # noqa: BLE001 — log de diagnóstico nunca pode derrubar a chamada
            pass

        return {
            "ok": resposta.is_success,
            "status": status,
            "corpo": corpo,
        }


registrar(ChamarApiRest())
