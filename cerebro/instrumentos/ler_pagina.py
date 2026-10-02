"""Instrumento "Ler página da web" — a IA abre um link e extrai o que o agente pediu.

Mesmo desenho do "Pesquisar na web" (por capacidade: o modelo escolhido diz qual IA lê
— a Anthropic, com a ferramenta de leitura dela, ou a OpenAI, com a busca dela, que
abre a página pedida). Substitui o "Ler site" que saiu dos prontos (Tavily/Firecrawl).
Custo: os tokens da página. Limites das duas: não executa JavaScript (site que só
monta o conteúdo no navegador vem vazio) e não entra em página com login. Só leitura.
"""

from pydantic import BaseModel, Field, model_validator

from instrumentos import anthropic_servidor as srv
from instrumentos import escolha_ia
from instrumentos import openai_servidor as oai
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

SISTEMA = (
    "Você lê páginas da web para outro agente de uma empresa brasileira. Abra o "
    "endereço indicado, extraia exatamente o que foi pedido e responda em português. "
    "Se a página não tiver a informação, diga claramente — nunca invente."
)
PADROES = {"anthropic": srv.MODELO_PADRAO_WEB, "openai": oai.MODELO_PADRAO_WEB}


class ConfigLeitura(BaseModel):
    modelo: str = escolha_ia.campo_modelo(
        "Em branco, o Batuta usa o mais barato da IA com chave (GPT-5.6 Luna ou Claude "
        "Haiku) — basta para extrair o que está na página."
    )
    max_tamanho: int = Field(
        default=30000, ge=2000, le=150000, title="Limite de leitura por página",
        description="Quanto da página a IA lê, no máximo — 30 mil já cobre uma página "
        "longa. Serve para uma página enorme não disparar o custo. Vale para os modelos "
        "da Anthropic.",
    )

    @model_validator(mode="before")
    @classmethod
    def _provedor_antigo(cls, dados):
        return escolha_ia.de_provedor_antigo(dados, PADROES)

    @model_validator(mode="after")
    def _modelo_valido(self) -> "ConfigLeitura":
        escolha_ia.validar(self.modelo, "a leitura")
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
    provedores_ia = escolha_ia.PROVEDORES
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
        modelo = escolha_ia.resolver(config.modelo, PADROES)
        # A ferramenta de leitura só abre endereços que JÁ estão na conversa: por isso
        # o link vai no texto do pedido (não basta o modelo "lembrar" dele).
        pedido = f"Endereço: {url}\n\nO que extrair: {args.o_que_extrair}"
        if escolha_ia.provedor(modelo) == "openai":
            return self._pela_openai(url, pedido, modelo)
        _, leitura = srv.versoes(modelo)
        r = srv.chamar(
            modelo=modelo, sistema=SISTEMA,
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

    def _pela_openai(self, url: str, pedido: str, modelo: str) -> dict:
        # Na OpenAI a leitura é a própria busca: o modelo abre a página pedida
        # (`open_page`). A regra "só esta página" vai nas instruções.
        r = oai.chamar(
            modelo=modelo,
            sistema=SISTEMA + " Abra exatamente o endereço indicado e use só essa página.",
            conteudo=[{"type": "input_text", "text": pedido}],
            ferramentas=[{"type": "web_search"}], max_ferramentas=3,
        )
        if not r["texto"]:
            raise FalhaInstrumento("a leitura da página não trouxe resposta.", retentavel=True)
        resultado = {
            "ok": True,
            "url": url,
            "conteudo": oai.sem_marca_no_texto(r["texto"]),
            "avisos": r["erros"],
            "uso": r["uso"],
        }
        abriu = any(
            i.get("type") == "web_search_call"
            and (i.get("action") or {}).get("type") in ("open_page", "find_in_page")
            for i in r["itens"]
        )
        if not abriu:
            # Respondeu sem abrir a página (de memória ou só buscando): o agente precisa
            # saber que a resposta pode não ter vindo dela.
            resultado["aviso"] = "A IA não abriu esta página; a resposta pode não ter vindo dela."
        return resultado


registrar(LerPagina())
