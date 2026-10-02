"""Instrumento "Ler página da web" — a IA abre um link e extrai o que o agente pediu.

Mesmo desenho do "Pesquisar na web" (por capacidade: o modelo escolhido diz qual IA lê
— a Anthropic, com a ferramenta de leitura dela; a OpenAI, com a busca dela, que abre
a página pedida; ou o Google, com a leitura de link dele, `url_context`). Substitui o "Ler site" que saiu dos prontos (Tavily/Firecrawl).
Custo: os tokens da página. Limites das duas: não executa JavaScript (site que só
monta o conteúdo no navegador vem vazio) e não entra em página com login. Só leitura.
"""

from html.parser import HTMLParser

import httpx
from google.genai import types as gtypes
from pydantic import BaseModel, Field, model_validator

from instrumentos import anthropic_servidor as srv
from instrumentos import escolha_ia
from instrumentos import google_servidor as goo
from instrumentos import openai_servidor as oai
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

SISTEMA = (
    "Você lê páginas da web para outro agente de uma empresa brasileira. Abra o "
    "endereço indicado, extraia exatamente o que foi pedido e responda em português. "
    "Se a página não tiver a informação, diga claramente — nunca invente."
)
TIMEOUT_DOWNLOAD_S = 30.0
NAVEGADOR = "Mozilla/5.0 (compatible; Batuta/1.0; +https://batuta.team)"
# Etiquetas cujo conteúdo não é texto da página.
_SEM_TEXTO = {"script", "style", "noscript", "svg", "template", "head"}


class _Texto(HTMLParser):
    """O texto visível de um HTML (sem script/estilo), com os links das âncoras —
    o bastante para a IA achar títulos, datas e endereços dos artigos."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._fora = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SEM_TEXTO:
            self._fora += 1
        elif tag == "a" and not self._fora:
            href = dict(attrs).get("href")
            if href and href.startswith("http"):
                self.partes.append(f" [{href}] ")
        elif tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr", "article", "time"):
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in _SEM_TEXTO and self._fora:
            self._fora -= 1

    def handle_data(self, data):
        if not self._fora and data.strip():
            self.partes.append(data.strip() + " ")


def texto_da_pagina(url: str, limite_caracteres: int) -> tuple[str, bool]:
    """Baixa a página AGORA e devolve (texto, cortado). Levanta FalhaInstrumento se ela
    não abrir. Feito pelo Batuta para a OpenAI porque a busca dela pode devolver uma
    cópia guardada (achado no uso real: o blog veio com os artigos de agosto como "os
    mais recentes", em 02/10/2026)."""
    try:
        r = httpx.get(url, timeout=TIMEOUT_DOWNLOAD_S, follow_redirects=True,
                      headers={"User-Agent": NAVEGADOR, "Accept-Language": "pt-BR,pt;q=0.9"})
    except httpx.HTTPError as e:
        raise FalhaInstrumento(f"a página não respondeu ({type(e).__name__}).", retentavel=True) from e
    if r.status_code in (401, 403):
        raise FalhaInstrumento(
            "a página não pôde ser aberta (exige login ou bloqueia robôs).",
            retentavel=False, codigo="pagina.inacessivel",
        )
    if r.status_code >= 400:
        raise FalhaInstrumento(
            f"a página respondeu erro {r.status_code}.",
            retentavel=r.status_code == 429 or r.status_code >= 500, codigo="pagina.inacessivel",
        )
    tipo = (r.headers.get("content-type") or "").lower()
    if "html" in tipo or "xml" in tipo:
        leitor = _Texto()
        leitor.feed(r.text)
        texto = "".join(leitor.partes)
    elif tipo.startswith("text/") or "json" in tipo:
        texto = r.text
    else:
        raise FalhaInstrumento(
            f"o endereço não é uma página de texto ({tipo or 'tipo desconhecido'}); para PDF, "
            "use o Ler documento.", retentavel=False,
        )
    texto = "\n".join(l.strip() for l in texto.splitlines() if l.strip())
    return texto[:limite_caracteres], len(texto) > limite_caracteres


PADROES = {
    "anthropic": srv.MODELO_PADRAO_WEB, "openai": oai.MODELO_PADRAO_WEB,
    "google": goo.MODELO_PADRAO_WEB,
}


class ConfigLeitura(BaseModel):
    modelo: str = escolha_ia.campo_modelo(
        "Em branco, o Batuta usa o mais barato da IA com chave (Claude Haiku, GPT-5.6 Luna "
        "ou Gemini Flash-Lite) — basta para extrair o que está na página."
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
    provedores_ia = escolha_ia.TODAS
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
            return self._pela_openai(url, args.o_que_extrair, modelo, config.max_tamanho)
        if escolha_ia.provedor(modelo) == "google":
            return self._pelo_google(url, pedido, modelo)
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

    def _pela_openai(self, url: str, o_que_extrair: str, modelo: str, max_tamanho: int) -> dict:
        # O Batuta baixa a página AO VIVO e entrega o texto: a busca da OpenAI pode abrir
        # uma cópia guardada (veio uma versão de agosto de um blog atualizado ontem).
        # `max_tamanho` está em tokens; ~4 caracteres por token.
        texto, cortado = texto_da_pagina(url, max_tamanho * 4)
        if not texto:
            raise FalhaInstrumento(
                "a página abriu, mas não tem texto (o conteúdo deve ser montado no navegador, "
                "com JavaScript).", retentavel=False, codigo="pagina.sem_texto",
            )
        pedido = f"Endereço: {url}\n\nO que extrair: {o_que_extrair}\n\nConteúdo da página (lido agora):\n{texto}"
        r = oai.chamar(
            modelo=modelo, sistema=SISTEMA,
            conteudo=[{"type": "input_text", "text": pedido}], ferramentas=[],
        )
        if not r["texto"]:
            raise FalhaInstrumento("a leitura da página não trouxe resposta.", retentavel=True)
        resultado = {
            "ok": True,
            "url": url,
            "conteudo": r["texto"],
            "avisos": r["erros"],
            "uso": r["uso"],
        }
        if cortado:
            resultado["aviso"] = (
                "A página é maior que o limite de leitura do instrumento: só o começo foi lido."
            )
        return resultado

    def _pelo_google(self, url: str, pedido: str, modelo: str) -> dict:
        r = goo.chamar(
            modelo=modelo, sistema=SISTEMA + " Use só a página indicada.",
            conteudo=[pedido], ferramentas=[gtypes.Tool(url_context=gtypes.UrlContext())],
        )
        situacoes = goo.links_lidos(r["resposta"])
        abriu = any(s.endswith("SUCCESS") for s in situacoes.values())
        if not r["texto"]:
            if situacoes and not abriu:
                raise FalhaInstrumento(
                    "a página não pôde ser aberta (fora do ar, exige login ou bloqueia robôs).",
                    retentavel=False, codigo="google.link_inacessivel",
                )
            raise FalhaInstrumento("a leitura da página não trouxe resposta.", retentavel=True)
        resultado = {
            "ok": True,
            "url": url,
            "conteudo": r["texto"],
            "avisos": [f"{link}: {s}" for link, s in situacoes.items() if not s.endswith("SUCCESS")],
            "uso": r["uso"],
        }
        if not abriu:
            resultado["aviso"] = "A IA não abriu esta página; a resposta pode não ter vindo dela."
        return resultado


registrar(LerPagina())
