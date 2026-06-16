"""Instrumento "Gerar imagem" (PRODUTO §13; Fase adicional).

Gera uma imagem a partir de uma descrição (prompt) e devolve um link para vê-la.
Usa a API de imagens da OpenAI; a chave é um SEGREDO (cofre da Fase 7-B). Como
o `gerar_pdf`, o arquivo é salvo localmente e servido pelo cérebro em `/arquivos`
(migra para o Supabase Storage na fase de produção).

Política de falha do encaixe (Tarefa 5.1): transporte/5xx/429 são retentáveis;
chave recusada (401/403) e configuração ausente não. O campo `provedor` fica
pronto para outros provedores; por ora, OpenAI.
"""

import base64
import uuid
from typing import Literal

import httpx
from pydantic import BaseModel, Field, model_validator

from arquivos import DIRETORIO_ARQUIVOS, url_do_arquivo
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

# Geração de imagem pode demorar; damos folga no timeout.
TIMEOUT_S = 120.0
URL_OPENAI = "https://api.openai.com/v1/images/generations"

# Tamanhos VÁLIDOS por modelo (fonte única da verdade da combinação modelo×tamanho).
# Espelha os tamanhos de `precos.PRECOS_IMAGEM_USD`. O campo `modelo`/`tamanho` da
# config é um `Literal` (vira dropdown na interface); este mapa valida o PAR — nem
# todo tamanho vale para todo modelo. `1024x1024` vale para os três (é o default).
TAMANHOS_POR_MODELO: dict[str, tuple[str, ...]] = {
    "gpt-image-1": ("1024x1024", "1024x1536", "1536x1024"),
    "dall-e-3": ("1024x1024", "1024x1792", "1792x1024"),
    "dall-e-2": ("1024x1024", "512x512", "256x256"),
}


class ConfigImagem(BaseModel):
    """Configuração fixa. `chave_api` é SEGREDO (cofre 7-B).

    `modelo` e `tamanho` são conjuntos fechados (`Literal`) — a interface os mostra
    como dropdown, em vez de texto livre. O par modelo×tamanho é validado abaixo
    (cada modelo aceita só alguns tamanhos)."""

    provedor: Literal["openai"] = Field(
        default="openai",
        title="Provedor",
        description="Provedor de geração de imagem (por ora, só OpenAI).",
    )
    # Mantido em sincronia com TAMANHOS_POR_MODELO (Literal exige valores estáticos).
    modelo: Literal["gpt-image-1", "dall-e-3", "dall-e-2"] = Field(
        default="gpt-image-1",
        title="Modelo da imagem",
        description="Modelo usado para gerar a imagem. gpt-image-1 é o mais novo da OpenAI.",
    )
    # União dos tamanhos válidos (1024x1024 primeiro/padrão, vale para todos).
    tamanho: Literal[
        "1024x1024", "1024x1536", "1536x1024", "1024x1792", "1792x1024", "512x512", "256x256"
    ] = Field(
        default="1024x1024",
        title="Tamanho",
        description="Tamanho da imagem. Atenção: o tamanho válido depende do modelo.",
    )
    chave_api: str = Field(
        default="",
        title="Chave da API (opcional)",
        description="Chave da API de imagem (segredo).",
    )

    @model_validator(mode="after")
    def _validar_tamanho_do_modelo(self) -> "ConfigImagem":
        """O tamanho precisa ser válido para o modelo escolhido — senão a OpenAI
        recusaria com um erro cru. Avisa claro já ao salvar o instrumento."""
        validos = TAMANHOS_POR_MODELO.get(self.modelo, ())
        if self.tamanho not in validos:
            raise ValueError(
                f"O tamanho '{self.tamanho}' não vale para o modelo '{self.modelo}'. "
                f"Tamanhos válidos: {', '.join(validos)}."
            )
        return self


class ArgsImagem(BaseModel):
    """O que a IA passa: a descrição da imagem a gerar."""

    prompt: str = Field(min_length=1, description="Descrição da imagem a gerar.")


def _imagem_bytes(dados: dict) -> bytes:
    """Extrai os bytes da imagem da resposta — seja em base64 (`b64_json`) ou por
    download da `url` temporária que alguns modelos devolvem."""
    b64 = dados.get("b64_json")
    if b64:
        return base64.b64decode(b64)
    url = dados.get("url")
    if url:
        try:
            r = httpx.get(url, timeout=TIMEOUT_S)
            r.raise_for_status()
            return r.content
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível baixar a imagem gerada: {e}", retentavel=True
            )
    raise FalhaInstrumento(
        "o serviço de imagem não devolveu a imagem.", retentavel=False
    )


class GerarImagem(TipoInstrumento):
    tipo = "gerar_imagem"
    nome_exibicao = "Gerar imagem"
    descricao = (
        "Gera uma imagem a partir de uma descrição (prompt) e devolve um link "
        "para vê-la. Use para ilustrar conteúdo, criar artes ou mockups."
    )
    Config = ConfigImagem
    Args = ArgsImagem
    campos_secretos = ("chave_api",)
    # Reusa a chave OpenAI da organização ("Chaves de IA") quando o instrumento não
    # tem uma chave própria — a borda a injeta. Ver instrumentos/base.py.
    chave_compartilhada = ("chave_api", "openai")

    def executar(self, config: ConfigImagem, args: ArgsImagem) -> dict:
        if not config.chave_api:
            raise FalhaInstrumento(
                "falta a chave de API de imagem — configure-a no instrumento ou "
                "cadastre a chave OpenAI da organização em Chaves de IA.",
                retentavel=False,
            )
        corpo = {
            "model": config.modelo,
            "prompt": args.prompt,
            "size": config.tamanho,
            "n": 1,
        }
        headers = {"Authorization": f"Bearer {config.chave_api}"}
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(URL_OPENAI, headers=headers, json=corpo)
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível gerar a imagem: {e}", retentavel=True
            )

        status = resposta.status_code
        if status in (401, 403):
            raise FalhaInstrumento(
                "a chave de API de imagem foi recusada — verifique-a.",
                retentavel=False,
            )
        if status == 429 or 500 <= status < 600:
            raise FalhaInstrumento(
                f"o serviço de imagem respondeu HTTP {status}.", retentavel=True
            )
        if not resposta.is_success:
            raise FalhaInstrumento(
                f"a geração de imagem falhou (HTTP {status}): {resposta.text[:300]}",
                retentavel=False,
            )

        dados = (resposta.json().get("data") or [{}])[0]
        conteudo = _imagem_bytes(dados)
        nome = f"{uuid.uuid4().hex}.png"
        (DIRETORIO_ARQUIVOS / nome).write_bytes(conteudo)
        return {"ok": True, "arquivo": nome, "url": url_do_arquivo(nome)}


registrar(GerarImagem())
