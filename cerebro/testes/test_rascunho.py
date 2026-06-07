"""Testes do schema do rascunho da IA criadora (Fase 9).

Puro Pydantic — sem banco. Garante os defaults, a geração de `ref`, o
round-trip JSON (é o que persiste em `conversas_criacao.rascunho`) e os helpers
de busca por ref.
"""

from criacao.rascunho import (
    AgenteRascunho,
    AutomacaoRascunho,
    InstrumentoRascunho,
    Rascunho,
)


def test_rascunho_vazio_e_valido():
    """Um rascunho recém-nascido é válido e vazio — a IA o preenche aos poucos."""
    r = Rascunho()
    assert r.time_nome is None
    assert r.agentes == []
    assert r.instrumentos == []
    assert r.automacao is None


def test_ref_gerado_automaticamente_e_unico():
    a1 = AgenteRascunho(nome="Redator")
    a2 = AgenteRascunho(nome="Revisor")
    assert a1.ref and a2.ref and a1.ref != a2.ref
    i = InstrumentoRascunho(nome="WordPress", tipo="wordpress")
    assert i.ref


def test_round_trip_json_preserva_tudo():
    """O rascunho vai e volta de JSONB sem perder estrutura."""
    r = Rascunho(
        time_nome="Time de Blog SEO",
        agentes=[AgenteRascunho(nome="Líder", papel="lider", cinto=["abc123"])],
        instrumentos=[
            InstrumentoRascunho(
                ref="abc123",
                nome="WordPress",
                tipo="wordpress",
                segredos_pendentes=["senha_app"],
            )
        ],
        automacao=AutomacaoRascunho(nome="Publicar artigo"),
    )
    bruto = r.model_dump(mode="json")
    volta = Rascunho.model_validate(bruto)
    assert volta.time_nome == "Time de Blog SEO"
    assert volta.agentes[0].papel == "lider"
    assert volta.agentes[0].cinto == ["abc123"]
    assert volta.instrumentos[0].segredos_pendentes == ["senha_app"]
    assert volta.automacao.nome == "Publicar artigo"


def test_helpers_busca_por_ref():
    a = AgenteRascunho(ref="ag1", nome="X")
    i = InstrumentoRascunho(ref="in1", nome="Y", tipo="busca_web")
    r = Rascunho(agentes=[a], instrumentos=[i])
    assert r.agente_por_ref("ag1") is a
    assert r.agente_por_ref("naoexiste") is None
    assert r.instrumento_por_ref("in1") is i


def test_tem_lider_respeita_excecao():
    r = Rascunho(
        agentes=[
            AgenteRascunho(ref="l", nome="Líder", papel="lider"),
            AgenteRascunho(ref="a", nome="Agente", papel="agente"),
        ]
    )
    assert r.tem_lider() is True
    # ao editar o próprio líder, ele não conta como "já existe outro líder"
    assert r.tem_lider(exceto_ref="l") is False
