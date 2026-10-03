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


def _pegar(valor: Any, caminho: str) -> tuple[bool, Any]:
    """Segue `caminho` dentro de `valor` e devolve (achou, recorte). O NOME INTEIRO vale
    primeiro: o Bubble tem campos com ponto no próprio nome (`cpo.NomeCliente`), que não
    podem virar "campo NomeCliente dentro de cpo". Só quando a chave inteira não existe
    o ponto separa níveis (`analytics.views`). `[]` diz que ali há uma lista e o resto
    do caminho vale para CADA item (`platforms[].status`). O recorte mantém a estrutura
    (`{"analytics": {"views": 10}}`), para o agente reconhecer de onde veio."""
    if not caminho:
        return True, valor
    if isinstance(valor, list):
        itens = [_pegar(item, caminho) for item in valor]
        return any(a for a, _ in itens), [r for a, r in itens if a]
    if not isinstance(valor, dict):
        return False, None
    if caminho in valor:
        return True, {caminho: valor[caminho]}
    partes = caminho.split(".")
    for corte in range(len(partes) - 1, 0, -1):
        chave, resto = ".".join(partes[:corte]), ".".join(partes[corte:])
        lista = chave.endswith("[]")
        chave = chave[:-2] if lista else chave
        if chave in valor:
            achou, recorte = _pegar(valor[chave], resto)
            return (True, {chave: recorte}) if achou else (False, None)
    if caminho.endswith("[]") and caminho[:-2] in valor:
        return True, {caminho[:-2]: valor[caminho[:-2]]}
    return False, None


def _juntar(a: Any, b: Any) -> Any:
    """Funde dois recortes do MESMO valor (dois caminhos que passam pelo mesmo lugar)."""
    if isinstance(a, dict) and isinstance(b, dict):
        saida = dict(a)
        for k, v in b.items():
            saida[k] = _juntar(saida[k], v) if k in saida else v
        return saida
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [_juntar(x, y) for x, y in zip(a, b)]
    return b


def _recortar(valor: Any, caminhos: list[str]) -> tuple[bool, Any]:
    """Recorta `valor` aos `caminhos` (cada um pelo `_pegar`), fundindo os recortes."""
    achou_algum, saida = False, None
    for caminho in caminhos:
        achou, recorte = _pegar(valor, caminho)
        if achou:
            saida = recorte if not achou_algum else _juntar(saida, recorte)
            achou_algum = True
    return achou_algum, saida


def _vazio(valor: Any) -> bool:
    return valor in (None, {}, []) or (
        isinstance(valor, list) and all(_vazio(v) for v in valor)
    )


def _projetar_registros(corpo: Any, campos: list[str]) -> Any:
    """Mantém só os `campos` de uma resposta — corta o custo de respostas grandes (ex.:
    uma busca no Bubble que traz 14 registros × 30 campos, quando o agente usa 6).

    Três jeitos de escrever um campo (2026-10-02; os dois primeiros valem como sempre):
    - nome simples (`id`, `cpo.NomeCliente`): vale para CADA registro da lista que o
      Batuta reconhece sozinho — o `response.results` do Bubble, uma lista no topo, ou
      as chaves `results`, `rows`, `items`, `data`, `records`;
    - com ponto, dentro do registro (`analytics.views`): só aquele pedaço aninhado;
    - com `[]`, a partir da RAIZ da resposta (`posts[].id`, `posts[].platforms[].status`):
      diz qual é a lista, em qualquer nível — para APIs cuja lista tem outro nome (as
      respostas do Zernio voltavam inteiras, com o custo de tokens lá no alto). Com
      algum campo assim, a resposta inteira passa a ser só o que foi pedido.

    TRAVA CONTRA O ZERO ABSOLUTO (2026-09-22): se o filtro não casa com NADA que tem
    conteúdo, ele não está economizando — está apagando (o caso clássico é pedir a
    chave do contêiner, `rows`, em vez dos campos da linha; o agente, sem ter como
    saber, inventou explicação). Aí a resposta volta INTACTA: devolver inteiro custa
    tokens, apagar custa a verdade. Formato não reconhecido também volta intacto."""
    if any("[]" in c for c in campos):
        achou, recorte = _recortar(corpo, campos)
        return recorte if achou and not _vazio(recorte) else corpo

    def enxuga_lista(lista: list) -> list:
        enxuto = []
        for registro in lista:
            if isinstance(registro, dict):
                _, recorte = _recortar(registro, campos)
                enxuto.append(recorte or {})
            else:
                enxuto.append(registro)
        tinha = [r for r in lista if isinstance(r, dict) and r]
        if tinha and all(not e for r, e in zip(lista, enxuto) if isinstance(r, dict) and r):
            return list(lista)
        return enxuto

    registros = registros_da_resposta(corpo)
    return registros.trocar(enxuga_lista(registros.lista)) if registros else corpo


class _Registros:
    """Onde estão as linhas de uma resposta, e como devolvê-la com as linhas trocadas."""

    def __init__(self, lista: list, trocar):
        self.lista = lista
        self.trocar = trocar


def registros_da_resposta(corpo: Any) -> "_Registros | None":
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
    if campos and any("[]" in c for c in campos):
        achou, recorte = _recortar(corpo, campos)
        return not achou or _vazio(recorte)
    registros = registros_da_resposta(corpo)
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
    # Certificado de cliente (mTLS) — instrumento LEGADO: só quem já tinha o
    # certificado guardado no próprio instrumento o usa (o novo é o conector). É o que APIs
    # bancárias (Pix, boleto) exigem além do token. Vazio = chamada sem
    # certificado, como sempre foi.
    certificado: str = Field(
        default="", description="Certificado de cliente em PEM (vem do cofre)."
    )
    chave_privada: str = Field(
        default="", description="Chave privada do certificado em PEM (vem do cofre)."
    )
    # OAuth do banco: o transporte não os usa — quem os usa é o passo de
    # obter/renovar o token de acesso.
    client_id: str = Field(default="", description="Client ID do OAuth (vem do cofre).")
    client_secret: str = Field(
        default="", description="Client Secret do OAuth (vem do cofre)."
    )
    # Token de acesso obtido e renovado pela BORDA (ver `oauth_mtls`). Não se digita: chega pronto e vira o Authorization.
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
    # Substituído na CRIAÇÃO pelo conector (uma ou várias operações, editável no
    # Construtor). As instâncias que já existem seguem funcionando como sempre.
    substituido_por = "conector"
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
        # O token colado à mão manda; na falta dele, o obtido pela borda (OAuth
        # do banco). Nenhum dos dois = sem Authorization.
        bearer = config.token_bearer or config.access_token
        if bearer:
            cabecalhos["Authorization"] = f"Bearer {bearer}"
        validar_cabecalhos_ascii(cabecalhos)
        try:
            # mTLS: se houver certificado de cliente guardado, ele é
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
