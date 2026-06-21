"""Instrumento "Montar imagem (a partir de fotos)".

Cria uma imagem NOVA combinando uma ou mais FOTOS-BASE (ex.: uma foto da pessoa
com fundo transparente, um produto, uma logo) com um TEMA descrito em texto,
preservando o rosto/produto das fotos. Use para montar a arte de um post com a
pessoa "dentro" da cena. Diferente do `gerar_imagem` (que cria do zero a partir só
de texto), aqui a IA passa também a(s) URL(s) da(s) foto(s)-base.

ORIGEM DAS FOTOS-BASE (importante): hoje a IA passa uma URL pública da foto. Quando
a BIBLIOTECA estiver no ar, as fotos-base virão de lá — a Biblioteca será acessível
ao agente, que escolherá entre vários modelos/fotos e passará a URL do escolhido a
este instrumento. O contrato (receber URL) já foi desenhado para isso: nada muda
neste instrumento quando a Biblioteca chegar. Ver `criacao/prompt.py`.

Usa a API de imagens da OpenAI no endpoint de EDIÇÃO/COMPOSIÇÃO
(`/v1/images/edits`, multipart): aceita até 16 imagens em `image[]` — a PRIMEIRA é
preservada com a maior fidelidade (textura/rosto), por isso a foto principal da
pessoa deve vir primeiro. O `input_fidelity: high` (suportado por gpt-image-1 e
gpt-image-1.5; NÃO por gpt-image-2/mini) reforça a fidelidade ao rosto da entrada.

A chave é um SEGREDO, reusada do pool da organização ("Chaves de IA") quando o
instrumento não tem chave própria (como o `gerar_imagem`). Reusa o `CATALOGO_IMAGEM`
do `gerar_imagem` como fonte única de modelos/validação; só muda os PADRÕES para a
montagem (gpt-image-1.5, retrato 1024x1536, qualidade alta). O custo (por imagem) é
contabilizado na borda — ver `medicao_instrumentos.TIPOS_PAGOS`.

Política de falha: transporte/5xx/429 são retentáveis; chave recusada (401/403),
configuração ausente e parâmetro inválido (4xx) não. Gerar imagem NÃO é irreversível
(não age no mundo externo), então NÃO exige portão e pode ser retentado com segurança.
"""

import uuid

import httpx
from pydantic import BaseModel, Field

import arquivos
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar
from instrumentos.gerar_imagem import (
    CATALOGO_IMAGEM,
    TIMEOUT_S,
    ConfigImagem,
    _QUALIDADES_GPT,
    _erro_openai,
    _imagem_bytes,
    _uniao_tamanhos,
)

URL_EDITS = "https://api.openai.com/v1/images/edits"

# Modelos que aceitam `input_fidelity` (reforça a fidelidade à imagem de entrada —
# essencial para preservar rosto). gpt-image-2 processa tudo em alta fidelidade
# sozinho (o parâmetro é recusado); gpt-image-1-mini não suporta.
MODELOS_COM_FIDELITY = {"gpt-image-1", "gpt-image-1.5"}

# Limite do endpoint de edição da OpenAI para a família gpt-image.
MAX_IMAGENS_BASE = 16

_EXT_POR_TIPO = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


class ConfigMontagem(ConfigImagem):
    """Mesma família e validação do `gerar_imagem` (catálogo único), mas com PADRÕES
    voltados à montagem com rosto: gpt-image-1.5 (aceita fidelidade alta à entrada),
    retrato 1024x1536 (bom pro feed/stories) e qualidade alta."""

    modelo: str = Field(
        default="gpt-image-1.5",
        title="Modelo da imagem",
        description=(
            "Modelo da família gpt-image. gpt-image-1.5 preserva melhor o "
            "rosto/produto da foto-base (fidelidade alta à entrada)."
        ),
        json_schema_extra={"enum": list(CATALOGO_IMAGEM)},
    )
    tamanho: str = Field(
        default="1024x1536",
        title="Tamanho",
        description="Resolução (as opções dependem do modelo). 1024x1536 = retrato, bom pro Instagram.",
        json_schema_extra={"enum": _uniao_tamanhos()},
    )
    qualidade: str = Field(
        default="high",
        title="Qualidade",
        description="low = rascunho; high = melhor acabamento (recomendado para montagem com rosto).",
        json_schema_extra={"enum": list(_QUALIDADES_GPT)},
    )


