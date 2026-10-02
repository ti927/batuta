"""Instrumento "Pesquisar na web" — a IA busca na internet e responde com as fontes.

Instrumento POR CAPACIDADE (decisão do maestro, 2026-10-02): o agente pede "pesquise
X"; QUAL IA faz a busca é configuração — o modelo escolhido (Anthropic ou OpenAI, cada
uma com a ferramenta de busca que roda nos servidores dela; `escolha_ia`).

Substitui as buscas de mercado que saíram dos prontos (Tavily, Exa) sem fornecedor de
fora: a chave é a de IA da organização. Custo real: US$ 10 por mil buscas + tokens,
medido pelo que a IA informa (na OpenAI, com o Luna, ~US$ 0,012 por pesquisa). Só leitura.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator

from instrumentos import anthropic_servidor as srv
from instrumentos import escolha_ia
from instrumentos import openai_servidor as oai
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

SISTEMA = (
    "Você pesquisa na web para outro agente de uma empresa brasileira. Busque o que "
    "for preciso, confira em mais de uma fonte quando o assunto pedir e responda em "
    "português, de forma objetiva, só com o que as fontes sustentam. Se não achar, "
    "diga claramente que não achou — nunca invente."
)
FUSO = ZoneInfo("America/Sao_Paulo")


def _sistema(desde: date | None) -> str:
    """As instruções com a DATA DE HOJE: sem ela o modelo não sabe que dia é e erra
    "notícias dos últimos 7 dias" (a busca da Anthropic não tem filtro de data). O
    `desde` vira regra — é filtro feito pelo modelo, não pela busca."""
    hoje = datetime.now(FUSO).strftime("%d/%m/%Y")
    texto = f"{SISTEMA}\n\nHoje é {hoje} (horário de São Paulo)."
    if desde:
        texto += (
            f" Use só fontes publicadas a partir de {desde.strftime('%d/%m/%Y')}; descarte "
            "as anteriores e diga claramente se sobrou pouco ou nada no período."
        )
    return texto


PADROES = {"anthropic": srv.MODELO_PADRAO_WEB, "openai": oai.MODELO_PADRAO_WEB}


class ConfigPesquisa(BaseModel):
    modelo: str = escolha_ia.campo_modelo(
        "Em branco, o Batuta usa o mais barato da IA com chave: GPT-5.6 Luna (cerca de "
        "US$ 0,01 por pesquisa) ou Claude Haiku (de US$ 0,02 a 0,05). Modelos maiores "
        "aprofundam mais, mas custam até dez vezes mais."
    )
    max_buscas: int = Field(
        default=5, ge=1, le=20, title="Máximo de buscas por pesquisa",
        description="Cada busca custa cerca de US$ 0,01.",
    )
    sites_preferidos: list[str] = Field(
        default_factory=list, title="Buscar só nestes sites",
        description="Ex.: gov.br, ibge.gov.br. Em branco = a web toda.",
    )
    sites_bloqueados: list[str] = Field(
        default_factory=list, title="Nunca buscar nestes sites",
        description="Não dá para usar junto com “Buscar só nestes sites”.",
    )

    @model_validator(mode="before")
    @classmethod
    def _provedor_antigo(cls, dados):
        return escolha_ia.de_provedor_antigo(dados, PADROES)

    @model_validator(mode="after")
    def _um_filtro_so(self) -> "ConfigPesquisa":
        if self.sites_preferidos and self.sites_bloqueados:
            raise ValueError(
                "Use “Buscar só nestes sites” ou “Nunca buscar nestes sites”, não os dois."
            )
        escolha_ia.validar(self.modelo, "a busca")
        return self


class ArgsPesquisa(BaseModel):
    pergunta: str = Field(
        min_length=3,
        description="O que pesquisar, com o contexto necessário (período, região, "
        "o que interessa). Ex.: preço médio do aluguel em Campinas em 2026.",
    )
    desde: date | None = Field(
        default=None,
        description="Opcional (AAAA-MM-DD): só usar fontes publicadas a partir desta data. "
        "Ex.: para 'notícias da última semana', a data de 7 dias atrás.",
    )


class PesquisarWeb(TipoInstrumento):
    tipo = "pesquisar_web"
    provedores_ia = escolha_ia.PROVEDORES
    categoria = "Pesquisa e leitura"
    nome_exibicao = "Pesquisar na web"
    descricao = (
        "Pesquisa na internet e devolve uma resposta em português com as fontes "
        "(título e link). Use para dados atuais: notícias, preços, concorrentes, "
        "referências. Só leitura."
    )
    Config = ConfigPesquisa
    Args = ArgsPesquisa

    def executar(self, config: ConfigPesquisa, args: ArgsPesquisa) -> dict:
        modelo = escolha_ia.resolver(config.modelo, PADROES)
        if escolha_ia.provedor(modelo) == "openai":
            return self._pela_openai(config, args, modelo)
        busca, _ = srv.versoes(modelo)
        ferramenta: dict = {
            "type": busca, "name": "web_search", "max_uses": config.max_buscas,
            "user_location": {"type": "approximate", "country": "BR",
                              "timezone": "America/Sao_Paulo"},
        }
        if config.sites_preferidos:
            ferramenta["allowed_domains"] = config.sites_preferidos
        if config.sites_bloqueados:
            ferramenta["blocked_domains"] = config.sites_bloqueados
        r = srv.chamar(
            modelo=modelo, sistema=_sistema(args.desde),
            conteudo=[{"type": "text", "text": args.pergunta}], ferramentas=[ferramenta],
        )
        if not r["texto"]:
            raise FalhaInstrumento("a pesquisa não trouxe resposta.", retentavel=True)
        return {
            "ok": True,
            "resposta": r["texto"],
            "fontes": srv.fontes(r["blocos"]),
            "avisos": r["erros"],
            "uso": r["uso"],
        }

    def _pela_openai(self, config: ConfigPesquisa, args: ArgsPesquisa, modelo: str) -> dict:
        ferramenta: dict = {
            "type": "web_search",
            "user_location": {"type": "approximate", "country": "BR",
                              "timezone": "America/Sao_Paulo"},
        }
        filtros = {}
        if config.sites_preferidos:
            filtros["allowed_domains"] = config.sites_preferidos
        if config.sites_bloqueados:
            filtros["blocked_domains"] = config.sites_bloqueados
        if filtros:
            ferramenta["filters"] = filtros
        r = oai.chamar(
            modelo=modelo, sistema=_sistema(args.desde),
            conteudo=[{"type": "input_text", "text": args.pergunta}], ferramentas=[ferramenta],
            include=["web_search_call.action.sources"], max_ferramentas=config.max_buscas,
        )
        if not r["texto"]:
            raise FalhaInstrumento("a pesquisa não trouxe resposta.", retentavel=True)
        return {
            "ok": True,
            "resposta": oai.sem_marca_no_texto(r["texto"]),
            "fontes": oai.fontes(r["itens"]),
            "avisos": r["erros"],
            "uso": r["uso"],
        }


registrar(PesquisarWeb())
