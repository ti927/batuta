"""Memória entre turnos da conversa (Fatia 4.3 / P2a).

`executar_agente`, quando recebe `checkpointer` + `thread_id`, roda com memória: o
`invoke` devolve o estado ACUMULADO e a medição conta só o DELTA do turno. O
`preambulo_sistema` (enquadramento do transporte) vai para o prompt de sistema.
Aqui o `create_agent` é trocado por um app falso que SIMULA o acúmulo — sem LLM.
"""

import uuid
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents.middleware import SummarizationMiddleware

import orquestracao.agente as agente_mod
from modelos import Agente


def _agente():
    ag = Agente(time_id=uuid.uuid4(), nome="Ag", papel="agente")
    ag.id = uuid.uuid4()
    return ag


def _uso(inp, out):
    return {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out}


def test_com_memoria_mede_so_o_delta(monkeypatch):
    """O turno anterior (999/99) NÃO pode ser recontado: o uso é só o do turno novo.
    O delta é POR IDENTIDADE (id): o que já existia no fio fica de fora."""
    # Estado que "já existia" no fio (turno anterior) — 1 AIMessage cara, com id estável.
    estado = {"messages": [AIMessage(content="anterior", usage_metadata=_uso(999, 99), id="m0")]}

    def fake_create(modelo, ferramentas, system_prompt, checkpointer=None, middleware=None):
        class App:
            def get_state(self, config):
                return SimpleNamespace(values=estado)

            def invoke(self, inp, config=None):
                estado["messages"] = estado["messages"] + [
                    HumanMessage(content="fala nova", id="m1"),
                    AIMessage(content="resposta nova", usage_metadata=_uso(50, 5), id="m2"),
                ]
                return {"messages": estado["messages"]}

        return App()

    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m: object())
    monkeypatch.setattr(agente_mod, "create_agent", fake_create)

    r = agente_mod.executar_agente(
        _agente(), [], "fala nova", checkpointer=object(), thread_id="t1"
    )
    assert r["saida"] == "resposta nova"
    assert r["uso"][0]["tokens_entrada"] == 50   # só o delta (não 999+50)
    assert r["uso"][0]["tokens_saida"] == 5


def test_delta_por_identidade_quando_o_resumo_encolhe(monkeypatch):
    """P2b: se o resumo dispara e ENCOLHE o fio (troca antigas por 1 resumo + janela),
    medir por POSIÇÃO (`mensagens[n:]`) daria ZERO. Por IDENTIDADE o delta segue certo:
    só a fala nova conta; o resumo injetado (sem uso) não polui a medição."""
    # Fio anterior: 5 mensagens com ids estáveis; AIMessages caras que NÃO podem recontar.
    antes = [
        AIMessage(content="a0", usage_metadata=_uso(999, 99), id="m0"),
        HumanMessage(content="a1", id="m1"),
        AIMessage(content="a2", usage_metadata=_uso(500, 50), id="m2"),
        HumanMessage(content="a3", id="m3"),
        AIMessage(content="a4", usage_metadata=_uso(300, 30), id="m4"),
    ]

    def fake_create(modelo, ferramentas, system_prompt, checkpointer=None, middleware=None):
        class App:
            def get_state(self, config):
                return SimpleNamespace(values={"messages": antes})

            def invoke(self, inp, config=None):
                # Simula a compactação: remove as antigas, injeta 1 resumo, preserva a
                # janela (m3, m4 — mesmos ids) e adiciona a fala nova + resposta. O fio
                # ENCOLHE (fica com menos mensagens do que havia antes).
                return {"messages": [
                    HumanMessage(content="resumo do que passou", id="s0"),
                    antes[3], antes[4],  # janela preservada (ids m3, m4)
                    HumanMessage(content="fala nova", id="n1"),
                    AIMessage(content="resposta nova", usage_metadata=_uso(40, 4), id="n2"),
                ]}

        return App()

    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m: object())
    monkeypatch.setattr(agente_mod, "create_agent", fake_create)

    r = agente_mod.executar_agente(
        _agente(), [], "fala nova", checkpointer=object(), thread_id="t1"
    )
    assert r["saida"] == "resposta nova"
    # Só o turno novo (40/4) — nem os 999/500/300 anteriores, nem zero por medir posição.
    assert r["uso"][0]["tokens_entrada"] == 40
    assert r["uso"][0]["tokens_saida"] == 4


