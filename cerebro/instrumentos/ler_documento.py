"""Instrumento "Ler documento (PDF)" — a IA lê um PDF (contrato, nota fiscal,
relatório) e responde à pergunta do agente.

Por capacidade: o modelo escolhido diz qual IA lê. Todas leem o PDF inteiro (texto,
tabelas e imagens das páginas) pelo LINK PÚBLICO — Anthropic e OpenAI baixam o
arquivo elas mesmas; para o Google, o Batuta baixa e manda junto (até 20 MB). Na
Anthropic, com citações ligadas, a resposta traz os trechos e as páginas que a
sustentam — o agente (e quem confere depois) sabe de onde veio cada dado; OpenAI e
Google não devolvem citações de PDF. Custo: só os tokens (cada página custa cerca de 1.500 a
3.000). Limites: 32 MB e 600 páginas na Anthropic. Só leitura.
"""

import httpx
from google.genai import types as gtypes
from pydantic import BaseModel, Field, model_validator

from instrumentos import anthropic_servidor as srv
from instrumentos import escolha_ia
from instrumentos import google_servidor as goo
from instrumentos import openai_servidor as oai
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

SISTEMA = (
    "Você lê documentos para outro agente de uma empresa brasileira. Responda em "
    "português, só com o que o documento diz. Se a informação não estiver no "
    "documento, diga claramente — nunca invente."
)
PADROES = {
    "anthropic": srv.MODELO_PADRAO, "openai": oai.MODELO_PADRAO, "google": goo.MODELO_PADRAO,
}
# O Google recebe o PDF dentro do pedido: até 20 MB por pedido.
MAX_BYTES_GOOGLE = 20_000_000
TIMEOUT_DOWNLOAD_S = 60.0


class ConfigDocumento(BaseModel):
    modelo: str = escolha_ia.campo_modelo(
        "Em branco, o Batuta usa um modelo preciso da IA com chave (Claude Sonnet 5, "
        "GPT-5.6 Terra ou Gemini 3.8 Flash). Só os modelos da Anthropic citam a página de "
        "cada informação."
    )

    @model_validator(mode="before")
    @classmethod
    def _provedor_antigo(cls, dados):
        return escolha_ia.de_provedor_antigo(dados, PADROES)

    @model_validator(mode="after")
    def _modelo_valido(self) -> "ConfigDocumento":
        escolha_ia.validar(self.modelo, "ler documentos")
        return self


class ArgsDocumento(BaseModel):
    url: str = Field(
        min_length=8,
        description="O link PÚBLICO do PDF (https://…). Um arquivo recebido pelo canal "
        "ou gerado por outro instrumento já vem com um link assim.",
    )
    pergunta: str = Field(
        default="Resuma o documento: do que se trata, partes envolvidas, valores e datas.",
        description="O que você quer saber do documento. Ex.: qual o valor total e o "
        "vencimento desta nota; quais as cláusulas de multa.",
    )


def _baixar_pdf(url: str) -> bytes:
    """Baixa o PDF para mandar ao Google (que não busca o link sozinho)."""
    try:
        r = httpx.get(url, timeout=TIMEOUT_DOWNLOAD_S, follow_redirects=True)
    except httpx.HTTPError as e:
        raise FalhaInstrumento(f"não consegui baixar o documento ({url}): {e}", retentavel=True) from e
    if r.status_code >= 400:
        raise FalhaInstrumento(
            f"o link do documento respondeu erro {r.status_code} — confira se é público: {url}",
            retentavel=r.status_code == 429 or r.status_code >= 500,
        )
    if len(r.content) > MAX_BYTES_GOOGLE:
        raise FalhaInstrumento(
            f"o documento passa de {MAX_BYTES_GOOGLE // 1_000_000} MB, o limite da IA do Google; "
            "escolha um modelo da Anthropic ou da OpenAI neste instrumento.",
            retentavel=False,
        )
    if not r.content.startswith(b"%PDF"):
        raise FalhaInstrumento(f"o link não aponta para um PDF: {url}", retentavel=False)
    return r.content


class LerDocumento(TipoInstrumento):
    tipo = "ler_documento"
    provedores_ia = escolha_ia.TODAS
    categoria = "Pesquisa e leitura"
    nome_exibicao = "Ler documento (PDF)"
    descricao = (
        "Lê um PDF (contrato, nota fiscal, relatório) e responde à sua pergunta em "
        "português. Com um modelo da Anthropic, cita os trechos e as páginas de onde "
        "tirou cada informação. Só leitura."
    )
    Config = ConfigDocumento
    Args = ArgsDocumento

    def executar(self, config: ConfigDocumento, args: ArgsDocumento) -> dict:
        url = args.url.strip()
        if not url.lower().startswith("https://"):
            raise FalhaInstrumento(
                "o link do documento precisa ser público e começar com https://.",
                retentavel=False,
            )
        modelo = escolha_ia.resolver(config.modelo, PADROES)
        if escolha_ia.provedor(modelo) == "openai":
            r = oai.chamar(
                modelo=modelo, sistema=SISTEMA,
                conteudo=[
                    {"type": "input_file", "file_url": url},
                    {"type": "input_text", "text": args.pergunta},
                ],
                ferramentas=[],
            )
            citacoes: list[dict] = []
        elif escolha_ia.provedor(modelo) == "google":
            r = goo.chamar(
                modelo=modelo, sistema=SISTEMA,
                conteudo=[gtypes.Part.from_bytes(data=_baixar_pdf(url), mime_type="application/pdf"),
                          args.pergunta],
                ferramentas=[],
            )
            citacoes = []
        else:
            r = srv.chamar(
                modelo=modelo, sistema=SISTEMA,
                conteudo=[
                    {"type": "document", "source": {"type": "url", "url": url},
                     "citations": {"enabled": True}},
                    {"type": "text", "text": args.pergunta},
                ],
                ferramentas=[],
            )
            citacoes = srv.citacoes_de_documento(r["blocos"])
        if not r["texto"]:
            raise FalhaInstrumento("a leitura do documento não trouxe resposta.", retentavel=True)
        return {
            "ok": True,
            "resposta": r["texto"],
            "citacoes": citacoes,
            "uso": r["uso"],
        }


registrar(LerDocumento())
