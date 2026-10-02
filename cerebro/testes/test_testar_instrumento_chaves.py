"""O "Testar" de um instrumento (tela e MCP) roda com as chaves da organização ligadas
do começo ao fim (2026-10-02). Antes, o bloco das chaves fechava logo depois de ler os
segredos: os instrumentos de IA da OpenAI e do Google respondiam "não há chave" com a
chave cadastrada, e os da Anthropic caíam na chave reserva do servidor (o custo ia para
a conta errada). Dentro de um agente sempre funcionou — só o teste falhava."""

import pytest

from cofre import cifrar, ultimos4
from instrumentos import anthropic_servidor as srv
from instrumentos import google_servidor as goo
from instrumentos import openai_servidor as oai
from modelos import ChaveApi, Instrumento
from rotas.instrumentos import acionar_instrumento


def _chave_da_consultoria(sessao, provedor, segredo):
    sessao.add(ChaveApi(organizacao_id=None, provedor=provedor, valor_cifrado=cifrar(segredo),
                        ultimos4=ultimos4(segredo), ativa=True))
    sessao.flush()


def _pesquisa(sessao, dados, modelo):
    inst = Instrumento(time_id=dados["timeA"].id, nome="Busca", tipo="pesquisar_web",
                       configuracao={"modelo": modelo})
    sessao.add(inst)
    sessao.flush()
    return inst


@pytest.mark.parametrize("provedor, modelo, modulo, segredo", [
    ("openai", "gpt-5.6-luna", oai, "sk-openai-consultoria"),
    ("google", "gemini-3.5-flash-lite", goo, "g-consultoria"),
    ("anthropic", "claude-haiku-4-5", srv, "sk-ant-consultoria"),
])
def test_testar_usa_a_chave_do_cofre_ate_o_fim(sessao, dados, monkeypatch, provedor, modelo, modulo, segredo):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # sem a chave reserva do servidor
    _chave_da_consultoria(sessao, provedor, segredo)
    vistas = []

    def chamar(**kw):
        vistas.append(modulo._chave())  # a chave que o instrumento enxerga AO RODAR
        return {"texto": "ok", "itens": [], "blocos": [], "resposta": None, "erros": [], "uso": {}}

    monkeypatch.setattr(modulo, "chamar", chamar)
    monkeypatch.setattr(goo, "fontes", lambda r: [])
    acionar_instrumento(sessao, _pesquisa(sessao, dados, modelo), {"pergunta": "selic hoje"})
    assert vistas == [segredo]


def test_testar_sem_chave_nenhuma_continua_dizendo_o_caminho(sessao, dados, monkeypatch):
    from instrumentos.base import FalhaInstrumento

    with pytest.raises(FalhaInstrumento) as e:
        acionar_instrumento(sessao, _pesquisa(sessao, dados, "gpt-5.6-luna"), {"pergunta": "selic hoje"})
    assert e.value.codigo == "ia.sem_chave"
