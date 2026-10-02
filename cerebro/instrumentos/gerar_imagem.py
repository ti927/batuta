"""Instrumento "Gerar imagem" (PRODUTO §13; Fase adicional).

Gera uma imagem a partir de uma descrição (prompt) e devolve um link para vê-la.
Usa a API de imagens da OpenAI (família gpt-image) ou a do Google (Gemini Image,
desde 2026-10-02) — a IA sai do MODELO escolhido (`provedor` no catálogo). Na OpenAI
a chave é um SEGREDO (cofre da Fase 7-B), reusada do pool da organização quando o
instrumento não tem chave própria; no Google, a chave do Google do pool. O arquivo é salvo localmente e servido pelo cérebro em `/arquivos` (migra
para o Supabase Storage na fase de produção).

CATÁLOGO ÚNICO (`CATALOGO_IMAGEM`) é a fonte da verdade dos modelos e da
parametrização válida de cada um. Dele saem, SEM listas paralelas mantidas à mão:
as opções da tela, a validação do trio modelo×tamanho×qualidade, o payload por
modelo e as dependências de UI (escolher o modelo → só aparecem os tamanhos/
qualidades que funcionam). A OpenAI aposentou os DALL·E — só a família gpt-image é
oferecida (decisão do maestro 2026-06-18); instrumentos antigos com DALL·E se
auto-curam para o modelo padrão na execução, sem migração de banco.

Como a OpenAI muda os parâmetros aceitos com o tempo, o `executar` traduz o erro da
API num recado ACIONÁVEL (qual parâmetro/mensagem/código a OpenAI recusou) — é o
que diz o que ajustar no catálogo quando algo parar de valer.

Política de falha do encaixe (Tarefa 5.1): transporte/5xx/429 são retentáveis;
chave recusada (401/403), configuração ausente e parâmetro inválido (4xx) não.
"""

import base64
import uuid
from typing import Literal

import httpx
from pydantic import BaseModel, Field, model_validator

import arquivos
import diagnostico_imagem
from instrumentos import google_servidor as goo
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

# Geração de imagem pode demorar; damos folga no timeout.
TIMEOUT_S = 120.0
URL_OPENAI = "https://api.openai.com/v1/images/generations"

# Tamanhos e qualidades comuns à família gpt-image (1024x1024 é o padrão e vale
# para todos). gpt-image-2 aceita tamanhos livres; oferecemos presets confiáveis.
_QUALIDADES_GPT = ("low", "medium", "high")

# ── FONTE ÚNICA DA VERDADE: modelos de imagem e a parametrização válida de cada um ──
# Adicionar um modelo = uma entrada aqui (+ preço em precos.PRECOS_IMAGEM_USD; um
# teste-guarda garante que todo modelo do catálogo tem preço).
# gpt-image-2 e 2.5 aceitam tamanhos livres (múltiplos de 16, proporção 1:3..3:1);
# oferecemos presets confiáveis: os 3 padrão + 16:9/9:16 + 4:5 (feed do Instagram,
# normal e alta-res) + 5:4 paisagem.
_TAMANHOS_GPT_2 = (
    "1024x1024", "1536x1024", "1024x1536", "1536x864", "864x1536",
    "1024x1280", "1536x1920", "1280x1024",
)

# A OpenAI tira gpt-image-1 em 23/10/2026 e gpt-image-1-mini/1.5 em 01/12/2026
# (developers.openai.com/api/docs/deprecations); os substitutos são os 2.5. Os 2.5
# aceitam também xhigh/max, que ficam de fora até termos o preço por imagem deles.
# Google (Gemini Image — ai.google.dev/gemini-api/docs/image-generation): o "tamanho"
# é a PROPORÇÃO e a "qualidade" é a RESOLUÇÃO (1K/2K/4K; o Flash-Lite só faz 1K).
# Toda imagem do Google sai com a marca invisível SynthID.
_PROPORCOES_GOOGLE = ("1:1", "4:5", "9:16", "16:9", "3:4", "4:3", "5:4", "3:2", "2:3")
_RESOLUCOES_GOOGLE = ("1K", "2K", "4K")

