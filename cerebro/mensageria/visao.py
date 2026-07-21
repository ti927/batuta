"""Leitura de imagem por VISÃO na mensageria — uma foto vira texto antes de chegar
ao agente (espelha `transcricao.py`, que faz o mesmo com áudio).

Usa a IA de visão multimodal via `construir_modelo(modelo)` (monta o cliente do
provedor certo e resolve a chave do contexto `usar_chaves`, ativo no turno) — o MESMO
caminho do instrumento `descrever_imagem`. Fica isolada para o resto da mensageria não
conhecer o provedor. Não toca o núcleo de orquestração.
"""

import base64

from langchain_core.messages import HumanMessage

from orquestracao.llm import construir_modelo, texto_da_resposta

# Teto de tamanho por imagem — falha rápida e clara (o chamador cai no aviso gentil)
# em vez de um 400 críptico do provedor. Fotos do Telegram são comprimidas (bem menores);
# só protege contra uma imagem-documento fora do comum.
MAX_BYTES = 5_000_000  # ~5 MB

# Instrução padrão da leitura na borda: além de descrever, TRANSCREVE texto/números
# legíveis — é o que serve a um atendimento (ex.: ler um comprovante, um documento, um
# print) e lançar os dados adiante.
INSTRUCAO_PADRAO = (
    "Você é os olhos de um atendente. Descreva esta imagem de forma objetiva e útil: "
    "o que aparece e, se houver TEXTO ou NÚMEROS legíveis, TRANSCREVA-os fielmente."
)


def _mime(dados: bytes) -> str | None:
    """O tipo de imagem pela assinatura dos bytes. None = não é imagem reconhecida."""
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    return None


def descrever(
    imagem: bytes, modelo: str | None, *, instrucao: str = INSTRUCAO_PADRAO
) -> tuple[str, dict]:
    """Lê a imagem (bytes) e devolve `(texto, uso)`. Roda sob `usar_chaves` (o chamador
    ativa o contexto). Levanta em falha de tipo/rede/IA — o chamador trata (aviso
    gentil). `uso` é o `usage_metadata` da chamada (tokens), para a contabilização."""
    if len(imagem) > MAX_BYTES:
        raise ValueError(f"imagem grande demais (> {MAX_BYTES // 1_000_000} MB)")
    mime = _mime(imagem)
    if mime is None:
        raise ValueError("não é uma imagem reconhecida (jpeg/png/gif/webp)")
    blocos = [
        {"type": "text", "text": instrucao},
        {
            "type": "image",
            "base64": base64.b64encode(imagem).decode("ascii"),
            "mime_type": mime,
        },
    ]
    resposta = construir_modelo(modelo).invoke([HumanMessage(content=blocos)])
    return texto_da_resposta(resposta), (getattr(resposta, "usage_metadata", None) or {})
