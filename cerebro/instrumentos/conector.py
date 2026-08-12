"""Instrumento "Conector" — Framework de Instrumentos, Fase 1 (o motor).

Um CONECTOR é um instrumento DECLARATIVO que descreve VÁRIAS operações de uma
mesma API (ex.: "listar posts", "publicar", "apagar"). Cada operação declarada
vira UMA ferramenta no cinto do agente — pelo MESMO mecanismo `expandir_ferramentas`
que o MCP já usa em produção. Diferente do "Chamar API REST" (um endpoint por
instrumento), aqui um único instrumento reúne o conjunto de chamadas de um serviço.

É a fundação do framework self-service (docs/FRAMEWORK-INSTRUMENTOS.md): quem monta
o agente DECLARA a integração (dado, não código). A execução reaproveita o núcleo
HTTP e o corte de custo (`campos_resposta`) provados no `rest.py`; a autenticação
reusa o cofre de segredos (`auth_segredo` é campo secreto, cifrado, injetado só na
execução).

NESTA FATIA (o motor, sem tela) a irreversibilidade é CONSERVADORA por INSTRUMENTO:
se QUALQUER operação escreve (POST/PUT/PATCH/DELETE), o conector inteiro exige a
parede de aprovação (nunca deixa passar uma ação irreversível sem portão). Refinar o
portão operação-a-operação ("GET livre, POST gateado") exige um toque aditivo no
motor (`agente.py`) e vem numa fatia própria, aprovada à parte pela evolução dirigida.
"""

import json
import re
import unicodedata
from typing import Any, Literal

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from instrumentos.base import (
    FalhaInstrumento,
    TipoInstrumento,
    registrar,
    validar_cabecalhos_ascii,
)
# Reuso do corte de custo do REST (mesma projeção de campos por registro): uma
# fonte de verdade só, comportamento idêntico ao `campos_resposta` do rest.py.
from instrumentos.rest import _projetar_registros

# Limites de segurança de uma resposta — iguais ao rest.py (evita estourar contexto).
TIMEOUT_S = 15.0
MAX_CORPO = 10_000
# Métodos que só LEEM — não mudam o estado do sistema externo (base da parede).
_METODOS_LEITURA = {"GET", "HEAD", "OPTIONS"}


class CampoOperacao(BaseModel):
    """Um parâmetro de uma operação. O `papel` decide quem o preenche:
    - "ia": a IA preenche na hora de acionar (vira argumento da ferramenta);
    - "fixo": valor constante definido por quem monta (a IA nem o vê).

    O `destino` diz ONDE o valor entra na requisição: na query string, no corpo
    JSON, ou substituindo `[nome]` na URL (o padrão de colchete do Bubble)."""

    nome: str = Field(min_length=1)
    papel: Literal["ia", "fixo"] = "ia"
    destino: Literal["query", "corpo", "url"] = "query"
    valor: str = Field(default="", description="Valor fixo (quando papel='fixo').")
    descricao: str = Field(default="", description="Ajuda para a IA (quando papel='ia').")
    obrigatorio: bool = True


class OperacaoConector(BaseModel):
    """Uma chamada da API — vira uma ferramenta no cinto do agente."""

    nome: str = Field(min_length=1, description="Nome da operação (base do nome da ferramenta).")
    descricao: str = Field(default="", description="O que a operação faz (para a IA).")
    metodo: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    url: str = Field(
        min_length=1,
        description="Endereço do endpoint; pode conter [campos] substituídos por valores.",
    )
    cabecalhos: dict[str, str] = Field(
        default_factory=dict, description="Cabeçalhos fixos não-secretos desta operação."
    )
    campos: list[CampoOperacao] = Field(default_factory=list)
    campos_resposta: list[str] = Field(
        default_factory=list,
        description="Opcional. Traga só estes campos de cada registro da resposta (corta custo).",
    )


class ConfigConector(BaseModel):
    """Configuração de um conector: autenticação + a lista de operações.

    `auth_segredo` é SEGREDO (cofre): nunca vai para a `instrumentos.configuracao`
    em claro — é cifrado e injetado só na execução, como todos os campos secretos."""

    auth_tipo: Literal["nenhuma", "bearer", "cabecalho", "query"] = "nenhuma"
    auth_nome: str = Field(
        default="",
        description="Nome do cabeçalho/parâmetro que leva o segredo (para 'cabecalho'/'query').",
    )
    auth_segredo: str = Field(
        default="", description="Token/chave de autenticação (SEGREDO → cofre)."
    )
    operacoes: list[OperacaoConector] = Field(default_factory=list)


