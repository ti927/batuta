"""Instrumento "Ler página da web" — a IA abre um link e extrai o que o agente pediu.

Mesmo desenho do "Pesquisar na web" (por capacidade; hoje só a Anthropic, com a
ferramenta de leitura que roda nos servidores dela). Substitui o "Ler site" que saiu
dos prontos (Tavily/Firecrawl). Custo: só os tokens da página. Limites da Anthropic:
não executa JavaScript (site que só monta o conteúdo no navegador vem vazio), não
entra em página com login, e lê texto, HTML e PDF. Só leitura.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from instrumentos import anthropic_servidor as srv
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

SISTEMA = (
    "Você lê páginas da web para outro agente de uma empresa brasileira. Abra o "
    "endereço indicado, extraia exatamente o que foi pedido e responda em português. "
    "Se a página não tiver a informação, diga claramente — nunca invente."
)


class ConfigLeitura(BaseModel):
    provedor: Literal["anthropic"] = Field(
        default="anthropic", title="IA que lê a página",
        description="Por enquanto, só a Anthropic.",
    )
    modelo: str = Field(
        default=srv.MODELO_PADRAO_WEB, title="Modelo da IA",
        description="O Haiku é o mais barato e basta para extrair o que está na página.",
        json_schema_extra={"enum": srv.modelos_disponiveis()},
    )
    max_tamanho: int = Field(
        default=30000, ge=2000, le=150000, title="Limite de leitura por página",
        description="Quanto da página a IA lê, no máximo — 30 mil já cobre uma página "
        "longa. Serve para uma página enorme não disparar o custo.",
    )

    @model_validator(mode="after")
    def _modelo_valido(self) -> "ConfigLeitura":
        if self.modelo not in srv.modelos_disponiveis():
            raise ValueError(f"Modelo indisponível para a leitura: {self.modelo}.")
        return self


class ArgsLeitura(BaseModel):
    url: str = Field(min_length=8, description="O endereço completo da página (https://…).")
    o_que_extrair: str = Field(
        default="Resuma o conteúdo principal da página.",
        description="O que você quer da página. Ex.: a tabela de preços; a data e o "
        "local do evento; os 5 pontos principais do artigo.",
    )


class LerPagina(TipoInstrumento):
    tipo = "ler_pagina"
    provedores_ia = ("anthropic",)
    categoria = "Pesquisa e leitura"
    nome_exibicao = "Ler página da web"
    descricao = (
        "Abre um link e devolve, em português, o que você pediu da página (resumo, "
        "uma tabela, dados específicos). Não abre páginas com login nem sites que só "
        "funcionam com JavaScript. Só leitura."
    )
    Config = ConfigLeitura
    Args = ArgsLeitura

    def executar(self, config: ConfigLeitura, args: ArgsLeitura) -> dict:
        url = args.url.strip()
        if not url.lower().startswith(("http://", "https://")):
            raise FalhaInstrumento(
                "o endereço precisa começar com http:// ou https://.", retentavel=False
            )
        _, leitura = srv.versoes(config.modelo)
        # A ferramenta de leitura só abre endereços que JÁ estão na conversa: por isso
        # o link vai no texto do pedido (não basta o modelo "lembrar" dele).
        pedido = f"Endereço: {url}\n\nO que extrair: {args.o_que_extrair}"
        r = srv.chamar(
            modelo=config.modelo, sistema=SISTEMA,
            conteudo=[{"type": "text", "text": pedido}],
            ferramentas=[{
                "type": leitura, "name": "web_fetch", "max_uses": 3,
                "max_content_tokens": config.max_tamanho,
            }],
        )
        if not r["texto"]:
            raise FalhaInstrumento("a leitura da página não trouxe resposta.", retentavel=True)
        return {
            "ok": True,
            "url": url,
            "conteudo": r["texto"],
            "avisos": r["erros"],
            "uso": r["uso"],
        }


registrar(LerPagina())
