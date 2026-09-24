"""Instrumento `quadro` — Entrega 2 do Cérebro (docs/CEREBRO-PLANO.md §5.3).

O que se prova: o agente lê e grava num quadro por um instrumento visível no cinto; o
acesso (ler × ler_e_escrever) decide as ferramentas; a ferramenta se descreve pela
estrutura do quadro; o carimbo sai do contexto de quem está agindo; a recusa volta como
dado E entra no que aconteceu na execução; e um time de OUTRA organização não alcança o
quadro, nem apontando pelo id.
"""

import json
import uuid
from contextlib import contextmanager

import pytest

import instrumentos as encaixe
from instrumentos.base import FalhaInstrumento
from modelos import Agente, Automacao, Execucao, Instrumento, Organizacao, Time, Usuario
from observabilidade import contexto
from orquestracao.agente import _ferramentas_de_instrumento
from quadros import servico as qs
from quadros.servico import Autor


@pytest.fixture(autouse=True)
def sessao_da_ferramenta(sessao, monkeypatch):
    """A ferramenta abre a PRÓPRIA sessão; no teste, ela usa a do teste (revertida)."""

    @contextmanager
    def _mesma():
        yield sessao

    monkeypatch.setattr("instrumentos.quadro._sessao", _mesma)


def _org(sessao, nome):
    u = Usuario(nome=nome, email=f"{nome}-{uuid.uuid4().hex[:6]}@x.com", ativo=True)
    sessao.add(u)
    sessao.flush()
    o = Organizacao(nome=nome, dono_id=u.id)
    sessao.add(o)
    sessao.flush()
    t = Time(organizacao_id=o.id, nome=f"Time {nome}")
    sessao.add(t)
    sessao.flush()
    return o, t


@pytest.fixture
def cenario(sessao):
    org, time = _org(sessao, "A")
    qs.criar_quadro(
        sessao, org.id, nome="Briefing por tema",
        descricao="Uma linha por tema, reescrita toda semana pelo Briefing de Pauta.",
        colunas=[
            {"nome": "Tema", "tipo": "opcao", "opcoes": ["COF", "PRO", "PES", "EST", "CAP"]},
            {"nome": "Atualizado em", "tipo": "data"},
            {"nome": "Briefing", "tipo": "texto_longo", "descricao": "até 400 caracteres"},
        ],
        chave=["Tema"],
    )
    return org, time


def _instrumento(sessao, time, *, acesso="ler_e_escrever", quadro="Briefing por tema"):
    inst = Instrumento(
        time_id=time.id, nome="Briefing do Painel", tipo="quadro",
        configuracao={"quadro": quadro, "acesso": acesso},
    )
    sessao.add(inst)
    sessao.flush()
    inst.segredos_decifrados = {}
    return inst


def _ferramentas(inst, erros=None):
    return {f.name.split("_Briefing")[0]: f for f in _ferramentas_de_instrumento(inst, [], {}, erros if erros is not None else [], {})}


def test_registrado_e_no_catalogo():
    t = encaixe.obter_tipo("quadro")
    assert t is not None and not t.acao_irreversivel
    assert "quadro" in [x.tipo for x in encaixe.tipos_disponiveis()]


def test_acesso_decide_as_ferramentas(sessao, cenario):
    _org_, time = cenario
    leitura = _ferramentas(_instrumento(sessao, time, acesso="ler"))
    assert set(leitura) == {"consultar", "totais", "ja_existe"}
    escrita = _ferramentas(_instrumento(sessao, time))
    assert set(escrita) == {
        "consultar", "totais", "ja_existe", "acrescentar", "atualizar", "gravar_pela_chave",
    }
    # Nenhuma ação do quadro pede aprovação (há histórico e dá para desfazer).
    assert all(f.metadata.get("irreversivel") is False for f in escrita.values())


