"""O agente DECLARA o ramo do fluxo (em vez de uma LLM roteadora adivinhar).

Quando um nó tem 2+ saídas, `executar_agente` injeta a ferramenta `seguir_para`
(enum dos rótulos) e expõe o ramo escolhido em `ramo_escolhido`. Nó de 1 saída não
oferece a ferramenta (não há o que escolher). Estes testes não falam com a LLM:
trocam `create_react_agent` por um app falso que aciona (ou não) a ferramenta.
"""

import uuid

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

import orquestracao.agente as agente_mod
from modelos import Agente


def _agente():
    ag = Agente(time_id=uuid.uuid4(), nome="Ag", papel="agente")
    ag.id = uuid.uuid4()
    return ag


def _saidas_duas():
    return [
        {"rotulo": "ok", "quando": "deu certo", "destino": "fim"},
        {"rotulo": "refazer", "quando": "precisa ajuste", "destino": "inicio"},
    ]


def _fake_app(monkeypatch, *, chama_rotulo=None, capturar=None):
    """Troca create_react_agent por um app falso. Se `chama_rotulo`, aciona a
    ferramenta `seguir_para` com esse rótulo. `capturar` recebe a lista de tools."""

    def fake_create(modelo, ferramentas, prompt):
        if capturar is not None:
            capturar.extend(ferramentas)
        if chama_rotulo is not None:
            seguir = next(f for f in ferramentas if f.name == "seguir_para")
            seguir.func(rotulo=chama_rotulo)

        class App:
            def invoke(self, _):
                return {"messages": [AIMessage(content="feito")]}

        return App()

    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m: object())
    monkeypatch.setattr(agente_mod, "create_react_agent", fake_create)


def test_agente_declara_o_ramo(monkeypatch):
    _fake_app(monkeypatch, chama_rotulo="refazer")
    r = agente_mod.executar_agente(_agente(), [], "entrada", saidas=_saidas_duas())
    assert r["ramo_escolhido"] == "refazer"


def test_uma_saida_nao_injeta_seguir_para(monkeypatch):
    tools: list = []
    _fake_app(monkeypatch, capturar=tools)
    r = agente_mod.executar_agente(
        _agente(), [], "entrada", saidas=[{"rotulo": "ok", "destino": "fim"}]
    )
    assert all(f.name != "seguir_para" for f in tools)
    assert r["ramo_escolhido"] is None


def test_sem_declarar_ramo_fica_none(monkeypatch):
    _fake_app(monkeypatch, chama_rotulo=None)  # app não chama seguir_para
    r = agente_mod.executar_agente(_agente(), [], "entrada", saidas=_saidas_duas())
    assert r["ramo_escolhido"] is None


def test_rotulo_fora_do_enum_e_rejeitado(monkeypatch):
    tools: list = []
    _fake_app(monkeypatch, capturar=tools)
    agente_mod.executar_agente(_agente(), [], "entrada", saidas=_saidas_duas())
    seguir = next(f for f in tools if f.name == "seguir_para")
    seguir.func(rotulo="ok")  # rótulo válido: passa
    with pytest.raises(ValidationError):
        seguir.func(rotulo="inexistente")  # fora do enum: rejeitado


# ── portao.md: instruções editáveis do portão (Onda 2) ──────────────────────

def test_instrucao_de_fluxo_usa_portao_md():
    """Com portao.md, o preâmbulo COMPORTAMENTAL vira o texto do nó; o TRILHO mecânico
    (`seguir_para` + a lista de Caminhos) continua SEMPRE — o criador não o remove."""
    txt = agente_mod._instrucao_de_fluxo(
        _saidas_duas(), True, "AO APROVAR, AGENDE E ENCAMINHE"
    )
    assert "AO APROVAR, AGENDE E ENCAMINHE" in txt
    assert "seguir_para" in txt and "Caminhos:" in txt
    assert "Quando você tiver a decisão da pessoa" not in txt  # padrão substituído


def test_instrucao_de_fluxo_fallback_sem_md():
    """Sem portao.md (None ou só espaços), vale o texto padrão — portões existentes
    não mudam."""
    padrao = agente_mod._instrucao_de_fluxo(_saidas_duas(), True, None)
    assert "Quando você tiver a decisão da pessoa" in padrao
    assert agente_mod._instrucao_de_fluxo(_saidas_duas(), True, "   ") == padrao


def _texto_do_prompt(p) -> str:
    """O prompt de sistema pode vir como texto puro (OpenAI/Google) OU como
    `SystemMessage` com blocos de cache (Anthropic — cache de prompt). Extrai o texto
    dos dois formatos, para a asserção não depender do provedor."""
    if isinstance(p, str):
        return p
    return "".join(b.get("text", "") for b in p.content)


def test_executar_agente_injeta_portao_md_no_prompt(monkeypatch):
    """O `texto_portao` chega ao PROMPT do agente, com o trilho `seguir_para` intacto."""
    prompts: list = []

    def fake_create(modelo, ferramentas, prompt):
        prompts.append(prompt)

        class App:
            def invoke(self, _):
                return {"messages": [AIMessage(content="feito")]}

        return App()

    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m: object())
    monkeypatch.setattr(agente_mod, "create_react_agent", fake_create)
    agente_mod.executar_agente(
        _agente(), [], "entrada", saidas=_saidas_duas(), gate=True,
        texto_portao="AGENDE E ENCAMINHE",
    )
    texto = _texto_do_prompt(prompts[0])
    assert "AGENDE E ENCAMINHE" in texto
    assert "seguir_para" in texto  # trilho mecânico preservado
