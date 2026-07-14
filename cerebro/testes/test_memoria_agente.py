"""Testes da memória do AGENTE (o agente aprende com o próprio trabalho).

Cobrem: o serviço (`memoria_agente`) — upsert por assunto, recusa suave (vazio/teto),
busca vazia; as 2 ferramentas injetadas no runtime (`orquestracao/agente.py`) — gravar,
pesquisar (vazio não levanta), teto de escritas por run, e a injeção no prompt só no modo
"sempre"; a duplicação (copia o interruptor, NÃO as fichas); os endpoints CRUD
(operador+; observador 403); e a leitura pela IA criadora (`ver_memoria_agente`).
"""

import json

from sqlalchemy import select

import memoria_agente
import orquestracao.agente as agente_mod
from criacao.ferramentas import ContextoCriacao, ferramenta_por_nome
from modelos import Agente, ConversaCriacao


def _agente(sessao, dados, *, memoria_ativa=True, memoria_recall="sempre", nome="Ag"):
    ag = Agente(
        time_id=dados["timeA"].id,
        nome=nome,
        papel="agente",
        memoria_ativa=memoria_ativa,
        memoria_recall=memoria_recall,
    )
    sessao.add(ag)
    sessao.flush()
    return ag


def _usar_sessao(monkeypatch, sessao):
    """Faz as ferramentas (que abrem CriadorDeSessao) usarem a sessão do teste."""
    monkeypatch.setattr(sessao, "close", lambda: None)
    monkeypatch.setattr(agente_mod, "CriadorDeSessao", lambda: sessao)


# ───────────────────────── serviço (memoria_agente) ─────────────────────────


def test_upsert_por_assunto(sessao, dados):
    ag = _agente(sessao, dados)
    m1, s1 = memoria_agente.registrar(sessao, ag.id, "Cliente: Padaria", "sem glúten")
    assert s1 == "criada"
    m2, s2 = memoria_agente.registrar(
        sessao, ag.id, "Cliente: Padaria", "sem glúten E entrega 3ª"
    )
    assert s2 == "atualizada" and m2.id == m1.id
    fichas = memoria_agente.listar(sessao, ag.id)
    assert len(fichas) == 1 and "3ª" in fichas[0].conteudo


def test_pesquisar_sem_match_lista_vazia(sessao, dados):
    ag = _agente(sessao, dados)
    assert memoria_agente.pesquisar(sessao, ag.id) == []
    assert memoria_agente.pesquisar(sessao, ag.id, "inexistente") == []


def test_registrar_vazio_recusa(sessao, dados):
    ag = _agente(sessao, dados)
    m, s = memoria_agente.registrar(sessao, ag.id, "", "conteudo")
    assert m is None and s == "recusada:vazio"


def test_teto_recusa_assunto_novo(monkeypatch, sessao, dados):
    monkeypatch.setattr(memoria_agente, "TETO_FICHAS", 2)
    ag = _agente(sessao, dados)
    memoria_agente.registrar(sessao, ag.id, "A", "a")
    memoria_agente.registrar(sessao, ag.id, "B", "b")
    m, s = memoria_agente.registrar(sessao, ag.id, "C", "c")  # assunto NOVO → estoura
    assert m is None and s == "recusada:teto"
    # editar ficha JÁ existente segue permitido (não cria assunto novo)
    _, s2 = memoria_agente.registrar(sessao, ag.id, "A", "a2")
    assert s2 == "atualizada"


# ───────────────────────── ferramentas do runtime ─────────────────────────


def test_ferramentas_registrar_e_pesquisar(monkeypatch, sessao, dados):
    _usar_sessao(monkeypatch, sessao)
    ag = _agente(sessao, dados)
    fs = {f.name: f for f in agente_mod._ferramentas_de_memoria(ag.id, {"n": 0})}
    r = json.loads(fs["registrar_memoria"].func(assunto="Cliente X", conteudo="azul"))
    assert r["ok"] and r["status"] == "criada"
    p = json.loads(fs["pesquisar_memoria"].func(assunto="Cliente"))
    assert p["ok"] and len(p["memorias"]) == 1
    assert p["memorias"][0]["assunto"] == "Cliente X"


def test_pesquisar_vazio_nao_levanta(monkeypatch, sessao, dados):
    _usar_sessao(monkeypatch, sessao)
    ag = _agente(sessao, dados)
    fs = {f.name: f for f in agente_mod._ferramentas_de_memoria(ag.id, {"n": 0})}
    p = json.loads(fs["pesquisar_memoria"].func())
    assert p["ok"] is True and p["memorias"] == []


