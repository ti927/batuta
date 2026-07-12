"""Testes da duplicação de TIME (POST /times/{id}/duplicar).

Cobre o que o estudo apontou como delicado: o grafo de propriedade copiado por
inteiro (agentes, instrumentos, cinto, automações), o REMAPEAMENTO das referências
internas da cadeia (ref de agente + aprovacao.instrumento_id, no formato novo E no
legado em que o id do nó é o agente), os segredos (inline copiado / canal nasce
desconectado), a memória da IA companheira herdada, a ausência de dados de runtime,
a matriz de acesso (admin cria; operador/observador 403; estranho 404) e o deep-copy
que isola a cópia. Roda na transação revertida do conftest.
"""

import uuid

import pytest
from sqlalchemy import select

import segredos_instrumento
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    ConversaCriacao,
    Instrumento,
    MemoriaProjeto,
    SegredoInstrumento,
    Time,
)
from orquestracao import grafo


@pytest.fixture
def time_rico(sessao, dados):
    """Monta um time A completo: líder + trabalhador, um instrumento comum (com
    segredo inline), um canal Telegram (com token + webhook), o cinto, uma automação
    nova (com portão por canal) e uma automação em formato LEGADO, mais a conversa
    da IA com memórias. Devolve os ids originais para conferir o remapeamento."""
    tA = dados["timeA"]
    lider = Agente(time_id=tA.id, nome="Líder", papel="lider", agent_md="manda")
    worker = Agente(time_id=tA.id, nome="Trabalhador", papel="agente", soul_md="alma")
    sessao.add_all([lider, worker])
    sessao.flush()

    comum = Instrumento(
        time_id=tA.id, nome="Busca", tipo="busca_web", configuracao={"profundidade": "basica"}
    )
    canal = Instrumento(
        time_id=tA.id, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": "555"},
        webhook_secret="xyz",  # canal conectado (crachá em coluna própria)
    )
    sessao.add_all([comum, canal])
    sessao.flush()
    segredos_instrumento.salvar_segredos(sessao, comum.id, {"chave_api": "SECRET123"})
    segredos_instrumento.salvar_segredos(sessao, canal.id, {"token_bot": "BOTTOKEN"})

    # cinto: o trabalhador carrega os dois instrumentos
    sessao.add_all([
        AgenteInstrumento(agente_id=worker.id, instrumento_id=comum.id),
        AgenteInstrumento(agente_id=worker.id, instrumento_id=canal.id),
    ])

    auto_nova = Automacao(
        time_id=tA.id, nome="Fluxo", tipo_gatilho="manual", configuracao_gatilho={},
        cadeia={
            "inicial": "n1",
            "nos": [
                {"id": "gatilho", "tipo": "gatilho", "gatilho": "manual",
                 "saidas": [{"rotulo": "inicia", "destino": "n1"}]},
                {"id": "n1", "tipo": "agente", "ref": str(worker.id), "gate": True,
                 "aprovacao": {"instrumento_id": str(canal.id), "destinatario": "555"},
                 "saidas": [{"rotulo": "ok", "destino": "fim"}]},
                {"id": "fim", "tipo": "fim", "saidas": []},
            ],
        },
        ativa=False,
    )
    # formato LEGADO: nos é DICT e o id do nó é o próprio agente_id
    auto_legada = Automacao(
        time_id=tA.id, nome="Legada", tipo_gatilho="manual", configuracao_gatilho={},
        cadeia={
            "inicio": str(lider.id),
            "nos": {
                str(lider.id): {
                    "pausa_humano": False,
                    "saidas": [{"rotulo": "ok", "quando": "", "destino": None}],
                }
            },
        },
        ativa=False,
    )
    sessao.add_all([auto_nova, auto_legada])

    conversa = ConversaCriacao(
        organizacao_id=tA.organizacao_id, criada_por_id=dados["admin"].id,
        titulo="Time A", time_id=tA.id,
        mensagens=[{"papel": "usuario", "texto": "oi"}],
    )
    sessao.add(conversa)
    sessao.flush()
    sessao.add_all([
        MemoriaProjeto(conversa_id=conversa.id, organizacao_id=tA.organizacao_id,
                       categoria="decisao", conteudo="Tom formal."),
        MemoriaProjeto(conversa_id=conversa.id, organizacao_id=tA.organizacao_id,
                       categoria="fato", conteudo="Cliente é fintech."),
    ])
    sessao.flush()
    return {
        "time": tA, "lider": lider, "worker": worker, "comum": comum, "canal": canal,
        "lider_id": lider.id, "worker_id": worker.id, "comum_id": comum.id,
        "canal_id": canal.id,
    }


