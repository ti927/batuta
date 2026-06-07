"""Testes do laço de conversa da IA criadora (Fase 9), com o agente MOCKADO.

Garantem que um turno persiste o histórico e o rascunho mutado pelas ferramentas,
mede os tokens, e que o turno seguinte recebe o histórico anterior. Sem LLM real:
`create_react_agent` e `construir_modelo` são substituídos."""

from langchain_core.messages import AIMessage, ToolMessage

import criacao.loop as loop
from criacao.loop import responder_turno
from modelos import ConversaCriacao


def _uso(entrada, saida):
    return {"input_tokens": entrada, "output_tokens": saida, "total_tokens": entrada + saida}


def test_turno_persiste_mensagens_e_rascunho(monkeypatch, sessao, dados):
    def fake_create(modelo, ferramentas, prompt=None):
        porta = {t.name: t for t in ferramentas}

        class App:
            def invoke(self, payload):
                # a IA "decide" montar o time via a ferramenta — muta o rascunho.
                # Como o react agent real, devolve o histórico recebido + a nova.
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

    r = responder_turno(conversa, "Quero um time de blog")
    assert r["resposta"] == "Montei o time."
    assert conversa.rascunho["time_nome"] == "Time da Conversa"
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
                        AIMessage(
                            content="Vou montar seu time!", usage_metadata=_uso(10, 5)
                        ),
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

    r = responder_turno(conversa, "oi")
    assert r["resposta"] == "Vou montar seu time!"
    # mediu os tokens dos dois turnos do modelo
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
        rascunho={},
    )
    sessao.add(conversa)
    sessao.flush()

    responder_turno(conversa, "segunda mensagem")
    papeis = [m["role"] for m in capturado["messages"]]
    assert papeis == ["user", "assistant", "user"]
    assert capturado["messages"][-1]["content"] == "segunda mensagem"
