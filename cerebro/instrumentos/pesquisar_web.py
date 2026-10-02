"""Instrumento "Pesquisar na web" — a IA busca na internet e responde com as fontes.

Instrumento POR CAPACIDADE (decisão do maestro, 2026-10-02): o agente pede "pesquise
X"; QUAL IA faz a busca é configuração. Hoje só a Anthropic (ferramenta de busca que
roda nos servidores dela); OpenAI e Google entram depois como outra opção do mesmo
`provedor`, sem refazer agente nenhum.

Substitui as buscas de mercado que saíram dos prontos (Tavily, Exa) sem fornecedor de
fora: a chave é a de IA da organização. Custo real: US$ 10 por mil buscas + tokens,
medido pelo que a Anthropic informa. Só leitura.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from instrumentos import anthropic_servidor as srv
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

SISTEMA = (
    "Você pesquisa na web para outro agente de uma empresa brasileira. Busque o que "
    "for preciso, confira em mais de uma fonte quando o assunto pedir e responda em "
    "português, de forma objetiva, só com o que as fontes sustentam. Se não achar, "
    "diga claramente que não achou — nunca invente."
)


class ConfigPesquisa(BaseModel):
    provedor: Literal["anthropic"] = Field(
        default="anthropic", title="IA que faz a busca",
        description="Por enquanto, só a Anthropic.",
    )
    modelo: str = Field(
        default=srv.MODELO_PADRAO_WEB, title="Modelo da IA",
        description="O Haiku é o mais barato (cerca de US$ 0,02 por pesquisa). Modelos "
        "maiores aprofundam mais, mas custam até dez vezes mais.",
        json_schema_extra={"enum": srv.modelos_disponiveis()},
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

    @model_validator(mode="after")
    def _um_filtro_so(self) -> "ConfigPesquisa":
        if self.sites_preferidos and self.sites_bloqueados:
            raise ValueError(
                "Use “Buscar só nestes sites” ou “Nunca buscar nestes sites”, não os dois."
            )
        if self.modelo not in srv.modelos_disponiveis():
            raise ValueError(f"Modelo indisponível para a busca: {self.modelo}.")
        return self


class ArgsPesquisa(BaseModel):
    pergunta: str = Field(
        min_length=3,
        description="O que pesquisar, com o contexto necessário (período, região, "
        "o que interessa). Ex.: preço médio do aluguel em Campinas em 2026.",
    )


class PesquisarWeb(TipoInstrumento):
    tipo = "pesquisar_web"
    provedores_ia = ("anthropic",)
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
        busca, _ = srv.versoes(config.modelo)
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
            modelo=config.modelo, sistema=SISTEMA,
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


registrar(PesquisarWeb())