CATALOGO_IMAGEM: dict[str, dict] = {
    "gpt-image-2": {
        "provedor": "openai",
        "rotulo": "GPT Image 2",
        "tamanhos": _TAMANHOS_GPT_2,
        "qualidades": _QUALIDADES_GPT,
    },
    "gpt-image-2.5-flare": {
        "provedor": "openai",
        "rotulo": "GPT Image 2.5 Flare (rápido, dia a dia)",
        "tamanhos": _TAMANHOS_GPT_2,
        "qualidades": _QUALIDADES_GPT,
    },
    "gpt-image-2.5-sunburst": {
        "provedor": "openai",
        "rotulo": "GPT Image 2.5 Sunburst (edição mais precisa)",
        "tamanhos": _TAMANHOS_GPT_2,
        "qualidades": _QUALIDADES_GPT,
    },
    "gemini-3.1-flash-image": {
        "provedor": "google",
        "rotulo": "Gemini 3.1 Flash Image (Google)",
        "tamanhos": _PROPORCOES_GOOGLE,
        "qualidades": _RESOLUCOES_GOOGLE,
        "max_referencias": 14,
    },
    "gemini-3.1-flash-lite-image": {
        "provedor": "google",
        "rotulo": "Gemini 3.1 Flash-Lite Image (Google, o mais barato)",
        "tamanhos": _PROPORCOES_GOOGLE,
        "qualidades": ("1K",),
        "max_referencias": 14,
    },
    "gemini-3-pro-image": {
        "provedor": "google",
        "rotulo": "Gemini 3 Pro Image (Google, acabamento superior)",
        "tamanhos": _PROPORCOES_GOOGLE,
        "qualidades": _RESOLUCOES_GOOGLE,
        "max_referencias": 14,
    },
}

MODELO_PADRAO = "gpt-image-2"
TAMANHO_PADRAO = "1024x1024"
QUALIDADE_PADRAO = "medium"

# Modelos APOSENTADOS pela OpenAI: instrumentos antigos configurados com eles se
# auto-curam para o padrão na execução (sem migração de banco).
MODELOS_LEGADOS = {"dall-e-2", "dall-e-3", "gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5"}


def _uniao_tamanhos() -> list[str]:
    """A união (sem repetir, ordem estável) de todos os tamanhos do catálogo — é o
    `enum` do campo `tamanho`; a UI o filtra por modelo via `dependencias_ui`."""
    return _uniao("tamanhos")


def _uniao(chave: str) -> list[str]:
    vistos: list[str] = []
    for spec in CATALOGO_IMAGEM.values():
        for t in spec[chave]:
            if t not in vistos:
                vistos.append(t)
    return vistos


def provedor_do_modelo(modelo: str) -> str:
    return (CATALOGO_IMAGEM.get(modelo) or {}).get("provedor", "openai")