class ArgsConector(BaseModel):
    """O acionamento ISOLADO do conector não pede argumentos — só descreve as
    operações declaradas (cada uma é uma ferramenta pelo `expandir_ferramentas`)."""


# ───────────────────────────── nomes seguros ─────────────────────────────


def _nome_ferramenta(base: str) -> str:
    """Nome de ferramenta válido para a IA (^[a-zA-Z0-9_-]{1,64}$)."""
    b = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    b = re.sub(r"[^a-zA-Z0-9_-]+", "_", b).strip("_")[:64]
    return b or "operacao"


def _id_seguro(nome: str) -> str:
    """Identificador Python válido a partir de um nome de campo qualquer — para
    campos como 'cpo.NomeCliente' virarem argumento de ferramenta sem quebrar."""
    s = re.sub(r"\W+", "_", nome).strip("_")
    if not s or s[0].isdigit():
        s = "c_" + s
    return s[:60]


def _campos_ia_seguros(op: OperacaoConector) -> list[tuple[str, CampoOperacao]]:
    """Campos IA da operação, cada um com uma CHAVE segura e ÚNICA (identificador
    válido) para virar argumento da ferramenta. Determinístico — o construtor do
    esquema e o acionamento usam esta MESMA função, então as chaves batem."""
    vistos: set[str] = set()
    saida: list[tuple[str, CampoOperacao]] = []
    for c in op.campos:
        if c.papel != "ia":
            continue
        base = _id_seguro(c.nome)
        chave = base
        i = 2
        while chave in vistos:
            chave = f"{base}_{i}"
            i += 1
        vistos.add(chave)
        saida.append((chave, c))
    return saida


def _args_da_operacao(op: OperacaoConector) -> type[BaseModel]:
    """O esquema de argumentos da ferramenta: só os campos IA (os fixos a IA nem vê)."""
    campos: dict[str, tuple] = {}
    for chave, c in _campos_ia_seguros(op):
        ajuda = c.descricao or c.nome
        if c.obrigatorio:
            campos[chave] = (str, Field(description=ajuda))
        else:
            campos[chave] = (str | None, Field(default=None, description=ajuda))
    return create_model(f"ArgsOp_{_id_seguro(op.nome)}", **campos)


# ───────────────────────────── execução ─────────────────────────────


def _chamar_http(
    metodo: str, url: str, cabecalhos: dict, params: dict, corpo: dict | None,
    campos_resposta: list[str],
) -> dict:
    """A chamada HTTP em si — espelha o núcleo provado do `rest.py`: erros de
    transporte e 5xx/429 viram falha retentável; 401/403 falha não-retentável;
    2xx e demais 4xx (ex.: 404) voltam ao agente como dado."""
    try:
        with httpx.Client(timeout=TIMEOUT_S) as cliente:
            resposta = cliente.request(
                metodo, url, headers=cabecalhos or None, params=params or None, json=corpo
            )
    except httpx.HTTPError as e:
        raise FalhaInstrumento(f"não foi possível chamar {url}: {e}", retentavel=True)

    status = resposta.status_code
    if status in (401, 403):
        raise FalhaInstrumento(
            f"acesso negado por {url} (HTTP {status}) — verifique a autenticação/chave.",
            retentavel=False,
        )
    if status == 429 or 500 <= status < 600:
        raise FalhaInstrumento(f"o sistema em {url} respondeu HTTP {status}.", retentavel=True)

    try:
        corpo_resp: Any = resposta.json()
    except ValueError:
        corpo_resp = resposta.text[:MAX_CORPO]
    if campos_resposta:
        corpo_resp = _projetar_registros(corpo_resp, campos_resposta)
    return {"ok": resposta.is_success, "status": status, "corpo": corpo_resp}


