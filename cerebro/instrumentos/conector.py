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

import base64
import json
import re
import unicodedata
from typing import Any, Literal

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

import certificados
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

    auth_tipo: Literal["nenhuma", "bearer", "cabecalho", "query", "basic", "oauth2"] = (
        "nenhuma"
    )
    auth_nome: str = Field(
        default="",
        description="Nome do cabeçalho/parâmetro que leva o segredo (para 'cabecalho'/'query').",
    )
    auth_usuario: str = Field(
        default="",
        description=(
            "Identificação não-secreta do par de autenticação: o USUÁRIO no Basic, "
            "o Client ID no OAuth 2.0."
        ),
    )
    auth_segredo: str = Field(
        default="",
        description=(
            "A metade secreta da autenticação (→ cofre): o token no Bearer, a chave "
            "no cabeçalho/query, a SENHA no Basic, o Client Secret no OAuth 2.0."
        ),
    )
    # OAuth 2.0 (client credentials): o Batuta troca usuário+segredo por um token
    # de acesso no endereço abaixo e o RENOVA sozinho antes de vencer.
    url_token: str = Field(
        default="", description="Endereço que emite o token (OAuth 2.0)."
    )
    escopo: str = Field(default="", description="Escopo pedido ao emitir o token.")
    # Certificado de cliente (mTLS) — vem da caixa-forte por referência a uma
    # credencial `certificado_mtls`, nunca digitado. Vale para TODAS as operações
    # do conector (é propriedade da conexão com o serviço, não de uma chamada).
    # Vazio = sem certificado, como sempre foi.
    certificado: str = Field(
        default="", description="Certificado de cliente em PEM (vem do cofre)."
    )
    chave_privada: str = Field(
        default="", description="Chave privada do certificado em PEM (vem do cofre)."
    )
    # OAuth do banco: acompanha a mesma credencial. O transporte não os usa; estão
    # aqui porque aceitar um tipo de credencial obriga a ter onde injetar cada
    # campo dele (regra conferida em test_tipos_credencial).
    client_id: str = Field(default="", description="Client ID do OAuth (vem do cofre).")
    client_secret: str = Field(
        default="", description="Client Secret do OAuth (vem do cofre)."
    )
    # Token de acesso obtido e renovado pela BORDA a partir da credencial mTLS
    # (ver `oauth_mtls`). Não se digita: chega pronto.
    access_token: str = Field(
        default="", description="Token de acesso OAuth (obtido automaticamente)."
    )
    operacoes: list[OperacaoConector] = Field(default_factory=list)
    # Metadados do Construtor — NÃO afetam a execução (o motor os ignora). A
    # descrição geral é referência humana; cada OPERAÇÃO tem a sua, que é a que o
    # agente lê por ferramenta. A categoria só agrupa/ajuda a achar o instrumento.
    descricao: str = Field(default="", description="Para que serve (referência humana).")
    categoria: str = Field(default="", description="Categoria para agrupar (cosmético).")


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
    campos_resposta: list[str], mtls: tuple[str, str] | None = None,
) -> dict:
    """A chamada HTTP em si — espelha o núcleo provado do `rest.py`: erros de
    transporte e 5xx/429 viram falha retentável; 401/403 falha não-retentável;
    2xx e demais 4xx (ex.: 404) voltam ao agente como dado.

    `mtls` é o par (certificado, chave) já materializado em arquivo, quando o
    conector tem certificado de cliente; None = chamada sem certificado."""
    try:
        with httpx.Client(timeout=TIMEOUT_S, cert=mtls) as cliente:
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
    if config.auth_tipo == "oauth2":
        # O segredo aqui é o Client Secret: quem vai no cabeçalho é o token que a
        # BORDA já trocou por ele (e renova sozinha). Sem token, a chamada sai sem
        # Authorization e o serviço responde 401 — com recado claro.
        if config.access_token:
            cabecalhos["Authorization"] = f"Bearer {config.access_token}"
    elif config.auth_tipo == "basic" and (config.auth_usuario or config.auth_segredo):
        par = f"{config.auth_usuario}:{config.auth_segredo}".encode()
        cabecalhos["Authorization"] = f"Basic {base64.b64encode(par).decode()}"
    elif config.auth_segredo:
        if config.auth_tipo == "bearer":
            cabecalhos["Authorization"] = f"Bearer {config.auth_segredo}"
        elif config.auth_tipo == "cabecalho":
            cabecalhos[config.auth_nome or "Authorization"] = config.auth_segredo
        elif config.auth_tipo == "query":
            params[config.auth_nome or "api_key"] = config.auth_segredo
    # Token vindo de uma CREDENCIAL da caixa-forte (o caminho antigo, preservado):
    # entra como Bearer quando a autenticação declarada não definiu nenhum.
    elif config.access_token:
        cabecalhos["Authorization"] = f"Bearer {config.access_token}"
    validar_cabecalhos_ascii(cabecalhos)

    # 4) certificado de cliente (mTLS), se a conexão tiver um: vale para toda
    # operação do conector. Os arquivos temporários morrem ao sair do contexto.
    with certificados.material_mtls(config.certificado, config.chave_privada) as par:
        return _chamar_http(
            op.metodo, url, cabecalhos, params, corpo or None, op.campos_resposta,
            mtls=par,
        )


# ───────────────────────── testar e detectar (Construtor) ─────────────────────────