def test_max_escritas_por_run(monkeypatch, sessao, dados):
    _usar_sessao(monkeypatch, sessao)
    ag = _agente(sessao, dados)
    escritas = {"n": memoria_agente.MAX_ESCRITAS_POR_RUN}  # já no teto
    fs = {f.name: f for f in agente_mod._ferramentas_de_memoria(ag.id, escritas)}
    r = json.loads(fs["registrar_memoria"].func(assunto="A", conteudo="a"))
    assert r["ok"] is False and "limite" in r["erro"]


def test_instrucao_memoria_sempre_vs_sob_demanda(monkeypatch, sessao, dados):
    _usar_sessao(monkeypatch, sessao)
    ag = _agente(sessao, dados, memoria_recall="sempre")
    memoria_agente.registrar(sessao, ag.id, "Cliente X", "gosta de azul")
    txt = agente_mod._instrucao_de_memoria(ag)
    assert "gosta de azul" in txt  # modo "sempre" injeta as fichas
    ag2 = _agente(sessao, dados, memoria_recall="sob_demanda", nome="Ag2")
    memoria_agente.registrar(sessao, ag2.id, "Y", "segredo do conteudo")
    txt2 = agente_mod._instrucao_de_memoria(ag2)
    assert "segredo do conteudo" not in txt2 and "pesquisar_memoria" in txt2


# ───────────────────────── duplicação ─────────────────────────


def test_duplicacao_copia_interruptor_nao_fichas(sessao, dados):
    import duplicacao_time

    ag = _agente(
        sessao, dados, memoria_ativa=True, memoria_recall="sob_demanda", nome="Aprendiz"
    )
    memoria_agente.registrar(sessao, ag.id, "Cliente X", "aprendi algo")
    novo = duplicacao_time.duplicar_time(
        sessao, dados["timeA"], "Cópia", dados["admin"].id
    )
    copia = sessao.scalars(
        select(Agente).where(Agente.time_id == novo.id, Agente.nome == "Aprendiz")
    ).first()
    assert copia is not None
    assert copia.memoria_ativa is True and copia.memoria_recall == "sob_demanda"
    assert memoria_agente.listar(sessao, copia.id) == []  # fichas NÃO copiadas


# ───────────────────────── endpoints (tela do humano) ─────────────────────────


def test_endpoints_crud(cliente, entrar, sessao, dados):
    entrar(dados["operador"])
    ag = _agente(sessao, dados)
    r = cliente.post(
        f"/agentes/{ag.id}/memorias",
        json={"assunto": "Cliente X", "conteudo": "gosta de azul"},
    )
    assert r.status_code == 201
    mid = r.json()["id"]
    r = cliente.get(f"/agentes/{ag.id}/memorias")
    assert r.status_code == 200 and len(r.json()) == 1
    r = cliente.put(f"/memorias-agente/{mid}", json={"conteudo": "gosta de verde"})
    assert r.status_code == 200 and "verde" in r.json()["conteudo"]
    r = cliente.delete(f"/memorias-agente/{mid}")
    assert r.status_code == 204
    assert memoria_agente.listar(sessao, ag.id) == []


def test_endpoint_observador_nao_grava(cliente, entrar, sessao, dados):
    ag = _agente(sessao, dados)
    entrar(dados["observador"])
    r = cliente.post(
        f"/agentes/{ag.id}/memorias", json={"assunto": "A", "conteudo": "a"}
    )
    assert r.status_code == 403


# ───────────────────────── leitura pela IA criadora ─────────────────────────


def test_criadora_ve_memoria_agente(sessao, dados):
    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id,
        criada_por_id=dados["admin"].id,
        time_id=dados["timeA"].id,
    )
    sessao.add(conversa)
    sessao.flush()
    ag = _agente(sessao, dados)
    memoria_agente.registrar(sessao, ag.id, "Cliente X", "gosta de azul")
    f = ferramenta_por_nome(
        ContextoCriacao(sessao=sessao, conversa=conversa, usuario=dados["admin"])
    )
    assert "ver_memoria_agente" in f
    r = json.loads(f["ver_memoria_agente"].func(agente_id=str(ag.id)))
    assert r["ok"] and len(r["memorias"]) == 1
    assert r["memorias"][0]["assunto"] == "Cliente X"