class ArgsMontagem(BaseModel):
    """O que a IA passa: o tema da montagem e a(s) URL(s) da(s) foto(s)-base."""

    prompt: str = Field(
        min_length=1,
        description=(
            "O tema/instrução da montagem: como combinar a(s) foto(s)-base com a cena. "
            "Ex.: 'coloque a pessoa da foto num fundo de escritório moderno, estilo "
            "corporativo, com o texto X em destaque'."
        ),
    )
    imagens_url: list[str] = Field(
        min_length=1,
        description=(
            "URLs PÚBLICAS das fotos-base (1 a 16). A PRIMEIRA é a preservada com mais "
            "fidelidade (use a foto principal da pessoa/produto). Quando a Biblioteca "
            "estiver disponível, a URL virá de lá."
        ),
    )


def _ext(content_type: str) -> str:
    return _EXT_POR_TIPO.get(content_type, ".png")


def _baixar(url: str) -> tuple[bytes, str]:
    """Baixa a foto-base da URL pública e devolve (bytes, content_type). A Graph da
    OpenAI recebe os bytes no multipart — então é o CÉREBRO que precisa conseguir
    baixar a imagem (a URL tem de ser pública)."""
    try:
        r = httpx.get(url, timeout=TIMEOUT_S, follow_redirects=True)
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não consegui baixar a foto-base ({url}): {e}", retentavel=True
        )
    if not r.is_success:
        raise FalhaInstrumento(
            f"a foto-base não pôde ser baixada (HTTP {r.status_code}) — confira se a "
            f"URL é pública e está acessível: {url}",
            retentavel=(r.status_code == 429 or 500 <= r.status_code < 600),
        )
    ct = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    if not ct.startswith("image/"):
        ct = "image/png"
    return r.content, ct


class MontarImagem(TipoInstrumento):
    tipo = "montar_imagem"
    categoria = "Conteúdo"
    nome_exibicao = "Montar imagem (a partir de fotos)"
    descricao = (
        "Monta uma imagem NOVA combinando uma ou mais fotos-base (ex.: uma foto da "
        "pessoa com fundo transparente) com um tema descrito em texto, preservando o "
        "rosto/produto das fotos. Use para criar a arte de um post com a pessoa "
        "dentro da cena. Recebe a URL pública da(s) foto(s)-base (quando a Biblioteca "
        "estiver disponível, a URL virá de lá). A primeira foto é a mais preservada."
    )
    Config = ConfigMontagem
    Args = ArgsMontagem
    campos_secretos = ("chave_api",)
    # Reusa a chave OpenAI da organização ("Chaves de IA") quando não há chave própria.
    chave_compartilhada = ("chave_api", "openai")

    def dependencias_ui(self) -> dict:
        """Ao escolher o `modelo`, só aparecem os tamanhos/qualidades válidos dele
        (do catálogo) — mesmo mecanismo do `gerar_imagem`."""
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

    def executar(self, config: ConfigMontagem, args: ArgsMontagem) -> dict:
        if not config.chave_api:
            raise FalhaInstrumento(
                "falta a chave de API de imagem — configure-a no instrumento ou "
                "cadastre a chave OpenAI da organização em Chaves de IA.",
                retentavel=False,
            )
        urls = [u.strip() for u in args.imagens_url if u and u.strip()]
        if not urls:
            raise FalhaInstrumento(
                "nenhuma foto-base foi informada (passe ao menos uma URL pública).",
                retentavel=False,
            )
        if len(urls) > MAX_IMAGENS_BASE:
            raise FalhaInstrumento(
                f"no máximo {MAX_IMAGENS_BASE} fotos-base por montagem.",
                retentavel=False,
            )

        # Baixa as fotos-base (a OpenAI recebe os bytes no multipart, não a URL).
        envio = []
        for i, u in enumerate(urls):
            conteudo, ct = _baixar(u)
            envio.append(("image[]", (f"base{i}{_ext(ct)}", conteudo, ct)))

        data = {
            "model": config.modelo,
            "prompt": args.prompt,
            "size": config.tamanho,
            "quality": config.qualidade,
            "n": "1",
        }
        if config.modelo in MODELOS_COM_FIDELITY:
            data["input_fidelity"] = "high"
        headers = {"Authorization": f"Bearer {config.chave_api}"}
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(URL_EDITS, headers=headers, data=data, files=envio)
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível montar a imagem: {e}", retentavel=True
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
        nome = f"{uuid.uuid4().hex}.png"
        url = arquivos.salvar(nome, conteudo, "image/png")
        return {"ok": True, "arquivo": nome, "url": url}


registrar(MontarImagem())
