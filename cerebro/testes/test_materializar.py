"""Testes da materialização do rascunho da IA criadora (Fase 9).

O portão de segurança: o rascunho só vira linhas reais aqui, e em uma transação
atômica. Cobre o caminho feliz, as invariantes (um líder só, tipos válidos,
cadeia coerente), a recusa de rascunho incompleto, a dupla aprovação e — o mais
importante — a ATOMICIDADE: uma falha no meio não deixa nada para trás.

Sem LLM: os rascunhos são montados à mão (a IA não participa desta camada)."""

import uuid

import pytest
from sqlalchemy import select

import auditoria
from criacao.materializar import (
    ConflitoMaterializacao,
    RascunhoInvalido,
    materializar,
)
from criacao.rascunho import (
    AgenteRascunho,
    AutomacaoRascunho,
    InstrumentoRascunho,
    Rascunho,
)
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    ConversaCriacao,
    Instrumento,
    Time,
)


def _conversa(sessao, org, usuario, rascunho: Rascunho) -> ConversaCriacao:
    """Cria e PERSISTE a conversa (commit), como no mundo real a conversa já
    existe antes de aprovar — e isola a transação da materialização."""
    c = ConversaCriacao(
        organizacao_id=org.id,
        criada_por_id=usuario.id,
        rascunho=rascunho.model_dump(mode="json"),
    )
    sessao.add(c)
    sessao.commit()
    return c


def _rascunho_completo() -> Rascunho:
    """Time de Blog SEO: líder + redator, 1 instrumento no cinto do redator,
    cadeia líder→redator→fim."""
    inst = InstrumentoRascunho(nome="Busca na web", tipo="busca_web")
    lider = AgenteRascunho(nome="Maestro do Blog", papel="lider")
    redator = AgenteRascunho(nome="Redator SEO", papel="agente", cinto=[inst.ref])
    cadeia = {
        "inicio": lider.ref,
        "nos": {
            lider.ref: {
                "saidas": [
                    {"rotulo": "1", "quando": "sempre", "destino": redator.ref}
                ]
            },
            redator.ref: {
                "saidas": [{"rotulo": "1", "quando": "fim", "destino": None}]
            },
        },
    }
    return Rascunho(
        time_nome="Time de Blog SEO",
        time_descricao="Escreve artigos de SEO",
        agentes=[lider, redator],
        instrumentos=[inst],
        automacao=AutomacaoRascunho(nome="Publicar artigo", cadeia=cadeia),
    )


def test_materializa_time_completo(sessao, dados):
    org = dados["orgA"]
    rasc = _rascunho_completo()
    conversa = _conversa(sessao, org, dados["admin"], rasc)

    resumo = materializar(sessao, conversa, dados["admin"])

    assert resumo["agentes"] == 2
    assert resumo["instrumentos"] == 1
    assert resumo["automacao"] is True

    time = sessao.scalars(
        select(Time).where(Time.nome == "Time de Blog SEO")
    ).one()
    agentes = sessao.scalars(select(Agente).where(Agente.time_id == time.id)).all()
    assert {a.papel for a in agentes} == {"lider", "agente"}
    insts = sessao.scalars(
        select(Instrumento).where(Instrumento.time_id == time.id)
    ).all()
    assert len(insts) == 1 and insts[0].tipo == "busca_web"
    # cinto: o redator tem o instrumento pendurado (filtra aos agentes deste time —
    # o banco real tem vínculos de outros times)
    vinculos = sessao.scalars(
        select(AgenteInstrumento)
        .join(Agente, Agente.id == AgenteInstrumento.agente_id)
        .where(Agente.time_id == time.id)
    ).all()
    assert len(vinculos) == 1

    # a conversa fica materializada e aponta para o time real
    assert conversa.estado == "materializada"
    assert conversa.time_id == time.id


def test_automacao_nasce_inativa_com_cadeia_em_uuids(sessao, dados):
    """A automação nasce DESLIGADA (não dispara sozinha após a criação) e sua
    cadeia já está em uuids reais, não nos refs locais do rascunho."""
    org = dados["orgA"]
    conversa = _conversa(sessao, org, dados["admin"], _rascunho_completo())
    materializar(sessao, conversa, dados["admin"])

    auto = sessao.scalars(
        select(Automacao).where(Automacao.nome == "Publicar artigo")
    ).one()
    assert auto.ativa is False
    # as chaves dos nós são uuids dos agentes criados, não os refs do rascunho
    ids_agentes = {
        str(i)
        for i in sessao.scalars(
            select(Agente.id).where(Agente.time_id == auto.time_id)
        ).all()
    }
    assert set(auto.cadeia["nos"].keys()) <= ids_agentes
    assert auto.cadeia["inicio"] in ids_agentes