def _executar_operacao(
    config: ConfigConector, op: OperacaoConector, valores_ia: dict
) -> dict:
    """Monta e executa UMA operação: coleta os valores (fixos + os da IA),
    distribui por destino (URL/query/corpo), aplica a autenticação e chama."""
    # 1) valores: fixos definidos por quem montou + os que a IA passou (IA sobrepõe).
    valores: dict[str, Any] = {c.nome: c.valor for c in op.campos if c.papel == "fixo"}
    valores.update(valores_ia)

    # 2) distribui por destino.
    url = op.url
    params: dict[str, Any] = {}
    corpo: dict[str, Any] = {}
    for c in op.campos:
        if c.nome not in valores:
            continue
        v = valores[c.nome]
        if c.destino == "url":
            url = url.replace(f"[{c.nome}]", str(v))
        elif c.destino == "corpo":
            corpo[c.nome] = v
        else:  # query
            params[c.nome] = v

    # 3) autenticação (declarativa, reusa o segredo do cofre).
    cabecalhos = dict(op.cabecalhos or {})
    if config.auth_segredo:
        if config.auth_tipo == "bearer":
            cabecalhos["Authorization"] = f"Bearer {config.auth_segredo}"
        elif config.auth_tipo == "cabecalho":
            cabecalhos[config.auth_nome or "Authorization"] = config.auth_segredo
        elif config.auth_tipo == "query":
            params[config.auth_nome or "api_key"] = config.auth_segredo
    validar_cabecalhos_ascii(cabecalhos)

    return _chamar_http(op.metodo, url, cabecalhos, params, corpo or None, op.campos_resposta)


class Conector(TipoInstrumento):
    tipo = "conector"
    categoria = "Integrações e dados"
    nome_exibicao = "Conector"
    descricao = (
        "Reúne várias operações de uma mesma API (listar, criar, publicar…), cada "
        "uma disponível como uma ação do agente. Configurado por declaração, sem código."
    )
    Config = ConfigConector
    Args = ArgsConector
    campos_secretos = ("auth_segredo",)
    # Baseline seguro; a irreversibilidade REAL depende das operações (ver abaixo).
    acao_irreversivel = True
    # Fase 1 (o motor): o tipo é REAL e executável, mas fica FORA do dropdown de
    # criar instrumento da tela atual — seu formulário cru (lista de operações) só
    # faz sentido no Construtor de Instrumento (Fase 2). Até lá, invisível na UI.
    oculto_no_catalogo = True

    def irreversivel_para(self, configuracao: dict) -> bool:
        """Conservador POR INSTRUMENTO nesta fatia: irreversível se QUALQUER operação
        escreve. Assim nenhuma ação de escrita passa sem a parede; o refino
        operação-a-operação vem numa fatia com toque aditivo no motor."""
        ops = (configuracao or {}).get("operacoes") or []
        return any(
            str((o or {}).get("metodo", "GET")).upper() not in _METODOS_LEITURA
            for o in ops
        )

    def executar(self, config: ConfigConector, args: ArgsConector) -> dict:
        """Acionamento isolado: descreve as operações (cada uma é uma ferramenta
        via `expandir_ferramentas`). Não chama nenhuma API."""
        return {
            "ok": True,
            "operacoes": [
                {"nome": o.nome, "metodo": o.metodo, "descricao": o.descricao}
                for o in config.operacoes
            ],
        }

    def expandir_ferramentas(self, config: ConfigConector) -> list:
        """Cada operação declarada vira uma ferramenta no cinto do agente."""
        return [self._ferramenta_de_operacao(config, op) for op in config.operacoes]

    def _ferramenta_de_operacao(
        self, config: ConfigConector, op: OperacaoConector
    ) -> StructuredTool:
        ArgsOp = _args_da_operacao(op)
        # chave segura (arg da IA) → nome real do campo (para query/corpo/URL).
        mapa = {chave: c.nome for chave, c in _campos_ia_seguros(op)}

        def acionar(**kwargs) -> str:
            valores_ia = {
                mapa[k]: v for k, v in kwargs.items() if k in mapa and v is not None
            }
            try:
                resultado = _executar_operacao(config, op, valores_ia)
            except FalhaInstrumento as e:
                return json.dumps(
                    {"ok": False, "erro": f"A operação '{op.nome}' falhou: {e}"},
                    ensure_ascii=False,
                )
            return json.dumps(resultado, ensure_ascii=False, default=str)

        return StructuredTool.from_function(
            func=acionar,
            name=_nome_ferramenta(op.nome),
            description=op.descricao or f"Operação {op.nome} do conector.",
            args_schema=ArgsOp,
        )


registrar(Conector())
