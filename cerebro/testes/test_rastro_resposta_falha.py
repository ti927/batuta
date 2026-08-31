"""Falha devolvida como DADO (`ok: false`) entra no rastro cru (`erros_instrumentos`).

Aprendizado de 2026-08-25: o `Cria_Reembolso` do conector respondeu HTTP 400, a falha
voltou só para a IA decidir e o rastro ficou limpo — o agente narrou "lancei" e nada
dizia o contrário. Agora um resultado com `ok: false` é registrado com
`origem="resposta"`, nos DOIS caminhos: ferramenta única (REST etc.) e ferramentas
expandidas (conector/MCP), sem mudar o que a IA recebe.
"""

import json
import uuid
from types import SimpleNamespace

from pydantic import BaseModel

import orquestracao.agente as ag


class _Args(BaseModel):
    pass


def _inst(nome="Cria_Reembolso"):
    return SimpleNamespace(nome=nome, id=uuid.uuid4(), configuracao={})


def test_helper_registra_ok_false_com_status_e_corpo():
    erros = []
    ag._registrar_resposta_com_falha(
        {"ok": False, "status": 400, "corpo": {"message": "Invalid id"}},
        ferramenta="Cria_Reembolso", tipo="conector", instrumento_id="i1",
        irreversivel=True, erros=erros,
    )
    assert len(erros) == 1
    e = erros[0]
    assert e["origem"] == "resposta"
    assert "HTTP 400" in e["erro"] and "Invalid id" in e["erro"]
    assert e["irreversivel"] is True


def test_helper_ignora_sucesso_e_nao_dict():
    erros = []
    ag._registrar_resposta_com_falha(
        {"ok": True}, ferramenta="F", tipo="t", instrumento_id="i",
        irreversivel=False, erros=erros,
    )
    ag._registrar_resposta_com_falha(
        "texto solto", ferramenta="F", tipo="t", instrumento_id="i",
        irreversivel=False, erros=erros,
    )
    assert erros == []


def test_ferramenta_unica_registra_resposta_com_falha(monkeypatch):
    """O REST devolve HTTP 4xx como `{"ok": false, ...}` SEM levantar exceção —
    antes isso não deixava rastro nenhum."""
    tipo = SimpleNamespace(
        tipo="chamar_api_rest", descricao="d", Args=_Args, campo_mensagem=None
    )
    inst = _inst()
    monkeypatch.setattr(
        ag, "acionar_com_retentativa",
        lambda t, c, a: {"ok": False, "status": 400, "corpo": "Invalid id"},
    )
    monkeypatch.setattr(ag, "acao_irreversivel", lambda t, c: True)
    monkeypatch.setattr(
        ag, "atividade",
        SimpleNamespace(registrar=lambda m: None, mensagem_para=lambda *a: ""),
    )
    erros = []
    f = ag._ferramenta_unica(inst, tipo, None, [], {}, erros)
    retorno = json.loads(f.func())
    assert retorno["ok"] is False           # a resposta para a IA segue intacta
    assert erros and erros[0]["origem"] == "resposta"
    assert erros[0]["ferramenta"] == "Cria_Reembolso"
    assert "HTTP 400" in erros[0]["erro"]


def test_expandida_ganha_rastro_preservando_a_ferramenta():
    """Conector/MCP tratam a própria falha e devolvem `ok: false` como texto JSON —
    o embrulho registra sem mudar nome, schema nem o retorno da ferramenta."""
    def acionar(**kwargs):
        return json.dumps(
            {"ok": False, "erro": "A operação 'Cria_Reembolso' falhou: HTTP 400"}
        )

    tool = ag.StructuredTool.from_function(
        func=acionar, name="Cria_Reembolso", description="op", args_schema=_Args
    )
    erros, falhas = [], []
    w = ag._com_rastro_de_resposta(tool, _inst(), "conector", True, erros, falhas)
    assert w.name == "Cria_Reembolso"
    retorno = json.loads(w.func())
    assert retorno["ok"] is False
    assert erros[0]["ferramenta"] == "Cria_Reembolso"
    assert erros[0]["origem"] == "resposta"
    assert "HTTP 400" in erros[0]["erro"]
    # AÇÃO IRREVERSÍVEL que respondeu `ok: false` NÃO aconteceu: vira falha de
    # verdade (o lançamento perdido no Bubble), não só uma linha no rastro.
    assert falhas and "não completou a ação" in falhas[0]


def test_expandida_de_leitura_com_ok_false_nao_derruba():
    """Falha de LEITURA continua sendo só rastro — o agente decide o que fazer."""
    def acionar(**kwargs):
        return json.dumps({"ok": False, "erro": "busca instável"})

    tool = ag.StructuredTool.from_function(
        func=acionar, name="Busca", description="op", args_schema=_Args
    )
    erros, falhas = [], []
    w = ag._com_rastro_de_resposta(tool, _inst("Busca"), "conector", False, erros, falhas)
    json.loads(w.func())
    assert erros and falhas == []


def test_apos_falha_irreversivel_o_turno_para_de_agir():
    """Uma ação irreversível falhou: nenhuma outra ação roda no mesmo turno (antes o
    agente seguia publicando e narrando por cima de uma falha)."""
    chamadas = {"n": 0}

    def acionar(**kwargs):
        chamadas["n"] += 1
        return json.dumps({"ok": True})

    tool = ag.StructuredTool.from_function(
        func=acionar, name="Publica", description="op", args_schema=_Args
    )
    falhas = ["já falhou antes neste turno"]
    w = ag._com_rastro_de_resposta(tool, _inst("Publica"), "conector", True, [], falhas)
    retorno = json.loads(w.func())
    assert retorno["ok"] is False and chamadas["n"] == 0


def test_expandida_com_sucesso_ou_texto_nao_registra():
    def ok(**kwargs):
        return json.dumps({"ok": True, "corpo": []})

    def texto(**kwargs):
        return "resposta livre, não-JSON"

    erros = []
    w1 = ag._com_rastro_de_resposta(
        ag.StructuredTool.from_function(
            func=ok, name="Busca", description="x", args_schema=_Args
        ),
        _inst("Busca"), "conector", False, erros, [],
    )
    w2 = ag._com_rastro_de_resposta(
        ag.StructuredTool.from_function(
            func=texto, name="Livre", description="x", args_schema=_Args
        ),
        _inst("Livre"), "mcp", False, erros, [],
    )
    assert json.loads(w1.func())["ok"] is True
    assert w2.func() == "resposta livre, não-JSON"
    assert erros == []