class ConfigImagem(BaseModel):
    """Configuração fixa. `chave_api` é SEGREDO (cofre 7-B).

    `modelo`, `tamanho` e `qualidade` são conjuntos fechados derivados do
    `CATALOGO_IMAGEM` (a interface os mostra como dropdown, com tamanho/qualidade
    DEPENDENTES do modelo). O trio é validado abaixo contra o catálogo."""

    modelo: str = Field(
        default=MODELO_PADRAO,
        title="Modelo da imagem",
        description="GPT Image (OpenAI) ou Gemini Image (Google) — só funciona o da IA "
        "que tem chave na organização.",
        json_schema_extra={"enum": list(CATALOGO_IMAGEM)},
    )
    tamanho: str = Field(
        default=TAMANHO_PADRAO,
        title="Tamanho",
        description="Resolução (OpenAI) ou proporção (Google) — as opções dependem do modelo.",
        json_schema_extra={"enum": _uniao_tamanhos()},
    )
    qualidade: str = Field(
        default=QUALIDADE_PADRAO,
        title="Qualidade",
        description="OpenAI: low = rascunho rápido e barato; high = melhor acabamento (mais "
        "caro). Google: a resolução, 1K, 2K ou 4K (mais caro).",
        json_schema_extra={"enum": _uniao("qualidades")},
    )
    formato: Literal["png", "jpeg"] = Field(
        default="png",
        title="Formato do arquivo",
        description=(
            "png = sem perdas, mais pesado; jpeg = bem mais leve na MESMA resolução "
            "(evita a recusa de upload por tamanho, ex.: o erro 413 do WordPress)."
        ),
    )
    chave_api: str = Field(
        default="",
        title="Chave da API (opcional)",
        description="Chave da API de imagem (segredo).",
    )

    @model_validator(mode="before")
    @classmethod
    def _curar_modelo_legado(cls, dados):
        """Instrumento antigo com modelo APOSENTADO (DALL·E, gpt-image-1…) → cai no padrão, com
        tamanho/qualidade ajustados para valores válidos do novo modelo. Assim os
        instrumentos legados voltam a funcionar sem mexer no banco (a config no
        banco continua a antiga; a cura acontece ao validar para usar)."""
        if not isinstance(dados, dict):
            return dados
        if "provedor" in dados:  # campo antigo: a IA agora sai do modelo
            dados = {k: v for k, v in dados.items() if k != "provedor"}
        if dados.get("modelo") in MODELOS_LEGADOS:
            dados = dict(dados)
            spec = CATALOGO_IMAGEM[MODELO_PADRAO]
            dados["modelo"] = MODELO_PADRAO
            if dados.get("tamanho") not in spec["tamanhos"]:
                dados["tamanho"] = TAMANHO_PADRAO
            if dados.get("qualidade") not in spec["qualidades"]:
                dados["qualidade"] = QUALIDADE_PADRAO
        return dados

    @model_validator(mode="after")
    def _validar_combinacao(self) -> "ConfigImagem":
        """O trio modelo×tamanho×qualidade precisa ser válido no catálogo — senão a
        OpenAI recusaria com um erro cru. Avisa claro já ao salvar/usar (é também o
        backstop para a IA criadora)."""
        spec = CATALOGO_IMAGEM.get(self.modelo)
        if spec is None:
            raise ValueError(
                f"Modelo de imagem desconhecido: '{self.modelo}'. "
                f"Use um destes: {', '.join(CATALOGO_IMAGEM)}."
            )
        if self.tamanho not in spec["tamanhos"]:
            raise ValueError(
                f"O tamanho '{self.tamanho}' não vale para o modelo '{self.modelo}'. "
                f"Tamanhos válidos: {', '.join(spec['tamanhos'])}."
            )
        if self.qualidade not in spec["qualidades"]:
            raise ValueError(
                f"A qualidade '{self.qualidade}' não vale para o modelo '{self.modelo}'. "
                f"Qualidades válidas: {', '.join(spec['qualidades'])}."
            )
        return self


class ArgsImagem(BaseModel):
    """O que a IA passa: a descrição da imagem a gerar."""

    prompt: str = Field(min_length=1, description="Descrição da imagem a gerar.")


def _erro_openai(status: int, resposta) -> str:
    """Traduz o erro da OpenAI num recado ACIONÁVEL: qual parâmetro, mensagem e
    código a API recusou. É o que diz o que ajustar no catálogo quando a OpenAI
    mudar os parâmetros aceitos."""
    try:
        erro = (resposta.json() or {}).get("error") or {}
    except ValueError:
        erro = {}
    mensagem = (erro.get("message") or (resposta.text or "")[:500] or "sem detalhes.").strip()
    codigo = erro.get("code")
    param = erro.get("param")
    cabeca = f"a geração de imagem falhou (HTTP {status})"
    if param:
        cabeca += f" no parâmetro '{param}'"
    if codigo:
        mensagem = f"{mensagem} [{codigo}]"
    return f"{cabeca}: {mensagem}"


def _imagem_bytes(dados: dict) -> bytes:
    """Bytes da imagem da resposta — base64 (`b64_json`, padrão da família
    gpt-image) ou download da `url` temporária (modelos legados)."""
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