def _registros_da_resposta(corpo: Any) -> list[dict]:
    """TODOS os registros (dicts) de uma resposta: o `response.results` do Bubble,
    uma lista no topo, `results` no topo, ou o próprio dict (um registro só).

    Varre TODOS — não só o primeiro — de propósito: o Bubble (e outras APIs) OMITE
    da resposta os campos VAZIOS de cada registro. Olhar só o primeiro perderia
    campos que estão preenchidos em outros registros. A união dá a lista completa."""
    if isinstance(corpo, dict):
        resp = corpo.get("response")
        if isinstance(resp, dict) and isinstance(resp.get("results"), list):
            return [r for r in resp["results"] if isinstance(r, dict)]
        if isinstance(corpo.get("results"), list):
            return [r for r in corpo["results"] if isinstance(r, dict)]
        return [corpo]
    if isinstance(corpo, list):
        return [r for r in corpo if isinstance(r, dict)]
    return []


def _tipo_amigavel(v: Any) -> str:
    if isinstance(v, bool):
        return "sim/não"
    if isinstance(v, (int, float)):
        return "número"
    if isinstance(v, str):
        return "texto"
    if isinstance(v, list):
        return "lista"
    if isinstance(v, dict):
        return "objeto"
    return "vazio"


def _exemplo(v: Any) -> Any:
    if isinstance(v, str):
        return v[:40] + ("…" if len(v) > 40 else "")
    if isinstance(v, bool) or isinstance(v, (int, float)):
        return v
    if isinstance(v, list):
        return f"lista ({len(v)})"
    if isinstance(v, dict):
        return "objeto"
    return None


def _detectar_campos(corpo: Any) -> list[dict]:
    """Os campos da resposta (nome + tipo amigável + exemplo), para o Construtor
    deixar o usuário marcar quais trazer (`campos_resposta`). Faz a UNIÃO dos campos
    de TODOS os registros retornados — porque o Bubble omite os vazios de cada um, e
    olhar só o primeiro perderia campos. Guarda o primeiro exemplo com valor de cada."""
    campos: dict[str, dict] = {}
    for registro in _registros_da_resposta(corpo):
        for k, v in registro.items():
            atual = campos.get(k)
            if atual is None:
                campos[k] = {"nome": k, "tipo": _tipo_amigavel(v), "exemplo": _exemplo(v)}
            elif atual["exemplo"] in (None, "") and v not in (None, ""):
                # um registro posterior tem valor onde o primeiro estava vazio: melhora
                campos[k] = {"nome": k, "tipo": _tipo_amigavel(v), "exemplo": _exemplo(v)}
    return list(campos.values())


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
    campos_secretos = (
        "auth_segredo", "certificado", "chave_privada", "client_secret",
        "access_token",
    )
    # O material de mTLS/OAuth é opcional: só APIs que o exigem o usam, e vazio
    # não pode virar "conector com segredo pendente".
    campos_secretos_opcionais = (
        "certificado", "chave_privada", "client_secret", "access_token",
    )
    # Caixa-forte: o conector aceita apontar para um certificado guardado no cofre
    # (o segredo não é digitado aqui nem passa pela IA).
    tipos_credencial_aceitos = ("certificado_mtls",)
    # Baseline seguro; a irreversibilidade REAL depende das operações (ver abaixo).
    acao_irreversivel = True
    # Fase 1 (o motor): o tipo é REAL e executável, mas fica FORA do dropdown de
    # criar instrumento da tela atual — seu formulário cru (lista de operações) só
    # faz sentido no Construtor de Instrumento (Fase 2). Até lá, invisível na UI.
    oculto_no_catalogo = True

    # Campos que a pessoa preenche no Construtor e que NÃO viram configuração: o
    # arquivo do certificado (e sua senha) só existem na hora de subir.
    _TRANSITORIOS = ("arquivo", "chave_arquivo", "senha_certificado")

    def normalizar_config(self, bruta: dict) -> dict:
        """Converte o ARQUIVO de certificado enviado pelo Construtor no par PEM
        que a conexão usa — para o instrumento ser completo sem passar pela
        caixa-forte. Sem arquivo, não mexe em nada (o certificado guardado antes
        é preservado, como todo campo secreto em branco).

        A senha do arquivo abre o `.pfx` e NÃO é guardada."""
        limpa = {k: v for k, v in bruta.items() if k not in self._TRANSITORIOS}
        arquivo = str(bruta.get("arquivo", "") or "").strip()
        if not arquivo:
            return limpa
        cert_pem, chave_pem, _titular, _expira = certificados.normalizar(
            arquivo,
            senha=str(bruta.get("senha_certificado", "") or ""),
            chave_b64=str(bruta.get("chave_arquivo", "") or ""),
        )
        return {**limpa, "certificado": cert_pem, "chave_privada": chave_pem}

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

    def testar_operacao(
        self, config: ConfigConector, nome_operacao: str, valores: dict
    ) -> dict:
        """Roda UMA operação com valores de exemplo (o "testar e detectar" do
        Construtor). Roda SEM o filtro `campos_resposta` — para mostrar a resposta
        inteira e detectar todos os campos, que é justamente o que o usuário vai
        escolher. Uma falha da chamada externa volta como dado (`ok=False`), não
        como erro do Batuta; operação inexistente levanta `FalhaInstrumento`."""
        op = next((o for o in config.operacoes if o.nome == nome_operacao), None)
        if op is None:
            raise FalhaInstrumento(
                f"operação '{nome_operacao}' não existe neste conector.", retentavel=False
            )
        op_cheia = op.model_copy(update={"campos_resposta": []})
        try:
            resultado = _executar_operacao(config, op_cheia, valores or {})
        except FalhaInstrumento as e:
            return {"ok": False, "erro": str(e), "status": None, "corpo": None,
                    "campos_detectados": []}
        return {**resultado, "campos_detectados": _detectar_campos(resultado.get("corpo"))}

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
