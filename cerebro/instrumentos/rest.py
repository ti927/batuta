"""Instrumento "Chamar API REST" (PRODUTO.md §13).

Faz uma requisição HTTP a um endereço configurado e devolve a resposta. A
configuração fixa (endereço, método, cabeçalhos) é definida por quem monta o
agente; os argumentos variáveis (parâmetros de query e corpo) são o que a IA
passa na hora de acionar.
"""

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

import certificados
import http_saida
from instrumentos.base import (
    FalhaInstrumento,
    TipoInstrumento,
    registrar,
    validar_cabecalhos_ascii,
)

# Limites de segurança para uma resposta — evita estourar memória/contexto.
TIMEOUT_S = 15.0
MAX_CORPO = 10_000


def _projetar_registros(corpo: Any, campos: list[str]) -> Any:
    """Mantém só `campos` em cada REGISTRO de uma resposta em lista — corta o custo
    de respostas grandes (ex.: uma busca no Bubble que traz 14 registros × 30 campos,
    quando o agente usa 6). Reconhece os formatos comuns: o `response.results` do
    Bubble, uma lista no topo, e as chaves de lista usadas pelas APIs conhecidas
    (`results`, `rows`, `items`, `data`, `records`). Formato não reconhecido (ou item
    que não é dict) → devolve INTACTO: nunca quebra e nunca descarta dado por engano
    (o pior caso é não economizar). Campo ausente num registro simplesmente não vem."""
    conjunto = set(campos)

    def enxuga(registro: Any) -> Any:
        if isinstance(registro, dict):
            return {k: v for k, v in registro.items() if k in conjunto}
        return registro

    def enxuga_lista(lista: list) -> list:
        enxuto = [enxuga(r) for r in lista]
        # TRAVA CONTRA O ZERO ABSOLUTO (2026-09-22). Se o filtro esvaziou TODOS os
        # registros que tinham conteúdo, ele não está economizando — está apagando: os
        # nomes pedidos não existem em registro nenhum.
        #
        # É o caso clássico de pedir a chave do CONTÊINER em vez dos campos da linha.
        # No Search Console (`campos_resposta: ["rows", …]`) a resposta voltava 200 com
        # N linhas TODAS vazias, sem cliques nem impressões — e o agente, sem ter como
        # saber, inventou explicação ("falha de serialização do Google") e seguiu.
        # Filtro que não casa com nada é engano de configuração; devolver intacto custa
        # tokens, apagar custa a verdade.
        tinha = [r for r in lista if isinstance(r, dict) and r]
        if tinha and all(not enxuga(r) for r in tinha):
            return list(lista)
        return enxuto

    registros = _registros_da_resposta(corpo)
    return registros.trocar(enxuga_lista(registros.lista)) if registros else corpo


class _Registros:
    """Onde estão as linhas de uma resposta, e como devolvê-la com as linhas trocadas."""

    def __init__(self, lista: list, trocar):
        self.lista = lista
        self.trocar = trocar


def _registros_da_resposta(corpo: Any) -> "_Registros | None":
    """Acha a LISTA de registros de uma resposta — fonte única do formato, usada pelo
    filtro `campos_resposta` e pelo aviso do teste do conector (se cada um tivesse a
    sua lista de formatos, um dia eles discordariam em silêncio). `None` = formato não
    reconhecido."""
    if isinstance(corpo, dict):
        resp = corpo.get("response")
        if isinstance(resp, dict) and isinstance(resp.get("results"), list):
            return _Registros(
                resp["results"],
                lambda nova: {**corpo, "response": {**resp, "results": nova}},
            )
        # `rows` é o formato das APIs do Google (Search Console, BigQuery, Sheets);
        # `items`/`data`/`records` cobrem o resto do que se vê por aí. Antes só
        # `results` era reconhecido, então `campos_resposta` num conector do Google
        # não economizava NADA — e em silêncio, que é o pior jeito de não funcionar.
        for chave in ("results", "rows", "items", "data", "records"):
            if isinstance(corpo.get(chave), list):
                return _Registros(corpo[chave], lambda nova, c=chave: {**corpo, c: nova})
    if isinstance(corpo, list):
        return _Registros(corpo, lambda nova: nova)
    return None


