"""Portão NATIVO (Fatia 4.3 / P3a) — o HITL seletivo dentro do `executar_agente`.

Diferente dos outros testes de agente (que falseiam `create_agent`), aqui rodamos o
`executar_agente` REAL com o `HumanInTheLoopMiddleware` REAL + um checkpointer em
memória — é o único jeito de provar o comportamento do portão nativo (pausa/retoma via
`Command`). O modelo é um FAKE roteirizado (custo zero, sem rede): lê → publica →
conclui. Os contadores das ferramentas são a prova de "quantas vezes rodou de verdade".

P3a é "no escuro": o portão nativo é OPT-IN (`portao_nativo=True`) e não está ligado a
nenhum fluxo de produção. Estes testes exercem só o mecanismo no motor.
"""

import uuid

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

import orquestracao.agente as agente_mod
from instrumentos.base import TipoInstrumento, registrar
from modelos import Agente, Instrumento
from orquestracao.agente import executar_agente

# Contadores de execução REAL das ferramentas.
contador = {"ler": 0, "publicar": 0}
# Nomes das ferramentas (derivados do id do instrumento) — o fake precisa acioná-los
# pelo nome EXATO; preenchidos por `_montar`.
_NOMES = {"ler": "", "pub": ""}


class _ConfVazia(BaseModel):
    pass


class _ArgsVazio(BaseModel):
    pass


class _ArgsPub(BaseModel):
    texto: str = "x"


class _TipoLer(TipoInstrumento):
    tipo = "p3_ler"
    nome_exibicao = "Ler"
    descricao = "lê um dado (seguro)"
    Config = _ConfVazia
    Args = _ArgsVazio
    acao_irreversivel = False  # LEITURA → não gateia

    def executar(self, config, args):
        contador["ler"] += 1
        return {"dados": 42}


class _TipoPub(TipoInstrumento):
    tipo = "p3_pub"
    nome_exibicao = "Publicar"
    descricao = "publica (irreversível)"
    Config = _ConfVazia
    Args = _ArgsPub
    acao_irreversivel = True  # IRREVERSÍVEL → gateia

    def executar(self, config, args):
        contador["publicar"] += 1
        return {"ok": True}


registrar(_TipoLer())
registrar(_TipoPub())


class _FakeModelo(BaseChatModel):
    """Roteiriza o laço react: chama ler → chama publicar → conclui. Idempotente pelo
    que já tem ToolMessage (re-execuções do laço não confundem a fita)."""

    @property
    def _llm_type(self) -> str:
        return "fake-p3"

    def bind_tools(self, tools, **kwargs):  # create_agent chama; ignoramos o schema
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        feitas = {m.name for m in messages if isinstance(m, ToolMessage)}
        if _NOMES["ler"] not in feitas:
            ai = AIMessage(content="", tool_calls=[
                {"name": _NOMES["ler"], "args": {}, "id": "c_ler", "type": "tool_call"}])
        elif _NOMES["pub"] not in feitas:
            ai = AIMessage(content="", tool_calls=[
                {"name": _NOMES["pub"], "args": {"texto": "olá"},
                 "id": "c_pub", "type": "tool_call"}])
        else:
            ai = AIMessage(content="pronto.")
        return ChatResult(generations=[ChatGeneration(message=ai)])


def _montar(monkeypatch):
    contador["ler"] = 0
    contador["publicar"] = 0
    time_id = uuid.uuid4()
    ag = Agente(id=uuid.uuid4(), time_id=time_id, nome="A", papel="agente",
                modelo_ia="claude-sonnet-5")
    ler = Instrumento(id=uuid.uuid4(), time_id=time_id, nome="Ler", tipo="p3_ler",
                      configuracao={})
    pub = Instrumento(id=uuid.uuid4(), time_id=time_id, nome="Publicar", tipo="p3_pub",
                      configuracao={})
    _NOMES["ler"] = agente_mod._nome_de_ferramenta(ler, "p3_ler")
    _NOMES["pub"] = agente_mod._nome_de_ferramenta(pub, "p3_pub")
    # `construir_modelo` é chamado p/ o agente E p/ o resumidor (P2b); o fake serve aos
    # dois (o resumo não dispara — fio minúsculo).
    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m, **k: _FakeModelo())
    return ag, [ler, pub]


