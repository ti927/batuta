"""Instrumento "Gerar PDF/documento" (PRODUTO §13).

Produz um documento PDF (contrato, laudo, relatório, comunicado) a partir do
texto que a IA monta, e devolve um link para baixá-lo. No core o arquivo é
servido localmente pelo cérebro; na Etapa 2 migra para o Supabase Storage.
"""

import uuid

from fpdf import FPDF
from pydantic import BaseModel, Field

from arquivos import DIRETORIO_ARQUIVOS, url_do_arquivo
from instrumentos.base import TipoInstrumento, registrar


class ConfigPdf(BaseModel):
    """Sem configuração fixa — o conteúdo vem todo da IA ao acionar."""


class ArgsPdf(BaseModel):
    """O que a IA passa: o título e o corpo do documento."""

    titulo: str = Field(default="", description="Título do documento (opcional).")
    conteudo: str = Field(min_length=1, description="O corpo do documento, em texto.")


def _latin1(texto: str) -> str:
    """As fontes nativas do PDF cobrem latin-1 (inclui acentos do português).
    Caracteres fora disso (ex.: emojis) viram '?' para não quebrar a geração."""
    return texto.encode("latin-1", "replace").decode("latin-1")


class GerarPdf(TipoInstrumento):
    tipo = "gerar_pdf"
    nome_exibicao = "Gerar PDF/documento"
    descricao = (
        "Gera um documento PDF a partir de um título e um texto, e devolve um "
        "link para baixá-lo. Use para produzir contratos, laudos, relatórios ou "
        "comunicados."
    )
    Config = ConfigPdf
    Args = ArgsPdf

    def executar(self, config: ConfigPdf, args: ArgsPdf) -> dict:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        if args.titulo.strip():
            pdf.set_font("Helvetica", style="B", size=16)
            pdf.multi_cell(0, 10, _latin1(args.titulo.strip()))
            pdf.ln(4)
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 8, _latin1(args.conteudo))

        nome = f"{uuid.uuid4().hex}.pdf"
        pdf.output(str(DIRETORIO_ARQUIVOS / nome))
        return {"ok": True, "arquivo": nome, "url": url_do_arquivo(nome)}


registrar(GerarPdf())