def test_sem_chave_nao_oferece_gravar_pela_chave(sessao, cenario):
    org, time = cenario
    qs.criar_quadro(sessao, org.id, nome="Log", colunas=[{"nome": "msg", "tipo": "texto"}])
    inst = _instrumento(sessao, time, quadro="Log")
    nomes = {f.name.split("_Log")[0] for f in _ferramentas_de_instrumento(inst, [], {}, [], {})}
    assert "gravar_pela_chave" not in nomes and "acrescentar" in nomes


def test_a_ferramenta_se_descreve_pela_estrutura(sessao, cenario):
    _o, time = cenario
    desc = _ferramentas(_instrumento(sessao, time))["acrescentar"].description
    assert "Quadro “Briefing por tema”" in desc
    assert "Tema (opção de uma lista; obrigatória; opções: COF | PRO | PES | EST | CAP)" in desc
    assert "até 400 caracteres" in desc
    assert "Cada linha é identificada por: Tema" in desc


def test_grava_pela_chave_com_carimbo_do_agente_e_da_execucao(sessao, cenario):
    org, time = cenario
    ag = Agente(time_id=time.id, nome="Briefing de Pauta", papel="agente")
    auto = Automacao(time_id=time.id, nome="Painel", tipo_gatilho="manual")
    sessao.add_all([ag, auto])
    sessao.flush()
    ex = Execucao(automacao_id=auto.id)
    sessao.add(ex)
    sessao.flush()
    fs = _ferramentas(_instrumento(sessao, time))
    with contexto.usar_contexto(execucao_id=str(ex.id), agente_id=str(ag.id)):
        r = json.loads(fs["gravar_pela_chave"].invoke({"linhas": [
            {"Tema": "cof", "Atualizado em": "24/09/2026", "Briefing": "Atraem Goiás: x"},
        ]}))
        r2 = json.loads(fs["gravar_pela_chave"].invoke({"linhas": [
            {"Tema": "COF", "Briefing": "Atraem Goiás: y"},
        ]}))
    assert r["ok"] and r["criadas"] == 1
    assert r2["ok"] and r2["atualizadas"] == 1
    linha = qs.consultar(sessao, org.id, "Briefing por tema")["linhas"][0]
    assert linha["valores"]["Briefing"] == "Atraem Goiás: y"
    assert linha["valores"]["Atualizado em"] == "2026-09-24"  # não informada: ficou
    assert linha["carimbo"]["agente_id"] == str(ag.id)
    assert linha["carimbo"]["execucao_id"] == str(ex.id)
    assert linha["carimbo"]["origem"] == "agente"


def test_carimbo_sem_contexto_nao_derruba(sessao, cenario):
    _o, time = cenario
    r = json.loads(_ferramentas(_instrumento(sessao, time))["acrescentar"].invoke(
        {"linhas": [{"Tema": "PRO"}]}
    ))
    assert r["ok"]


def test_recusa_volta_como_dado_e_entra_no_que_aconteceu(sessao, cenario):
    _o, time = cenario
    erros: list[dict] = []
    fs = _ferramentas(_instrumento(sessao, time), erros)
    r = json.loads(fs["acrescentar"].invoke({"linhas": [
        {"Tema": "COF"}, {"Tema": "RH", "Atualizado em": "teste"},
    ]}))
    assert r["ok"] is False and "Nada foi gravado" in r["erro"]
    assert {(d["linha"], d["coluna"]) for d in r["detalhes"]} == {(2, "Tema"), (2, "Atualizado em")}
    # O agente não pode narrar "gravei": a recusa ficou registrada na execução.
    assert erros and erros[0]["tipo"] == "quadro"


def test_aceita_lista_mandada_como_texto_json(sessao, cenario):
    """A IA às vezes manda a lista como TEXTO — o Radar tinha até regra no markdown
    ("nunca use quebra de linha…") por causa disso."""
    _o, time = cenario
    fs = _ferramentas(_instrumento(sessao, time))
    r = json.loads(fs["acrescentar"].invoke(
        {"linhas": '[{"Tema": "EST",\n "Briefing": "linha 1\\nlinha 2"}]'}
    ))
    assert r["ok"] and r["criadas"] == 1


