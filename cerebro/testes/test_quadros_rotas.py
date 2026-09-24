"""Rotas dos quadros — Entrega 4 do Cérebro (a tela). Papéis, isolamento, recusa
legível (200 + ok:false), busca livre, importação com prévia/pular, desfazer por
execução, histórico com nomes e exportação."""

from modelos import Agente, Automacao, Execucao
from quadros import servico as qs
from quadros.servico import Autor

CSV = "Data;Tema;Pergunta\n21/09/2026;COF;1\nteste;COF;2\n21/09/2026;RH;3\n21/09/2026;PRO;4\n"


def _base(o):
    return f"/organizacoes/{o.id}/quadros"


def _criar(cliente, dados):
    r = cliente.post(_base(dados["orgA"]), json={
        "nome": "Radar", "descricao": "Uma linha por pergunta.",
        "colunas": [{"nome": "Data", "tipo": "data"},
                    {"nome": "Tema", "tipo": "opcao", "opcoes": ["COF", "PRO"]},
                    {"nome": "Pergunta", "tipo": "numero"}],
        "chave": ["Data", "Pergunta"],
    })
    assert r.status_code == 200 and r.json()["ok"], r.text
    return r.json()["quadro_id"]


def test_papeis(cliente, entrar, dados):
    entrar(dados["observador"])
    assert cliente.post(_base(dados["orgA"]), json={"nome": "X", "colunas": [{"nome": "a", "tipo": "texto"}]}).status_code == 403
    entrar(dados["operador"])
    qid = _criar(cliente, dados)
    assert cliente.delete(f"{_base(dados['orgA'])}/{qid}").status_code == 403
    entrar(dados["observador"])
    assert cliente.get(_base(dados["orgA"])).json()[0]["nome"] == "Radar"
    assert cliente.post(f"{_base(dados['orgA'])}/{qid}/linhas", json={"linhas": [{"Data": "2026-09-21", "Pergunta": 1}]}).status_code == 403
    entrar(dados["admin"])
    previa = cliente.delete(f"{_base(dados['orgA'])}/{qid}?simular=true").json()
    assert previa["simulado"] and cliente.get(_base(dados["orgA"])).json()
    assert cliente.delete(f"{_base(dados['orgA'])}/{qid}").json()["ok"]
    assert cliente.get(_base(dados["orgA"])).json() == []


def test_isolamento(cliente, entrar, dados):
    entrar(dados["operador"])
    qid = _criar(cliente, dados)
    entrar(dados["estranho"])
    # O guarda do projeto responde 404 a quem não é da organização (nem revela que existe).
    assert cliente.get(_base(dados["orgA"])).status_code in (403, 404)
    # Nem pela organização DELE com o id do quadro da outra.
    assert cliente.get(f"{_base(dados['orgB'])}/{qid}").status_code == 404


def test_recusa_legivel_e_busca(cliente, entrar, dados):
    entrar(dados["operador"])
    qid = _criar(cliente, dados)
    r = cliente.post(f"{_base(dados['orgA'])}/{qid}/linhas", json={"linhas": [{"Data": "teste", "Pergunta": 1}]})
    assert r.status_code == 200 and r.json()["ok"] is False
    assert r.json()["detalhes"][0]["coluna"] == "Data"
    cliente.post(f"{_base(dados['orgA'])}/{qid}/linhas", json={"linhas": [
        {"Data": "21/09/2026", "Tema": "COF", "Pergunta": 1},
        {"Data": "21/09/2026", "Tema": "PRO", "Pergunta": 2},
    ]})
    c = cliente.post(f"{_base(dados['orgA'])}/{qid}/consulta", json={"busca": "pro"}).json()
    assert c["total"] == 1 and c["linhas"][0]["valores"]["Tema"] == "PRO"
    assert c["linhas"][0]["carimbo"]["usuario_nome"] == dados["operador"].nome
    lista = cliente.get(_base(dados["orgA"])).json()[0]
    assert lista["linhas"] == 2 and lista["ultima_gravacao"]


def test_editar_linha_e_historico_com_nomes(cliente, entrar, dados):
    entrar(dados["operador"])
    qid = _criar(cliente, dados)
    cliente.post(f"{_base(dados['orgA'])}/{qid}/linhas", json={"linhas": [{"Data": "2026-09-21", "Tema": "COF", "Pergunta": 1}]})
    lid = cliente.post(f"{_base(dados['orgA'])}/{qid}/consulta", json={}).json()["linhas"][0]["id"]
    ruim = cliente.patch(f"{_base(dados['orgA'])}/{qid}/linhas/{lid}", json={"campos": {"Tema": "RH"}}).json()
    assert ruim["ok"] is False
    ok = cliente.patch(f"{_base(dados['orgA'])}/{qid}/linhas/{lid}", json={"campos": {"Tema": "PRO"}}).json()
    assert ok["ok"] and ok["mudadas"] == 1
    h = cliente.get(f"{_base(dados['orgA'])}/{qid}/linhas/{lid}/historico").json()["alteracoes"]
    assert [a["acao"] for a in h] == ["criou", "mudou"] and h[1]["usuario_nome"] == dados["operador"].nome


