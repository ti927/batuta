"""Testes da memória de longo prazo do projeto (Fase 10, abordagem destilada).

Cobrem: gravar/listar/esquecer no serviço; a categoria inválida virar 'fato'; o
filtro de busca; o ISOLAMENTO ESTRITO entre projetos (uma conversa nunca vê nem
apaga a memória de outra); as ferramentas lembrar/recordar/esquecer; e a injeção da
memória no prompt da criadora.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

from criacao import memoria
from criacao.ferramentas import ContextoCriacao, ferramenta_por_nome
from criacao.prompt import montar_prompt_criadora
from modelos import ConversaCriacao


def _conversa(sessao, org, usuario):
    c = ConversaCriacao(organizacao_id=org.id, criada_por_id=usuario.id)
    sessao.add(c)
    sessao.flush()
    return c


def _chamar(f, ferramenta, **kwargs):
    return json.loads(f[ferramenta].func(**kwargs))


# ─────────────────────────── Serviço ───────────────────────────

def test_lembrar_e_listar_recente_primeiro(sessao, dados):
    c = _conversa(sessao, dados["orgA"], dados["admin"])
    m1 = memoria.lembrar(sessao, c, categoria="fato", conteudo="Primeiro fato")
    m2 = memoria.lembrar(sessao, c, categoria="decisao", conteudo="Segunda decisão")
    # `now()` é o horário de início da transação (igual para os dois no mesmo turno);
    # fixamos timestamps distintos para provar que a listagem vem da mais recente.
    agora = datetime.now(timezone.utc)
    m1.criado_em = agora - timedelta(minutes=5)
    m2.criado_em = agora
    sessao.flush()
    itens = memoria.listar(sessao, c)
    assert [m.conteudo for m in itens] == ["Segunda decisão", "Primeiro fato"]
    assert itens[0].categoria == "decisao"


def test_categoria_invalida_vira_fato(sessao, dados):
    c = _conversa(sessao, dados["orgA"], dados["admin"])
    m = memoria.lembrar(sessao, c, categoria="inventada", conteudo="x")
    assert m.categoria == "fato"


def test_busca_filtra_por_substring(sessao, dados):
    c = _conversa(sessao, dados["orgA"], dados["admin"])
    memoria.lembrar(sessao, c, categoria="fato", conteudo="O público é o decisor")
    memoria.lembrar(sessao, c, categoria="fato", conteudo="Tom de voz formal")
    achados = memoria.listar(sessao, c, busca="DECISOR")
    assert len(achados) == 1 and "decisor" in achados[0].conteudo


def test_esquecer_apaga(sessao, dados):
    c = _conversa(sessao, dados["orgA"], dados["admin"])
    m = memoria.lembrar(sessao, c, categoria="fato", conteudo="some daqui")
    assert memoria.esquecer(sessao, c, m.id) is True
    assert memoria.listar(sessao, c) == []
    # apagar de novo (já não existe) é inofensivo
    assert memoria.esquecer(sessao, c, m.id) is False


# ─────────────────────── Isolamento estrito ───────────────────────

def test_uma_conversa_nao_ve_memoria_de_outra(sessao, dados):
    a = _conversa(sessao, dados["orgA"], dados["admin"])
    b = _conversa(sessao, dados["orgB"], dados["estranho"])
    memoria.lembrar(sessao, a, categoria="fato", conteudo="segredo do projeto A")
    assert memoria.listar(sessao, b) == []
    assert [m.conteudo for m in memoria.listar(sessao, a)] == ["segredo do projeto A"]


def test_nao_apaga_memoria_de_outro_projeto(sessao, dados):
    a = _conversa(sessao, dados["orgA"], dados["admin"])
    b = _conversa(sessao, dados["orgB"], dados["estranho"])
    m = memoria.lembrar(sessao, a, categoria="fato", conteudo="só de A")
    # a conversa B tenta apagar uma memória de A: recusado, e a memória continua lá.
    assert memoria.esquecer(sessao, b, m.id) is False
    assert len(memoria.listar(sessao, a)) == 1


# ───────────────────────── Ferramentas ─────────────────────────

def test_ferramentas_lembrar_recordar_esquecer(sessao, dados):
    c = _conversa(sessao, dados["orgA"], dados["admin"])
    f = ferramenta_por_nome(ContextoCriacao(sessao=sessao, conversa=c, usuario=dados["admin"]))

    assert _chamar(f, "lembrar", categoria="preferencia", conteudo="Gosta de tom direto")["ok"]
    rec = _chamar(f, "recordar")
    assert len(rec["memorias"]) == 1
    mid = rec["memorias"][0]["id"]
    assert rec["memorias"][0]["categoria"] == "preferencia"

    # recordar com busca que não casa
    assert _chamar(f, "recordar", busca="nada-a-ver")["memorias"] == []
    # esquecer pelo id
    assert _chamar(f, "esquecer", memoria_id=mid)["ok"]
    assert _chamar(f, "recordar")["memorias"] == []
    # esquecer id inexistente → erro como dado
    assert _chamar(f, "esquecer", memoria_id=str(uuid.uuid4()))["ok"] is False


# ─────────────────────── Injeção no prompt ───────────────────────

def test_memoria_entra_no_prompt(sessao, dados):
    c = _conversa(sessao, dados["orgA"], dados["admin"])
    memoria.lembrar(sessao, c, categoria="fato", conteudo="fato-injetado-xyz")
    prompt = montar_prompt_criadora(None, memoria.para_o_prompt(sessao, c))
    assert "memória de longo prazo" in prompt
    assert "fato-injetado-xyz" in prompt


def test_prompt_sem_memoria_nao_traz_secao(sessao, dados):
    prompt = montar_prompt_criadora(None, [])
    assert "O que você já sabe deste projeto" not in prompt
