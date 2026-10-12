"""Resposta cortada no teto de saída não passa adiante como se estivesse inteira.

Em 12/10/2026 (execução f2886ef5) o artigo do Redator parou em "receita acumul": o teto
fixo de 8192 tokens (com o pensamento do modelo contando dentro) cortou o texto, o passo
foi marcado como concluído e o texto pela metade seguiu para o Editor. Agora: o tamanho
é do AGENTE (curto/padrão/longo, aba Ritmo e espera), o teto respeita o que cada modelo
aceita, e a resposta cortada PARA o passo com o que fazer.
"""

import uuid

import pytest
from langchain_core.messages import AIMessage

import orquestracao.agente as agente_mod
from instrumentos.base import FalhaInstrumento
from mensageria import config as cfg
from modelos import Agente
from orquestracao import llm


def _agente(configuracao=None):
    ag = Agente(time_id=uuid.uuid4(), nome="Redator", papel="agente",
                modelo_ia="claude-sonnet-5-5", configuracao=configuracao)
    ag.id = uuid.uuid4()
    return ag


def _app_falso(monkeypatch, resposta: AIMessage, capturar: dict):
    def fake_construir(modelo, **k):
        capturar.update(k)
        return object()

    def fake_create(modelo, ferramentas, system_prompt, middleware=None):
        class App:
            def invoke(self, _entrada, _config=None):
                return {"messages": [resposta]}

        return App()

    monkeypatch.setattr(agente_mod, "construir_modelo", fake_construir)
    monkeypatch.setattr(agente_mod, "create_agent", fake_create)


@pytest.mark.parametrize(
    "meta",
    [
        {"stop_reason": "max_tokens"},           # Anthropic
        {"finish_reason": "length"},             # OpenAI
        {"finish_reason": "MAX_TOKENS"},         # Google
        {"finish_reason": "FinishReason.MAX_TOKENS"},
    ],
)
def test_reconhece_o_corte_nos_tres_provedores(meta):
    assert llm.resposta_cortada(AIMessage(content="x", response_metadata=meta))


@pytest.mark.parametrize(
    "meta", [{"stop_reason": "end_turn"}, {"finish_reason": "stop"}, {"stop_reason": "tool_use"}, {}]
)
def test_resposta_inteira_nao_e_corte(meta):
    assert not llm.resposta_cortada(AIMessage(content="x", response_metadata=meta))


def test_resposta_cortada_para_o_passo_com_o_que_fazer(monkeypatch):
    eventos = []
    monkeypatch.setattr(
        "observabilidade.escritor.registrar_evento", lambda **k: eventos.append(k)
    )
    cortada = AIMessage(
        content="A planilha precisa calcular a receita acumul",
        response_metadata={"stop_reason": "max_tokens"},
    )
    _app_falso(monkeypatch, cortada, {})
    with pytest.raises(FalhaInstrumento) as e:
        agente_mod.executar_agente(_agente(), [], "escreva o artigo")
    msg = str(e.value)
    assert "Redator" in msg and "saiu cortada" in msg
    assert "Tamanho máximo de cada resposta" in msg  # onde mudar, pelo nome da tela
    assert e.value.retentavel is False  # tentar de novo daria o mesmo corte
    # §12-A: a queda tem endereço no banco de logs
    assert eventos and eventos[0]["acao"] == "agente.resposta_cortada"
    assert eventos[0]["nivel"] == "error"


def test_resposta_inteira_segue(monkeypatch):
    inteira = AIMessage(content="Artigo completo.", response_metadata={"stop_reason": "end_turn"})
    _app_falso(monkeypatch, inteira, {})
    r = agente_mod.executar_agente(_agente(), [], "escreva o artigo")
    assert r["saida"] == "Artigo completo."


@pytest.mark.parametrize(
    "configuracao,tokens",
    [(None, 16000), ({"tamanho_resposta": "curto"}, 4000),
     ({"tamanho_resposta": "longo"}, 32000), ({"tamanho_resposta": "xis"}, 16000)],
)
def test_o_tamanho_vem_do_agente(monkeypatch, configuracao, tokens):
    pedido = {}
    _app_falso(monkeypatch, AIMessage(content="ok"), pedido)
    agente_mod.executar_agente(_agente(configuracao), [], "x")
    assert pedido["max_tokens"] == tokens


def test_o_teto_respeita_o_que_o_modelo_aceita():
    assert llm.tokens_de_saida("claude-sonnet-5-5", 32000) == 32000
    assert llm.tokens_de_saida("gpt-4o", 32000) == 16384
    assert llm.tokens_de_saida("gemini-2.0-flash", None) == 8192
    assert llm.tokens_de_saida("claude-haiku-5-5", None) == llm.MAX_TOKENS == 16000


def test_construir_modelo_manda_o_tamanho_e_alonga_a_espera(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-teste")
    m = llm.construir_modelo("claude-sonnet-5-5", max_tokens=32000)
    assert m.max_tokens == 32000
    # resposta longa leva mais tempo para ser escrita: a espera cresce junto
    assert m.default_request_timeout >= 32000 // 40
    curto = llm.construir_modelo("claude-sonnet-5-5", max_tokens=4000)
    assert curto.default_request_timeout == llm.TIMEOUT_IA_S


def test_tamanho_e_so_do_agente_e_aparece_na_tela():
    """Fora da herança automação → agente (não há padrão a herdar), mas com botão."""
    assert "tamanho_resposta" not in cfg.GLOBAL
    assert "tamanho_resposta" in cfg.CHAVES_SO_DO_AGENTE
    campo = next(
        c for g in cfg.painel_config()["grupos"] if g["nivel"] == "so_agente"
        for c in g["campos"] if c["chave"] == "tamanho_resposta"
    )
    assert campo["padrao"] == "padrao"
    assert {o["valor"] for o in campo["opcoes"]} == set(cfg.TAMANHOS_RESPOSTA)