def test_middleware_de_resumo_so_no_chat(monkeypatch):
    """Com memória (chat) o agente recebe o SummarizationMiddleware (janela/resumo, P2b);
    sem memória (orquestração/tarefa/portão) NÃO recebe middleware — grafo efêmero,
    byte-idêntico à P1."""
    capt: dict = {"mws": []}

    class ModeloFake:
        # O SummarizationMiddleware calibra o contador por este atributo do modelo.
        _llm_type = "anthropic-chat"

    def fake_create(modelo, ferramentas, system_prompt, **kwargs):
        capt["mws"].append(kwargs.get("middleware", "AUSENTE"))

        class App:
            def get_state(self, config):
                return SimpleNamespace(values={"messages": []})

            def invoke(self, inp, config=None):
                return {"messages": [AIMessage(content="ok", usage_metadata=_uso(1, 1))]}

        return App()

    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m: ModeloFake())
    monkeypatch.setattr(agente_mod, "create_agent", fake_create)

    agente_mod.executar_agente(_agente(), [], "oi", checkpointer=object(), thread_id="t1")
    agente_mod.executar_agente(_agente(), [], "oi")  # sem memória

    com_mem, sem_mem = capt["mws"]
    assert isinstance(com_mem, list) and len(com_mem) == 1
    assert isinstance(com_mem[0], SummarizationMiddleware)
    assert sem_mem == "AUSENTE"  # sem memória, nenhum middleware é passado


def test_sem_memoria_conta_o_fio_inteiro(monkeypatch):
    """Sem checkpointer (orquestração/tarefa), nada muda: conta todas as AIMessage do
    resultado (n_antes=0), como sempre — e NÃO chama get_state nem passa config."""
    chamou = {"get_state": False, "config": "ausente"}

    def fake_create(modelo, ferramentas, system_prompt):  # sem kwarg checkpointer
        class App:
            def get_state(self, config):
                chamou["get_state"] = True
                return None

            def invoke(self, inp, config="ausente"):
                chamou["config"] = config
                return {"messages": [AIMessage(content="ok", usage_metadata=_uso(10, 2))]}

        return App()

    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m: object())
    monkeypatch.setattr(agente_mod, "create_agent", fake_create)

    r = agente_mod.executar_agente(_agente(), [], "entrada")  # sem memória
    assert r["uso"][0]["tokens_entrada"] == 10
    assert chamou["get_state"] is False        # não mexe em estado
    assert chamou["config"] == "ausente"       # invoke chamado SEM config (fake de 1 arg)


def test_preambulo_vai_para_o_prompt_de_sistema(monkeypatch):
    """O enquadramento do transporte entra no prompt de sistema (persistente/cacheado)."""
    capt = {}

    def fake_create(modelo, ferramentas, system_prompt, checkpointer=None, middleware=None):
        capt["sys"] = system_prompt

        class App:
            def get_state(self, config):
                return SimpleNamespace(values={"messages": []})

            def invoke(self, inp, config=None):
                return {"messages": [AIMessage(content="ok", usage_metadata=_uso(1, 1))]}

        return App()

    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m: object())
    monkeypatch.setattr(agente_mod, "create_agent", fake_create)

    agente_mod.executar_agente(
        _agente(), [], "oi", checkpointer=object(), thread_id="t1",
        preambulo_sistema="ENQUADRAMENTO DO CANAL",
    )
    # o prompt pode vir como texto puro ou SystemMessage (Anthropic) — extrai o texto
    sys = capt["sys"]
    texto = sys if isinstance(sys, str) else "".join(b.get("text", "") for b in sys.content)
    assert "ENQUADRAMENTO DO CANAL" in texto