def _agentes(sessao, time_id):
    return {a.nome: a for a in sessao.scalars(
        select(Agente).where(Agente.time_id == time_id))}


def _instrumentos(sessao, time_id):
    return {i.nome: i for i in sessao.scalars(
        select(Instrumento).where(Instrumento.time_id == time_id))}


def test_duplica_grafo_completo(cliente, entrar, dados, sessao, time_rico):
    entrar(dados["admin"])
    r = cliente.post(f"/times/{time_rico['time'].id}/duplicar", json={"nome": "Cópia"})
    assert r.status_code == 201
    novo = r.json()
    assert novo["id"] != str(time_rico["time"].id)        # id novo
    assert novo["nome"] == "Cópia"
    assert novo["organizacao_id"] == str(dados["orgA"].id)  # mesma org

    ags = _agentes(sessao, uuid.UUID(novo["id"]))
    assert set(ags) == {"Líder", "Trabalhador"}
    assert ags["Líder"].papel == "lider" and ags["Líder"].agent_md == "manda"
    assert ags["Trabalhador"].soul_md == "alma"
    assert ags["Líder"].id != time_rico["lider_id"]        # ids novos

    insts = _instrumentos(sessao, uuid.UUID(novo["id"]))
    assert set(insts) == {"Busca", "Bot"}

    # cinto recriado com os ids novos (o trabalhador novo carrega os dois novos)
    cinto = sessao.scalars(
        select(AgenteInstrumento.instrumento_id)
        .where(AgenteInstrumento.agente_id == ags["Trabalhador"].id)
    ).all()
    assert set(cinto) == {insts["Busca"].id, insts["Bot"].id}


def test_remapeia_cadeia_nova(cliente, entrar, dados, sessao, time_rico):
    entrar(dados["admin"])
    novo = cliente.post(
        f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"}
    ).json()
    ags = _agentes(sessao, uuid.UUID(novo["id"]))
    insts = _instrumentos(sessao, uuid.UUID(novo["id"]))
    auto = sessao.scalars(
        select(Automacao).where(
            Automacao.time_id == uuid.UUID(novo["id"]), Automacao.nome == "Fluxo"
        )
    ).one()
    assert auto.ativa is False
    n1 = next(n for n in auto.cadeia["nos"] if n.get("tipo") == "agente")
    assert n1["ref"] == str(ags["Trabalhador"].id)                  # ref remapeado
    assert n1["aprovacao"]["instrumento_id"] == str(insts["Bot"].id)  # portão remapeado
    # e NÃO aponta mais para os ids do time original
    assert n1["ref"] != str(time_rico["worker_id"])
    assert n1["aprovacao"]["instrumento_id"] != str(time_rico["canal_id"])


def test_remapeia_cadeia_legada(cliente, entrar, dados, sessao, time_rico):
    """No formato legado o id do nó é o próprio agente_id — tem que ser remapeado."""
    entrar(dados["admin"])
    novo = cliente.post(
        f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"}
    ).json()
    ags = _agentes(sessao, uuid.UUID(novo["id"]))
    auto = sessao.scalars(
        select(Automacao).where(
            Automacao.time_id == uuid.UUID(novo["id"]), Automacao.nome == "Legada"
        )
    ).one()
    no_ag = next(n for n in auto.cadeia["nos"] if n.get("tipo") == "agente")
    novo_lider = str(ags["Líder"].id)
    assert no_ag["ref"] == novo_lider
    assert no_ag["id"] == novo_lider                 # id do nó remapeado também
    assert auto.cadeia["inicial"] == novo_lider      # inicial remapeado
    # nenhum vestígio do id antigo do líder
    assert str(time_rico["lider_id"]) not in str(auto.cadeia)


