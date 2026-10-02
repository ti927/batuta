"""Instrumento "Ler documento (PDF)" — a IA lê um PDF (contrato, nota fiscal,
relatório) e responde à pergunta do agente, citando a página de onde tirou cada dado.

Por capacidade (hoje só a Anthropic, que lê o PDF inteiro: texto, tabelas e imagens
das páginas). O PDF vai por LINK PÚBLICO — a própria Anthropic o baixa. Com citações
ligadas, a resposta traz os trechos e as páginas que a sustentam: o agente (e quem
confere depois) sabe de onde veio cada dado. Custo: só os tokens (cada página custa
cerca de 1.500 a 3.000). Limites: 32 MB e 600 páginas. Só leitura.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from instrumentos import anthropic_servidor as srv
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

SISTEMA = (
    "Você lê documentos para outro agente de uma empresa brasileira. Responda em "
    "português, só com o que o documento diz. Se a informação não estiver no "
    "documento, diga claramente — nunca invente."
)


class ConfigDocumento(BaseModel):
    provedor: Literal["anthropic"] = Field(
        default="anthropic", title="IA que lê o documento",
        description="Por enquanto, só a Anthropic.",
    )
    modelo: str = Field(
        default=srv.MODELO_PADRAO, title="Modelo da IA",
        json_schema_extra={"enum": srv.modelos_disponiveis()},
    )

    @model_validator(mode="after")
    def _modelo_valido(self) -> "ConfigDocumento":
        if self.modelo not in srv.modelos_disponiveis():
            raise ValueError(f"Modelo indisponível para ler documentos: {self.modelo}.")
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


class LerDocumento(TipoInstrumento):
    tipo = "ler_documento"
    provedores_ia = ("anthropic",)
    categoria = "Pesquisa e leitura"
    nome_exibicao = "Ler documento (PDF)"
    descricao = (
        "Lê um PDF (contrato, nota fiscal, relatório) e responde à sua pergunta em "
        "português, citando os trechos e as páginas de onde tirou cada informação. "
        "Só leitura."
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
        r = srv.chamar(
            modelo=config.modelo, sistema=SISTEMA,
            conteudo=[
                {"type": "document", "source": {"type": "url", "url": url},
                 "citations": {"enabled": True}},
                {"type": "text", "text": args.pergunta},
            ],
            ferramentas=[],
        )
        if not r["texto"]:
            raise FalhaInstrumento("a leitura do documento não trouxe resposta.", retentavel=True)
        return {
            "ok": True,
            "resposta": r["texto"],
            "citacoes": srv.citacoes_de_documento(r["blocos"]),
            "uso": r["uso"],
        }


registrar(LerDocumento())