def campos_resposta_nao_casam(corpo: Any, campos: list[str]) -> bool:
    """Os `campos` escolhidos não existem em NENHUM registro com conteúdo?

    É a pergunta certa para o aviso do teste. A anterior ("o filtro mudou a resposta?")
    dava alarme falso quando os campos escolhidos eram TODOS os da linha — o filtro
    guarda tudo, nada muda, e o aviso dizia que nada batia (visto em 2026-09-26 no
    Search Console, com `keys, clicks, impressions, ctr, position` certinhos)."""
    registros = _registros_da_resposta(corpo)
    if not registros or not campos:
        return False
    conjunto = set(campos)
    tinha = [r for r in registros.lista if isinstance(r, dict) and r]
    return bool(tinha) and not any(conjunto & r.keys() for r in tinha)


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
    # Certificado de cliente (mTLS) — chega da caixa-forte, por referência a uma
    # credencial do tipo `certificado_mtls`; NÃO se digita aqui. É o que APIs
    # bancárias (Pix, boleto) exigem além do token. Vazio = chamada sem
    # certificado, como sempre foi.
    certificado: str = Field(
        default="", description="Certificado de cliente em PEM (vem do cofre)."
    )
    chave_privada: str = Field(
        default="", description="Chave privada do certificado em PEM (vem do cofre)."
    )
    # OAuth do banco: vem junto da mesma credencial. O transporte (esta fatia) não
    # os usa — quem os usa é o passo de obter/renovar o token de acesso. Existem
    # aqui porque a credencial é UMA só: aceitar o tipo obriga a ter onde injetar
    # cada campo dele (regra conferida em test_tipos_credencial).
    client_id: str = Field(default="", description="Client ID do OAuth (vem do cofre).")
    client_secret: str = Field(
        default="", description="Client Secret do OAuth (vem do cofre)."
    )
    # Token de acesso obtido e renovado pela BORDA a partir da credencial mTLS
    # (ver `oauth_mtls`). Não se digita: chega pronto e vira o Authorization.
    access_token: str = Field(
        default="", description="Token de acesso OAuth (obtido automaticamente)."
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
    campos_secretos = (
        "token_bearer", "certificado", "chave_privada", "client_secret",
        "access_token",
    )
    # O material de mTLS/OAuth só existe para quem integra com API que o exige —
    # vazio não é pendência (senão todo REST nasceria "faltando certificado").
    campos_secretos_opcionais = (
        "certificado", "chave_privada", "client_secret", "access_token",
    )
    tipos_credencial_aceitos = ("token_bearer", "certificado_mtls")
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
        # O token colado à mão manda; na falta dele, o obtido pela borda a partir
        # da credencial mTLS (OAuth do banco). Nenhum dos dois = sem Authorization.
        bearer = config.token_bearer or config.access_token
        if bearer:
            cabecalhos["Authorization"] = f"Bearer {bearer}"
        validar_cabecalhos_ascii(cabecalhos)
        try:
            # mTLS: se houver certificado de cliente (credencial do cofre), ele é
            # apresentado no aperto de mão TLS. Sem certificado, `par` é None e a
            # chamada sai idêntica à de sempre.
            with certificados.material_mtls(
                config.certificado, config.chave_privada
            ) as par:
                with http_saida.cliente(timeout=TIMEOUT_S, cert=par) as cliente:
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
                http_saida.mensagem_de_rede(config.url, e), retentavel=True
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
        # campos escolhidos. Vazio = resposta inteira (retrocompatível).
        if config.campos_resposta:
            corpo = _projetar_registros(corpo, config.campos_resposta)

        return {
            "ok": resposta.is_success,
            "status": status,
            "corpo": corpo,
        }


registrar(ChamarApiRest())