def test_segredo_nao_canal_copiado(cliente, entrar, dados, sessao, time_rico):
    entrar(dados["admin"])
    novo = cliente.post(
        f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"}
    ).json()
    insts = _instrumentos(sessao, uuid.UUID(novo["id"]))
    decifrado = segredos_instrumento.decifrar(sessao, insts["Busca"].id)
    assert decifrado.get("chave_api") == "SECRET123"  # copiado e decifrável


def test_canal_nasce_desconectado(cliente, entrar, dados, sessao, time_rico):
    entrar(dados["admin"])
    novo = cliente.post(
        f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"}
    ).json()
    insts = _instrumentos(sessao, uuid.UUID(novo["id"]))
    bot = insts["Bot"]
    # sem token (segredo do canal não é copiado)
    segs = sessao.scalars(
        select(SegredoInstrumento).where(SegredoInstrumento.instrumento_id == bot.id)
    ).all()
    assert segs == []
    # canal nasce "a conectar": sem crachá (webhook_secret); config preservada
    assert bot.webhook_secret is None
    assert bot.configuracao.get("destinatario_padrao") == "555"
    assert bot.credencial_id is None


def test_memoria_da_ia_herdada(cliente, entrar, dados, sessao, time_rico):
    entrar(dados["admin"])
    novo = cliente.post(
        f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"}
    ).json()
    conversa = sessao.scalars(
        select(ConversaCriacao).where(
            ConversaCriacao.time_id == uuid.UUID(novo["id"])
        )
    ).one()
    # A conversa RECOMEÇA LIMPA (o histórico literal carregaria ids do time original e
    # confundiria a IA); herda a MEMÓRIA durável + ganha uma nota de proveniência.
    assert conversa.mensagens == []
    conteudos = {
        m.conteudo
        for m in sessao.scalars(
            select(MemoriaProjeto).where(MemoriaProjeto.conversa_id == conversa.id)
        ).all()
    }
    assert "Tom formal." in conteudos and "Cliente é fintech." in conteudos  # herdadas
    assert any("duplicado de" in c for c in conteudos)  # proveniência, sem ids stale


def test_runtime_nao_copiado(cliente, entrar, dados, sessao, time_rico):
    """A cópia nasce sem histórico operacional (sem execuções)."""
    entrar(dados["admin"])
    novo = cliente.post(
        f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"}
    ).json()
    from modelos import Execucao
    execs = sessao.scalars(
        select(Execucao)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .where(Automacao.time_id == uuid.UUID(novo["id"]))
    ).all()
    assert execs == []


def test_deep_copy_nao_mexe_no_original(cliente, entrar, dados, sessao, time_rico):
    entrar(dados["admin"])
    cliente.post(f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"})
    # a automação original ainda aponta para o agente ORIGINAL (não foi mutada)
    original = sessao.scalars(
        select(Automacao).where(
            Automacao.time_id == time_rico["time"].id, Automacao.nome == "Fluxo"
        )
    ).one()
    n1 = next(n for n in original.cadeia["nos"] if n.get("tipo") == "agente")
    assert n1["ref"] == str(time_rico["worker_id"])


def test_nome_em_branco_422(cliente, entrar, dados, time_rico):
    entrar(dados["admin"])
    r = cliente.post(f"/times/{time_rico['time'].id}/duplicar", json={"nome": "  "})
    assert r.status_code == 422


def test_operador_403(cliente, entrar, dados, time_rico):
    entrar(dados["operador"])  # operador não cria time (duplicar exige admin)
    r = cliente.post(f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"})
    assert r.status_code == 403


def test_observador_403(cliente, entrar, dados, time_rico):
    entrar(dados["observador"])
    r = cliente.post(f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"})
    assert r.status_code == 403


def test_estranho_404(cliente, entrar, dados, time_rico):
    entrar(dados["estranho"])  # de outra organização → nem enxerga
    r = cliente.post(f"/times/{time_rico['time'].id}/duplicar", json={"nome": "C"})
    assert r.status_code == 404