def gerar_pelo_google(
    config: ConfigImagem, prompt: str, referencias: list[tuple[bytes, str]] = (),
) -> tuple[bytes, str, str]:
    """Gera (ou monta, com `referencias`) uma imagem no Google. Devolve (bytes, tipo,
    extensão). O formato do arquivo segue a config (png/jpeg)."""
    from google.genai import errors
    from google.genai import types as gtypes

    mime, ext = ("image/jpeg", ".jpg") if config.formato == "jpeg" else ("image/png", ".png")
    partes: list = [gtypes.Part.from_bytes(data=b, mime_type=t) for b, t in referencias]
    partes.append(prompt)
    cli = goo.cliente(TIMEOUT_S)
    try:
        resposta = cli.models.generate_content(
            model=config.modelo, contents=partes,
            config=gtypes.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=gtypes.ImageConfig(
                    aspect_ratio=config.tamanho, image_size=config.qualidade,
                    output_mime_type=mime,
                ),
            ),
        )
    except errors.APIError as e:
        raise goo.traduzir_excecao(e, config.modelo) from e
    except Exception as e:
        raise FalhaInstrumento(
            f"o Google não respondeu a tempo ({type(e).__name__}); tente de novo em instantes.",
            retentavel=True, codigo="ia.indisponivel",
        ) from e
    for candidato in resposta.candidates or []:
        for parte in getattr(candidato.content, "parts", None) or []:
            dados = getattr(parte, "inline_data", None)
            if dados and dados.data:
                return dados.data, dados.mime_type or mime, ext
    motivo = (resposta.candidates or [None])[0]
    motivo = str(getattr(motivo, "finish_reason", "") or "")
    raise FalhaInstrumento(
        "o Google não gerou a imagem"
        + (" (recusou por política de segurança — reescreva a descrição)" if motivo and "STOP" not in motivo else "")
        + ".",
        retentavel=False, codigo="ia.recusa" if motivo and "STOP" not in motivo else "google.sem_imagem",
    )


class GerarImagem(TipoInstrumento):
    tipo = "gerar_imagem"
    # Só existe para a organização que tem a chave da OpenAI ou a do Google.
    provedores_ia = ("openai", "google")
    categoria = "Conteúdo"
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

    def dependencias_ui(self) -> dict:
        """Dependências da tela: ao escolher o `modelo`, só aparecem os tamanhos e
        as qualidades válidos dele (do catálogo). Mecanismo genérico — ver
        `TipoInstrumento.dependencias_ui`."""
        return {
            "tamanho": {
                "controlado_por": "modelo",
                "opcoes": {m: list(s["tamanhos"]) for m, s in CATALOGO_IMAGEM.items()},
            },
            "qualidade": {
                "controlado_por": "modelo",
                "opcoes": {m: list(s["qualidades"]) for m, s in CATALOGO_IMAGEM.items()},
            },
        }

    def executar(self, config: ConfigImagem, args: ArgsImagem) -> dict:
        if provedor_do_modelo(config.modelo) == "google":
            conteudo, mime, ext = gerar_pelo_google(config, args.prompt)
            nome = f"{uuid.uuid4().hex}{ext}"
            return {"ok": True, "arquivo": nome, "url": arquivos.salvar(nome, conteudo, mime)}
        if not config.chave_api:
            raise FalhaInstrumento(
                "falta a chave de API de imagem — configure-a no instrumento, cadastre a "
                "chave OpenAI da organização em Chaves de IA, ou escolha um modelo do "
                "Google neste instrumento.",
                retentavel=False,
            )
        # Payload por modelo, a partir do catálogo. NÃO enviamos `response_format`:
        # a família gpt-image sempre devolve base64 (e o legado, url — ambos tratados).
        corpo = {
            "model": config.modelo,
            "prompt": args.prompt,
            "size": config.tamanho,
            "quality": config.qualidade,
            "n": 1,
        }
        # Formato de saída: a própria OpenAI devolve o b64 já no formato pedido
        # (`output_format`). Só enviamos o parâmetro para JPEG — PNG é o padrão da
        # família gpt-image, então o caminho PNG segue byte-idêntico ao de antes.
        ext, mime = (".jpg", "image/jpeg") if config.formato == "jpeg" else (".png", "image/png")
        if config.formato == "jpeg":
            corpo["output_format"] = "jpeg"
        # VIGIA: registra o que SERÁ transmitido. Este instrumento é TEXTO→IMAGEM —
        # NÃO envia imagem de entrada (não há anexo); o diagnóstico deixa isso claro.
        diagnostico_imagem.registrar(
            "gerar_imagem",
            URL_OPENAI,
            "POST application/json",
            corpo,
            [],
            observacao=(
                "Instrumento TEXTO→IMAGEM: cria do zero a partir do texto, NÃO envia "
                "imagem de entrada (não existe anexo). Para montar com uma foto, use o "
                "instrumento 'Montar imagem (a partir de fotos)'."
            ),
        )

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
            raise FalhaInstrumento(_erro_openai(status, resposta), retentavel=False)

        dados = (resposta.json().get("data") or [{}])[0]
        conteudo = _imagem_bytes(dados)
        nome = f"{uuid.uuid4().hex}{ext}"
        url = arquivos.salvar(nome, conteudo, mime)
        return {"ok": True, "arquivo": nome, "url": url}


registrar(GerarImagem())