def test_time_sem_automacao_e_permitido(sessao, dados):
    rasc = Rascunho(
        time_nome="Só agentes",
        agentes=[AgenteRascunho(nome="Único", papel="lider")],
    )
    conversa = _conversa(sessao, dados["orgA"], dados["admin"], rasc)
    resumo = materializar(sessao, conversa, dados["admin"])
    assert resumo["automacao"] is False
    assert sessao.scalars(
        select(Automacao).join(Time).where(Time.nome == "Só agentes")
    ).first() is None


def test_dois_lideres_recusado(sessao, dados):
    rasc = Rascunho(
        time_nome="Dois chefes",
        agentes=[
            AgenteRascunho(nome="Chefe 1", papel="lider"),
            AgenteRascunho(nome="Chefe 2", papel="lider"),
        ],
    )
    conversa = _conversa(sessao, dados["orgA"], dados["admin"], rasc)
    with pytest.raises(RascunhoInvalido):
        materializar(sessao, conversa, dados["admin"])
    # nada criado
    assert sessao.scalars(
        select(Time).where(Time.nome == "Dois chefes")
    ).first() is None


def test_rascunho_incompleto_recusado(sessao, dados):
    # sem nome de time e sem agentes
    conversa = _conversa(sessao, dados["orgA"], dados["admin"], Rascunho())
    with pytest.raises(RascunhoInvalido) as exc:
        materializar(sessao, conversa, dados["admin"])
    assert exc.value.problemas  # tem motivos legíveis


def test_instrumento_tipo_desconhecido_recusado(sessao, dados):
    rasc = Rascunho(
        time_nome="Tipo errado",
        agentes=[AgenteRascunho(nome="X", papel="lider")],
        instrumentos=[InstrumentoRascunho(nome="Mágico", tipo="nao_existe")],
    )
    conversa = _conversa(sessao, dados["orgA"], dados["admin"], rasc)
    with pytest.raises(RascunhoInvalido):
        materializar(sessao, conversa, dados["admin"])


def test_cadeia_referenciando_agente_inexistente_recusada(sessao, dados):
    a = AgenteRascunho(nome="Solo", papel="lider")
    rasc = Rascunho(
        time_nome="Cadeia furada",
        agentes=[a],
        automacao=AutomacaoRascunho(
            cadeia={
                "inicio": a.ref,
                "nos": {
                    a.ref: {
                        "saidas": [
                            {"rotulo": "1", "quando": "x", "destino": "fantasma"}
                        ]
                    }
                },
            }
        ),
    )
    conversa = _conversa(sessao, dados["orgA"], dados["admin"], rasc)
    with pytest.raises(RascunhoInvalido):
        materializar(sessao, conversa, dados["admin"])


def test_aprovar_duas_vezes_conflito(sessao, dados):
    conversa = _conversa(sessao, dados["orgA"], dados["admin"], _rascunho_completo())
    materializar(sessao, conversa, dados["admin"])
    with pytest.raises(ConflitoMaterializacao):
        materializar(sessao, conversa, dados["admin"])


def test_falha_no_meio_desfaz_tudo(sessao, dados, monkeypatch):
    """ATOMICIDADE: se algo falha DEPOIS de já ter inserido linhas (aqui, a
    auditoria), o rollback desfaz tudo — nem o time, nem os agentes sobrevivem."""
    conversa = _conversa(sessao, dados["orgA"], dados["admin"], _rascunho_completo())

    def explodir(*a, **k):
        raise RuntimeError("falha simulada no fim da transação")

    monkeypatch.setattr(auditoria, "registrar", explodir)

    with pytest.raises(RuntimeError):
        materializar(sessao, conversa, dados["admin"])

    # nada persistiu: nem o time, nem os agentes
    assert sessao.scalars(
        select(Time).where(Time.nome == "Time de Blog SEO")
    ).first() is None
    assert sessao.scalars(
        select(Agente).where(Agente.nome == "Redator SEO")
    ).first() is None
    # a conversa continua em rascunho (pode tentar de novo)
    conversa_recarregada = sessao.get(ConversaCriacao, conversa.id)
    assert conversa_recarregada.estado == "rascunho"
