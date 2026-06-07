"""Testes do laço de conversa da IA criadora, com o agente MOCKADO.

Garantem que um turno persiste o histórico, mede os tokens, escreve no TIME REAL
pelas ferramentas, e que o turno seguinte recebe o histórico anterior. Sem LLM real:
`create_react_agent` e `construir_modelo` são substituídos."""

from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy import select

import criacao.loop as loop
from criacao.loop import responder_turno
from modelos import ConversaCriacao, Time


def _uso(entrada, saida):
    return {"input_tokens": entrada, "output_tokens": saida, "total_tokens": entrada + saida}


def test_turno_persiste_mensagens_e_cria_time(monkeypatch, sessao, dados):
    def fake_create(modelo, ferramentas, prompt=None):
        porta = {t.name: t for t in ferramentas}

        class App:
            def invoke(self, payload):
                # a IA "decide" criar o time via a ferramenta — escreve no time REAL.
                porta["definir_time"].func(nome="Time da Conversa")
                return {
                    "messages": payload["messages"]
                    + [AIMessage(content="Montei o time.", usage_metadata=_uso(12, 7))]
                }

        return App()

    monkeypatch.setattr(loop, "create_react_agent", fake_create)
    monkeypatch.setattr(loop, "construir_modelo", lambda *a, **k: object())

    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id, criada_por_id=dados["admin"].id
    )
    sessao.add(conversa)
    sessao.flush()

    r = responder_turno(sessao, conversa, "Quero um time de blog", usuario=dados["admin"])
    assert r["resposta"] == "Montei o time."
    # o time foi criado de verdade e vinculado à conversa
    assert conversa.time_id is not None
    time = sessao.get(Time, conversa.time_id)
    assert time.nome == "Time da Conversa"
    assert r["time"]["time"]["nome"] == "Time da Conversa"
    assert len(conversa.mensagens) == 2
    assert conversa.mensagens[0]["papel"] == "usuario"
    assert conversa.mensagens[-1]["uso"]["tokens_entrada"] == 12
    assert conversa.mensagens[-1]["uso"]["tokens_saida"] == 7


def test_texto_vem_de_turno_anterior_quando_o_ultimo_vem_vazio(
    monkeypatch, sessao, dados
):
    """Regressão: o modelo (Anthropic) emite o texto JUNTO com a chamada de
    ferramenta; o ÚLTIMO AIMessage, depois das ferramentas, vem vazio. A resposta
    NÃO pode ficar vazia — juntamos o texto de todos os turnos do modelo."""

    def fake_create(modelo, ferramentas, prompt=None):
        porta = {t.name: t for t in ferramentas}

        class App:
            def invoke(self, payload):
                porta["definir_time"].func(nome="Time X")
                return {
                    "messages": payload["messages"]
                    + [
                        AIMessage(content="Vou montar seu time!", usage_metadata=_uso(10, 5)),
                        ToolMessage(content="{}", tool_call_id="x"),
                        AIMessage(content="", usage_metadata=_uso(8, 0)),
                    ]
                }

        return App()

    monkeypatch.setattr(loop, "create_react_agent", fake_create)
    monkeypatch.setattr(loop, "construir_modelo", lambda *a, **k: object())

    conversa = ConversaCriacao(organizacao_id=dados["orgA"].id)
    sessao.add(conversa)
    sessao.flush()

    r = responder_turno(sessao, conversa, "oi", usuario=dados["admin"])
    assert r["resposta"] == "Vou montar seu time!"
    assert conversa.mensagens[-1]["uso"]["tokens_entrada"] == 18


def test_turno_recebe_o_historico_anterior(monkeypatch, sessao, dados):
    capturado = {}

    def fake_create(modelo, ferramentas, prompt=None):
        class App:
            def invoke(self, payload):
                capturado["messages"] = payload["messages"]
                return {
                    "messages": payload["messages"]
                    + [AIMessage(content="ok", usage_metadata=_uso(0, 0))]
                }

        return App()

    monkeypatch.setattr(loop, "create_react_agent", fake_create)
    monkeypatch.setattr(loop, "construir_modelo", lambda *a, **k: object())

    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id,
        mensagens=[
            {"papel": "usuario", "conteudo": "oi"},
            {"papel": "ia", "conteudo": "olá, vamos criar?"},
        ],
    )
    sessao.add(conversa)
    sessao.flush()

    responder_turno(sessao, conversa, "segunda mensagem", usuario=dados["admin"])
    papeis = [m["role"] for m in capturado["messages"]]
    assert papeis == ["user", "assistant", "user"]
    assert capturado["messages"][-1]["content"] == "segunda mensagem"
