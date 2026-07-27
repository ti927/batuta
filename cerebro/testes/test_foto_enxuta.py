"""Parte E (economia de tokens da IA criadora): a foto do time que vai no PROMPT é
ENXUTA — só a ESTRUTURA, sem os 4 markdowns dos agentes nem a cadeia das automações —
e a IA puxa esse detalhe sob demanda com ver_agente/ver_automacao. A foto CHEIA
continua indo para o front (redesenhar o canvas) e para o ver_time."""

import json

from criacao.ferramentas import (
    ContextoCriacao,
    enxugar_snapshot,
    ferramenta_por_nome,
    snapshot_time,
)
from criacao.prompt import montar_prompt_criadora
from modelos import ConversaCriacao

_ID_INEXISTENTE = "00000000-0000-0000-0000-000000000000"


def _setup(sessao, dados):
    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id, criada_por_id=dados["admin"].id
    )
    sessao.add(conversa)
    sessao.flush()
    ctx = ContextoCriacao(sessao=sessao, conversa=conversa, usuario=dados["admin"])
    return ctx, conversa, ferramenta_por_nome(ctx)


def _chamar(f, ferramenta, **kwargs):
    return json.loads(f[ferramenta].func(**kwargs))


def _montar_time(f):
    """Time com líder → agente (com markdowns), um instrumento e uma cadeia."""
    _chamar(f, "definir_time", nome="Blog SEO")
    a1 = _chamar(
        f, "adicionar_agente", nome="Chefe", papel="lider",
        agent_md="AGENT_CHEFE_MD", skill_md="SKILL_CHEFE_MD",
    )["id"]
    a2 = _chamar(
        f, "adicionar_agente", nome="Redator", papel="agente", soul_md="SOUL_REDATOR_MD"
    )["id"]
    _chamar(f, "configurar_instrumento", nome="Busca", tipo="busca_web")
    cadeia = {
        "inicio": a1,
        "nos": {
            a1: {"saidas": [{"rotulo": "1", "quando": "x", "destino": a2}]},
            a2: {"saidas": [{"rotulo": "1", "quando": "fim", "destino": None}]},
        },
    }
    _chamar(f, "montar_cadeia", cadeia=cadeia)
    return a1, a2


def test_enxugar_snapshot_tira_markdowns_e_cadeia_mantendo_estrutura(sessao, dados):
    _ctx, conversa, f = _setup(sessao, dados)
    _montar_time(f)
    cheia = snapshot_time(sessao, conversa)
    # A foto CHEIA (a que vai para o front) TEM os markdowns e a cadeia.
    ag_cheia = {a["nome"]: a for a in cheia["agentes"]}
    assert ag_cheia["Chefe"]["agent_md"] == "AGENT_CHEFE_MD"
    assert cheia["automacoes"][0]["cadeia"]["nos"]

    enxuta = enxugar_snapshot(cheia)
    ag = {a["nome"]: a for a in enxuta["agentes"]}
    # Estrutura mantida (nome/papel/id/modelo/cinto), markdowns FORA.
    assert set(ag["Chefe"].keys()) == {"id", "nome", "papel", "modelo_ia", "cinto"}
    assert ag["Chefe"]["papel"] == "lider"
    assert "agent_md" not in ag["Chefe"] and "skill_md" not in ag["Chefe"]
    assert "soul_md" not in ag["Redator"]
    # Automação sem cadeia, mas com nome/gatilho/ativa/id.
    auto = enxuta["automacoes"][0]
    assert "cadeia" not in auto
    assert {"id", "nome", "tipo_gatilho", "ativa"} <= set(auto.keys())
    assert "cadeia" not in (enxuta["automacao"] or {})
    # Instrumentos ficam INTEIROS (pequenos e guiam a decisão da IA).
    assert enxuta["instrumentos"] == cheia["instrumentos"]
    # A foto CHEIA não foi mutada pela projeção.
    assert ag_cheia["Chefe"]["agent_md"] == "AGENT_CHEFE_MD"


def test_enxugar_snapshot_none_e_vazio():
    assert enxugar_snapshot(None) is None
    assert enxugar_snapshot({}) == {}


def test_prompt_da_criadora_nao_leva_markdowns_nem_cadeia(sessao, dados):
    _ctx, conversa, f = _setup(sessao, dados)
    _montar_time(f)
    cheia = snapshot_time(sessao, conversa)
    prompt_cheio = montar_prompt_criadora(cheia)
    prompt_enxuto = montar_prompt_criadora(enxugar_snapshot(cheia))
    # O markdown vaza no prompt com a foto CHEIA (comportamento antigo) e SOME no enxuto.
    assert "AGENT_CHEFE_MD" in prompt_cheio
    assert "AGENT_CHEFE_MD" not in prompt_enxuto
    assert "SOUL_REDATOR_MD" not in prompt_enxuto
    # A estrutura continua no prompt (a IA sabe o que existe e os ids).
    assert "Chefe" in prompt_enxuto and "Redator" in prompt_enxuto
    # E o prompt orienta a IA a pedir o detalhe sob demanda.
    assert "ver_agente" in prompt_enxuto and "ver_automacao" in prompt_enxuto


def test_ver_agente_traz_os_markdowns(sessao, dados):
    _ctx, _conversa, f = _setup(sessao, dados)
    a1, _a2 = _montar_time(f)
    r = json.loads(f["ver_agente"].func(agente_id=a1))
    assert r["agent_md"] == "AGENT_CHEFE_MD"
    assert r["skill_md"] == "SKILL_CHEFE_MD"
    assert r["nome"] == "Chefe" and r["papel"] == "lider"
    # id inexistente → erro como DADO (a IA corrige na conversa).
    assert json.loads(f["ver_agente"].func(agente_id=_ID_INEXISTENTE))["ok"] is False


def test_ver_automacao_traz_a_cadeia(sessao, dados):
    _ctx, conversa, f = _setup(sessao, dados)
    a1, a2 = _montar_time(f)
    auto_id = snapshot_time(sessao, conversa)["automacoes"][0]["id"]
    r = json.loads(f["ver_automacao"].func(automacao_id=auto_id))
    nos = {n["id"]: n for n in r["cadeia"]["nos"]}
    assert a1 in nos and a2 in nos
    # id inexistente → erro como DADO.
    assert json.loads(f["ver_automacao"].func(automacao_id=_ID_INEXISTENTE))["ok"] is False