def test_consulta_compacta_e_so_a_mais_recente(sessao, cenario):
    org, time = cenario
    qs.gravar_linhas(
        sessao, org.id, "Briefing por tema",
        [{"Tema": "COF", "Atualizado em": "2026-09-17"}, {"Tema": "PRO", "Atualizado em": "2026-09-24"}],
        autor=Autor(origem="pessoa"),
    )
    fs = _ferramentas(_instrumento(sessao, time, acesso="ler"))
    r = json.loads(fs["consultar"].invoke({
        "colunas": ["Tema", "Atualizado em"], "so_o_mais_recente_de": "Atualizado em",
    }))
    assert r == {
        "ok": True, "quadro": "Briefing por tema", "total": 1, "devolvidas": 1,
        "proximo": None, "colunas": ["Tema", "Atualizado em"], "linhas": [["PRO", "2026-09-24"]],
    }
    t = json.loads(fs["totais"].invoke({"agrupar_por": ["Tema"]}))
    assert [g["valores"]["quantidade"] for g in t["resultados"]] == [1, 1]
    j = json.loads(fs["ja_existe"].invoke({"coluna": "Tema", "valores": ["COF", "CAP"]}))
    assert j["existem"] == ["COF"] and j["faltam"] == ["CAP"]


def test_atualizar_por_filtro(sessao, cenario):
    org, time = cenario
    qs.gravar_linhas(sessao, org.id, "Briefing por tema", [{"Tema": "PES"}], autor=Autor(origem="pessoa"))
    fs = _ferramentas(_instrumento(sessao, time))
    r = json.loads(fs["atualizar"].invoke({
        "filtros": [{"coluna": "Tema", "valor": "PES"}], "campos": {"Briefing": "amostra pequena"},
    }))
    assert r["ok"] and r["mudadas"] == 1


def test_outra_organizacao_nao_alcanca_nem_pelo_id(sessao, cenario):
    org, _time = cenario
    _org_b, time_b = _org(sessao, "B")
    qid = str(qs.obter_quadro(sessao, org.id, "Briefing por tema").id)
    for ref in ("Briefing por tema", qid):
        inst = _instrumento(sessao, time_b, quadro=ref)
        with pytest.raises(FalhaInstrumento, match="Não achei o quadro"):
            encaixe.obter_tipo("quadro").expandir_ferramentas_da_instancia(
                inst, encaixe.obter_tipo("quadro").Config.model_validate(inst.configuracao)
            )


def test_quadro_inexistente_sai_do_cinto_com_aviso(sessao, cenario):
    """Pelo motor: o instrumento que não acha o quadro sai do cinto COM aviso ao agente
    e registro na execução — o passo segue com o resto (nunca some calado)."""
    from modelos import Agente as Ag
    from orquestracao import agente as mod

    _o, time = cenario
    inst = _instrumento(sessao, time, quadro="Não existe")
    ag = Ag(time_id=time.id, nome="X", papel="agente")
    sessao.add(ag)
    sessao.flush()
    erros, falhas = [], []
    try:
        mod._ferramentas_de_instrumento(inst, falhas, {}, erros, {})
        pytest.fail("devia levantar")
    except FalhaInstrumento as e:
        mod._cinto_sem(inst, e, erros, falhas)
    assert erros[0]["origem"] == "cinto" and "Não achei o quadro" in erros[0]["erro"]
    assert falhas


def test_acionar_isolado_descreve():
    t = encaixe.obter_tipo("quadro")
    r = t.executar(t.Config(quadro="X", acesso="ler"), t.Args())
    assert r["acoes"] == ["consultar", "totais", "ja_existe"]