def test_importar_previa_e_pular(cliente, entrar, dados):
    entrar(dados["operador"])
    qid = _criar(cliente, dados)
    p = cliente.post(f"{_base(dados['orgA'])}/{qid}/importar/previa", json={"csv": CSV}).json()
    assert p["linhas_no_csv"] == 4
    assert {x["linha"] for x in p["problemas"]} == {3, 4}  # "teste" e "RH"
    assert [m["vai_para"] for m in p["mapeamento"]] == ["Data", "Tema", "Pergunta"]
    tudo = cliente.post(f"{_base(dados['orgA'])}/{qid}/importar", json={"csv": CSV}).json()
    assert tudo["ok"] is False
    pulando = cliente.post(f"{_base(dados['orgA'])}/{qid}/importar", json={"csv": CSV, "pular_linhas_com_problema": True}).json()
    assert pulando["ok"] and pulando["criadas"] == 2 and len(pulando["linhas_puladas"]) == 2
    c = cliente.post(f"{_base(dados['orgA'])}/{qid}/consulta", json={}).json()
    assert c["linhas"][0]["carimbo"]["origem"] == "importacao"


def test_desfazer_o_que_a_execucao_gravou(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    qid = _criar(cliente, dados)
    auto = Automacao(time_id=dados["timeA"].id, nome="Radar semanal", tipo_gatilho="manual")
    sessao.add(auto)
    sessao.flush()
    ag = Agente(time_id=dados["timeA"].id, nome="Radar", papel="agente")
    ex = Execucao(automacao_id=auto.id)
    sessao.add_all([ag, ex])
    sessao.flush()
    qs.gravar_linhas(sessao, dados["orgA"].id, qid, [{"Data": "2026-09-21", "Pergunta": i} for i in range(1, 4)],
                     autor=Autor(origem="agente", agente_id=ag.id, execucao_id=ex.id))
    v = cliente.get(f"{_base(dados['orgA'])}/{qid}").json()
    assert v["execucoes_recentes"][0]["linhas"] == 3 and v["execucoes_recentes"][0]["automacao"] == "Radar semanal"
    c = cliente.post(f"{_base(dados['orgA'])}/{qid}/consulta", json={}).json()
    assert c["linhas"][0]["carimbo"]["agente_nome"] == "Radar"
    assert c["linhas"][0]["carimbo"]["automacao_nome"] == "Radar semanal"
    previa = cliente.post(f"{_base(dados['orgA'])}/{qid}/linhas/apagar", json={"execucao_id": str(ex.id), "simular": True}).json()
    assert previa["apagadas"] == 3 and previa["simulado"]
    feito = cliente.post(f"{_base(dados['orgA'])}/{qid}/linhas/apagar", json={"execucao_id": str(ex.id)}).json()
    assert feito["apagadas"] == 3
    assert cliente.post(f"{_base(dados['orgA'])}/{qid}/consulta", json={}).json()["total"] == 0


def test_estrutura_e_exportar(cliente, entrar, dados):
    entrar(dados["operador"])
    qid = _criar(cliente, dados)
    cliente.post(f"{_base(dados['orgA'])}/{qid}/linhas", json={"linhas": [{"Data": "2026-09-21", "Tema": "COF", "Pergunta": 1}]})
    sim = cliente.post(f"{_base(dados['orgA'])}/{qid}/estrutura", json={
        "operacoes": [{"acao": "adicionar_coluna", "coluna": {"nome": "Obs", "tipo": "texto_longo"}}], "simular": True,
    }).json()
    assert sim["ok"] and sim["simulado"]
    exp = cliente.post(f"{_base(dados['orgA'])}/{qid}/exportar", json={}).json()
    assert exp["csv"].splitlines() == ["Data,Tema,Pergunta", "2026-09-21,COF,1"]
    sug = cliente.post(f"{_base(dados['orgA'])}/sugerir-colunas", json={"csv": CSV}).json()
    assert [c["tipo"] for c in sug["colunas"]] == ["texto", "texto", "numero"]  # "teste" impede data