def test_gate_seletivo_pausa_so_no_irreversivel(monkeypatch):
    ag, cinto = _montar(monkeypatch)
    ckpt, tid = MemorySaver(), "t-sel"
    r = executar_agente(ag, cinto, "faça", checkpointer=ckpt, thread_id=tid,
                        portao_nativo=True)
    # o de LEITURA rodou livre; o IRREVERSÍVEL parou no portão (não executou)
    assert r["pausado"] is True
    assert contador["ler"] == 1
    assert contador["publicar"] == 0
    # o pedido de aprovação carrega o nome + args da ação irreversível
    reqs = r["acao_pendente"]["action_requests"]
    assert any(a["name"] == _NOMES["pub"] for a in reqs)


def test_aprovar_publica_uma_vez_e_nao_re_executa_leitura(monkeypatch):
    ag, cinto = _montar(monkeypatch)
    ckpt, tid = MemorySaver(), "t-aprovar"
    # 1º: pausa no portão. 2º: chamada NOVA (grafo efêmero) no MESMO checkpointer+thread
    # — é o cenário REAL de produção (cada turno reconstrói o app).
    executar_agente(ag, cinto, "faça", checkpointer=ckpt, thread_id=tid, portao_nativo=True)
    r = executar_agente(ag, cinto, "", checkpointer=ckpt, thread_id=tid,
                        portao_nativo=True, retomar={"decisions": [{"type": "approve"}]})
    assert r["pausado"] is False
    assert contador["publicar"] == 1      # aprovou → publicou EXATAMENTE 1×
    assert contador["ler"] == 1           # a leitura anterior NÃO re-executou (caveat contido)


def test_recusar_nao_publica(monkeypatch):
    ag, cinto = _montar(monkeypatch)
    ckpt, tid = MemorySaver(), "t-recusar"
    executar_agente(ag, cinto, "faça", checkpointer=ckpt, thread_id=tid, portao_nativo=True)
    r = executar_agente(ag, cinto, "", checkpointer=ckpt, thread_id=tid,
                        portao_nativo=True, retomar={"decisions": [{"type": "reject"}]})
    assert r["pausado"] is False
    assert contador["publicar"] == 0      # recusou → NÃO publicou (0×)


def test_reaprovar_nao_duplica(monkeypatch):
    ag, cinto = _montar(monkeypatch)
    ckpt, tid = MemorySaver(), "t-duplo"
    executar_agente(ag, cinto, "faça", checkpointer=ckpt, thread_id=tid, portao_nativo=True)
    executar_agente(ag, cinto, "", checkpointer=ckpt, thread_id=tid,
                    portao_nativo=True, retomar={"decisions": [{"type": "approve"}]})
    assert contador["publicar"] == 1
    # reenvio/duplo-clique: retomar de novo no thread já concluído não pode publicar 2×
    try:
        executar_agente(ag, cinto, "", checkpointer=ckpt, thread_id=tid,
                        portao_nativo=True, retomar={"decisions": [{"type": "approve"}]})
    except Exception:
        pass  # levantar é aceitável; o que não pode é publicar de novo
    assert contador["publicar"] == 1


def test_sem_portao_nativo_nao_gateia(monkeypatch):
    """P3a é 'no escuro': com o opt-in DESLIGADO (default), o comportamento é o de hoje —
    a ferramenta irreversível roda no mesmo turno, sem pausa."""
    ag, cinto = _montar(monkeypatch)
    ckpt, tid = MemorySaver(), "t-off"
    r = executar_agente(ag, cinto, "faça", checkpointer=ckpt, thread_id=tid)
    assert r["pausado"] is False
    assert contador["publicar"] == 1      # rodou sem pausar (comportamento atual)


def test_interrupt_on_derivado_da_parede(monkeypatch):
    """O `interrupt_on` do middleware é derivado de `acao_irreversivel` (a MESMA regra da
    parede) — só o irreversível é gateado. Prova direta pelo helper."""
    mids = agente_mod._middleware_portao({"pub_x": True, "ler_x": False})
    assert len(mids) == 1
    # só o irreversível entra no gate (o middleware normaliza True → config de decisões)
    assert set(mids[0].interrupt_on) == {"pub_x"}
    # cinto sem nada irreversível → nenhum middleware (nada a gatear)
    assert agente_mod._middleware_portao({"ler_x": False, "buscar_y": False}) == []
