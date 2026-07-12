"""Instrumento "Descrever/ler imagem (visão)" — imagem entra, TEXTO sai.

O oposto do `gerar_imagem`/`montar_imagem` (que PRODUZEM imagem): aqui uma IA de
VISÃO (multimodal) LÊ uma ou mais imagens e devolve uma descrição em texto, para o
agente entender uma foto (ex.: o post de um comentário) e responder com contexto.

Multi-provedor SEM ramificar por provedor: usa `construir_modelo(config.modelo)`, que
monta o cliente do provedor certo (Anthropic/OpenAI/Google) e resolve a chave do
contexto `usar_chaves` — ativo durante a execução. Se o provedor do modelo escolhido
não tem chave, `construir_modelo` levanta e viramos numa FalhaInstrumento clara. A
mensagem multimodal usa o bloco agnóstico do langchain v1
(`{"type":"image","base64":...,"mime_type":...}`), que serve aos 3 provedores.

O modelo é escolhido na config; o campo é marcado `ui:"modelo_ia"` para o formulário
mostrar só os modelos de provedores com chave (mesmo padrão do seletor do agente).
Sem segredo próprio (a chave vem do pool via contexto). Só leitura → sem portão.
"""

import base64

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar
from instrumentos.montar_imagem import _baixar  # download público + política de erro
from orquestracao.llm import construir_modelo, texto_da_resposta
from orquestracao.modelos_ia import MODELOS_POR_PROVEDOR

# Teto de imagens por leitura (carrossel) e de tamanho por imagem — falha rápida e
# clara em vez de um 400 críptico do provedor.
MAX_IMAGENS = 8
MAX_BYTES = 5_000_000  # ~5 MB

# Todos os modelos conhecidos são multimodais (leem imagem). O formulário filtra por
# provedor com chave; aqui a enum é a UNIÃO (validação no backend).
MODELOS_VISAO = [m for modelos in MODELOS_POR_PROVEDOR.values() for m in modelos]


def _mime_imagem(dados: bytes) -> str | None:
    """O tipo de imagem pela assinatura dos bytes (não confia no content-type, que o
    `_baixar` normaliza). None = não é uma imagem reconhecida (jpeg/png/gif/webp)."""
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    return None


class ConfigDescrever(BaseModel):
    modelo: str = Field(
        default="claude-haiku-4-5",
        title="Modelo de IA (visão)",
        description="Qual IA vai LER a imagem. Só aparecem os modelos de provedores "
        "com chave cadastrada na organização.",
        json_schema_extra={"enum": MODELOS_VISAO, "ui": "modelo_ia"},
    )


class ArgsDescrever(BaseModel):
    imagens_url: list[str] = Field(
        min_length=1,
        description="URLs PÚBLICAS da(s) imagem(ns) a ler (1 a 8). Num carrossel, "
        "passe todas. Para vídeo/reels, passe a URL da MINIATURA (não do vídeo).",
    )
    instrucao: str = Field(
        default="Descreva a imagem em detalhes, de forma objetiva.",
        description="O que você quer saber/extrair da(s) imagem(ns).",
    )


class DescreverImagem(TipoInstrumento):
    tipo = "descrever_imagem"
    categoria = "Conteúdo"
    nome_exibicao = "Descrever/ler imagem (visão)"
    descricao = (
        "Lê uma ou mais imagens com uma IA de visão e devolve uma DESCRIÇÃO em texto "
        "(o que aparece na imagem). Use para o agente entender uma foto — por exemplo, "
        "o post de um comentário — e responder com contexto. Escolha o modelo (só "
        "aparecem os provedores com chave). Só leitura."
    )
    Config = ConfigDescrever
    Args = ArgsDescrever

    def executar(self, config: ConfigDescrever, args: ArgsDescrever) -> dict:
        urls = [u.strip() for u in (args.imagens_url or []) if u and u.strip()]
        if not urls:
            raise FalhaInstrumento(
                "nenhuma imagem informada (passe ao menos uma URL pública).",
                retentavel=False,
            )
        if len(urls) > MAX_IMAGENS:
            raise FalhaInstrumento(
                f"no máximo {MAX_IMAGENS} imagens por leitura (recebi {len(urls)}).",
                retentavel=False,
            )

        # Fail-fast no provedor sem chave, ANTES de baixar as imagens.
        try:
            modelo = construir_modelo(config.modelo)
        except RuntimeError as e:
            raise FalhaInstrumento(str(e), retentavel=False)

        blocos: list[dict] = [{"type": "text", "text": args.instrucao}]
        for u in urls:
            conteudo, _ct = _baixar(u)  # bytes + política de erro (retentável/não)
            if len(conteudo) > MAX_BYTES:
                raise FalhaInstrumento(
                    f"a imagem é grande demais (> {MAX_BYTES // 1_000_000} MB): {u}",
                    retentavel=False,
                )
            mime = _mime_imagem(conteudo)
            if mime is None:
                raise FalhaInstrumento(
                    f"a URL não aponta para uma imagem (jpeg/png/gif/webp): {u}",
                    retentavel=False,
                )
            blocos.append(
                {
                    "type": "image",
                    "base64": base64.b64encode(conteudo).decode("ascii"),
                    "mime_type": mime,
                }
            )

        try:
            resposta = modelo.invoke([HumanMessage(content=blocos)])
        except Exception as e:
            raise FalhaInstrumento(
                f"a IA de visão falhou ao ler a imagem: {e}", retentavel=True
            )
        return {
            "ok": True,
            "descricao": texto_da_resposta(resposta),
            "modelo": config.modelo,
            "imagens": len(urls),
        }


registrar(DescreverImagem())
