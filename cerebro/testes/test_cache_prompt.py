"""Cache de prompt da conversa inteira (`orquestracao/cache_prompt`).

O que estes testes travam (a regressão de cache é muda — o pedido segue funcionando, só
fica mais caro):
- os 4 pontos ficam onde devem (sistema, 2 últimas falas humanas, automático) e nunca
  passam do teto da API (4);
- o contexto volátil nunca recebe ponto e o estado original não é mutado;
- fora da Anthropic a peça não toca em nada;
- no PEDIDO REAL que o langchain-anthropic monta, o turno seguinte começa byte a byte
  igual ao anterior até a fala marcada — é o que faz o cache ser relido;
- a gravação no cache é contada (o langchain põe o número em chaves por TTL)."""

import json

from langchain.agents.middleware.types import ModelRequest
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from orquestracao.cache_prompt import (
    PONTO_DE_CACHE,
    CacheDePrompt,
    marcar_pedido,
    mensagem_de_contexto_volatil,
    tokens_de_cache,
)


def _modelo():
    return ChatAnthropic(model="claude-sonnet-5", api_key="sk-teste", max_tokens=100)


def _pontos(req: ModelRequest) -> int:
    n = 1 if req.model_settings.get("cache_control") else 0
    msgs = ([req.system_message] if req.system_message else []) + list(req.messages)
    for m in msgs:
        if isinstance(m.content, list):
            n += sum(1 for b in m.content if isinstance(b, dict) and "cache_control" in b)
    return n


def _turno(fala_antiga: str, fala_nova: str, volatil: str | None) -> list:
    msgs = [
        HumanMessage(content=fala_antiga),
        AIMessage(
            content="",
            tool_calls=[{"name": "ver", "args": {}, "id": "c1", "type": "tool_call"}],
        ),
        ToolMessage(content="resultado", tool_call_id="c1"),
        AIMessage(content="feito"),
        HumanMessage(content=fala_nova),
    ]
    if volatil:
        msgs.append(mensagem_de_contexto_volatil(volatil))
    return msgs


def test_marca_sistema_duas_falas_e_automatico_sem_passar_do_teto():
    sistema = SystemMessage(
        content=[{"type": "text", "text": "S", "cache_control": {"type": "ephemeral"}}]
    )
    req = ModelRequest(
        model=_modelo(),
        messages=_turno("primeira", "segunda", "FOTO"),
        system_message=sistema,
    )
    antes = [m.model_copy(deep=True) for m in req.messages]
    novo = marcar_pedido(req)

    assert _pontos(novo) == 4
    assert novo.model_settings["cache_control"] == PONTO_DE_CACHE
    assert novo.system_message.content[-1]["cache_control"] == PONTO_DE_CACHE
    falas = [m for m in novo.messages if isinstance(m, HumanMessage)]
    assert falas[0].content[-1]["cache_control"] == PONTO_DE_CACHE  # relê o turno anterior
    assert falas[1].content[-1]["cache_control"] == PONTO_DE_CACHE  # grava para o próximo
    assert falas[2].content == "FOTO"  # o volátil nunca é marcado
    # Nada do estado é mutado: a marcação vale só para este pedido.
    assert [m.content for m in req.messages] == [m.content for m in antes]


def test_um_turno_so_e_sem_sistema_fica_dentro_do_teto():
    req = ModelRequest(model=_modelo(), messages=[HumanMessage(content="oi")])
    assert _pontos(marcar_pedido(req)) == 2  # a fala + o automático


def test_fora_da_anthropic_nao_toca_no_pedido():
    class Outro:  # qualquer modelo que não é ChatAnthropic
        pass

    req = ModelRequest(model=Outro(), messages=[HumanMessage(content="oi")])
    visto = {}
    CacheDePrompt().wrap_model_call(req, lambda r: visto.setdefault("r", r))
    assert visto["r"] is req


def _payload(req: ModelRequest) -> dict:
    """O corpo que o langchain-anthropic mandaria à API para este pedido."""
    entrada = ([req.system_message] if req.system_message else []) + list(req.messages)
    return req.model._get_request_payload(entrada, **req.model_settings)


def test_turno_seguinte_comeca_igual_ate_a_fala_marcada():
    """A prova de que o cache é relido: o prefixo que o turno N gravou (até a fala nova
    dele) reaparece IDÊNTICO no turno N+1 — mesmo com a foto volátil mudando entre os
    dois e o resultado de ferramenta guardado truncado."""
    sistema = SystemMessage(content="SISTEMA ESTÁVEL")
    t1 = marcar_pedido(
        ModelRequest(
            model=_modelo(), messages=_turno("a", "b", "FOTO 1"), system_message=sistema
        )
    )
    # Turno 2: a conversa salva repete o turno 1 (sem o volátil) e segue.
    msgs2 = _turno("a", "b", None) + [
        AIMessage(content="ok"),
        HumanMessage(content="c"),
        mensagem_de_contexto_volatil("FOTO 2 — o time mudou"),
    ]
    t2 = marcar_pedido(ModelRequest(model=_modelo(), messages=msgs2, system_message=sistema))

    p1, p2 = _payload(t1), _payload(t2)
    assert p1["system"] == p2["system"]

    def sem_pontos(x):
        # Os pontos em si não fazem parte do prefixo (o ponto que anda sempre difere), e
        # conteúdo em texto puro é o atalho da API para um bloco de texto só.
        if isinstance(x, dict):
            if isinstance(x.get("content"), str) and "role" in x:
                x = {**x, "content": [{"type": "text", "text": x["content"]}]}
            return {k: sem_pontos(v) for k, v in x.items() if k != "cache_control"}
        if isinstance(x, list):
            return [sem_pontos(v) for v in x]
        return x

    def ate_fala_b(p):
        msgs = sem_pontos(p["messages"])
        for i, m in enumerate(msgs):
            blocos = m["content"] if isinstance(m["content"], list) else []
            if any(isinstance(b, dict) and b.get("text") == "b" for b in blocos):
                # só a fala "b" (o volátil, se houver, vem num bloco depois dela)
                fala = [b for b in blocos if b.get("text") == "b"]
                return json.dumps(msgs[:i] + [{**m, "content": fala}], sort_keys=True)
        raise AssertionError("fala 'b' não encontrada")

    assert ate_fala_b(p1) == ate_fala_b(p2)
    # O volátil do turno 1 não vaza para o turno 2.
    assert "FOTO 1" not in json.dumps(p2, ensure_ascii=False)


def test_conta_a_gravacao_nas_chaves_por_ttl():
    # Como o langchain-anthropic 1.4 reporta: cache_creation zerado, número por TTL.
    u = {
        "input_token_details": {
            "cache_read": 900,
            "cache_creation": 0,
            "ephemeral_5m_input_tokens": 300,
            "ephemeral_1h_input_tokens": 20,
        }
    }
    assert tokens_de_cache(u) == (900, 320)
    # Formato antigo (sem detalhe por TTL) segue valendo.
    assert tokens_de_cache({"input_token_details": {"cache_creation": 50}}) == (0, 50)
    assert tokens_de_cache(None) == (0, 0)
