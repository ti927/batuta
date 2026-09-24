"""Links de leitura de um quadro (acesso de fora, para painéis): criar/trocar/revogar é
de admin; o link inteiro só aparece uma vez; a leitura pública devolve CSV e JSON, com
filtros, datas relativas e totais; revogado/expirado/limite são recusados com frase
humana; toda leitura conta no link; e um link nunca lê outro quadro."""

from datetime import datetime, timedelta, timezone

from modelos import QuadroLink
from quadros import links
from quadros import servico as qs
from quadros.servico import Autor


def _base(o):
    return f"/organizacoes/{o.id}/quadros"


def _quadro(cliente, sessao, dados):
    r = cliente.post(_base(dados["orgA"]), json={
        "nome": "Painel – semanas",
        "colunas": [{"nome": "Semana", "tipo": "data"}, {"nome": "Tema", "tipo": "texto"},
                    {"nome": "Cliques", "tipo": "numero"}, {"nome": "Custo", "tipo": "dinheiro"}],
        "chave": ["Semana", "Tema"],
    }).json()
    qs.gravar_linhas(sessao, dados["orgA"].id, r["quadro_id"], [
        {"Semana": "2026-09-07", "Tema": "COF", "Cliques": 10, "Custo": "12,50"},
        {"Semana": "2026-09-14", "Tema": "COF", "Cliques": 30, "Custo": 5},
        {"Semana": "2026-09-14", "Tema": "PRO", "Cliques": 7, "Custo": 1},
    ], autor=Autor(origem="agente"))
    return r["quadro_id"]


def _criar_link(cliente, dados, qid, **extra):
    r = cliente.post(f"{_base(dados['orgA'])}/{qid}/links", json={"nome": "Looker", **extra}).json()
    assert r["ok"], r
    return r


def test_so_admin_cria_e_o_link_aparece_uma_vez(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    qid = _quadro(cliente, sessao, dados)
    assert cliente.post(f"{_base(dados['orgA'])}/{qid}/links", json={"nome": "x"}).status_code in (403, 404)
    entrar(dados["admin"])
    r = _criar_link(cliente, dados, qid)
    assert r["caminho"].startswith("/publico/quadros/bq_")
    token = r["caminho"].rsplit("/", 1)[1]
    guardado = sessao.query(QuadroLink).one()
    assert guardado.token_hash != token and token not in guardado.token_hash  # só o hash
    lista = cliente.get(f"{_base(dados['orgA'])}/{qid}/links").json()
    assert lista[0]["final"] == token[-4:] and "caminho" not in lista[0]
    entrar(dados["observador"])
    assert cliente.get(f"{_base(dados['orgA'])}/{qid}/links").json()[0]["nome"] == "Looker"


def test_leitura_publica_csv_json_filtros_e_contagem(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    qid = _quadro(cliente, sessao, dados)
    caminho = _criar_link(cliente, dados, qid)["caminho"]
    main_overrides = dict(cliente.app.dependency_overrides)
    # Sem login: a leitura pública não depende de usuário.
    from auth import usuario_atual
    cliente.app.dependency_overrides.pop(usuario_atual, None)
    csv = cliente.get(caminho, params={"ordem": ["Semana", "Tema"]})
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert csv.headers["access-control-allow-origin"] == "*"
    assert csv.text.splitlines() == [
        "Semana,Tema,Cliques,Custo",
        "2026-09-07,COF,10,12.5",
        "2026-09-14,COF,30,5",
        "2026-09-14,PRO,7,1",
    ]
    br = cliente.get(caminho, params={"filtro": "Tema|eq|COF", "decimal": "virgula", "ordem": "Semana"})
    assert br.text.splitlines()[1] == '2026-09-07,COF,10,"12,5"'
    js = cliente.get(caminho, params={"formato": "json", "recente": "Semana", "colunas": "Tema,Cliques"}).json()
    assert js["total"] == 2 and {ln["Tema"] for ln in js["linhas"]} == {"COF", "PRO"}
    rel = cliente.get(caminho, params={"formato": "json", "filtro": "Semana|gte|hoje-3650"}).json()
    assert rel["total"] == 3
    tot = cliente.get(caminho + "/totais", params={"agrupar": "Tema", "metrica": ["soma|Cliques", "contar"]})
    assert tot.text.splitlines() == ["Tema,soma de Cliques,quantidade", "COF,40,2", "PRO,7,1"]
    cliente.app.dependency_overrides.update(main_overrides)
    assert sessao.query(QuadroLink).one().usos == 5


def test_recusas_com_frase_humana(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    qid = _quadro(cliente, sessao, dados)
    r = _criar_link(cliente, dados, qid)
    caminho, lid = r["caminho"], r["link"]["id"]
    assert cliente.get("/publico/quadros/bq_nao_existe").status_code == 404
    ruim = cliente.get(caminho, params={"filtro": "Semana|eq|teste", "formato": "json"})
    assert ruim.status_code == 422 and "não é uma data" in ruim.json()["erro"]
    # Trocar: o antigo para na hora, o novo funciona.
    novo = cliente.post(f"{_base(dados['orgA'])}/{qid}/links/{lid}/trocar").json()["caminho"]
    assert cliente.get(caminho).status_code == 404 and cliente.get(novo).status_code == 200
    # Revogar: 410 com o que fazer.
    cliente.post(f"{_base(dados['orgA'])}/{qid}/links/{lid}/revogar")
    rev = cliente.get(novo)
    assert rev.status_code == 410 and "revogado" in rev.text
    # Expirado.
    exp = _criar_link(cliente, dados, qid, expira_em=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    link = sessao.get(QuadroLink, __import__("uuid").UUID(exp["link"]["id"]))
    link.expira_em = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.flush()
    assert cliente.get(exp["caminho"]).status_code == 410


def test_limite_por_minuto_visivel_e_ajustavel(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    qid = _quadro(cliente, sessao, dados)
    r = _criar_link(cliente, dados, qid, limite_por_minuto=2)
    assert r["link"]["limite_por_minuto"] == 2
    assert cliente.get(r["caminho"]).status_code == 200
    assert cliente.get(r["caminho"]).status_code == 200
    passou = cliente.get(r["caminho"])
    assert passou.status_code == 429 and "limite deste link é 2" in passou.text
    ruim = cliente.post(f"{_base(dados['orgA'])}/{qid}/links", json={"nome": "x", "limite_por_minuto": 10**6}).json()
    assert ruim["ok"] is False and "de 1 a" in ruim["erro"]


def test_link_so_le_o_proprio_quadro(sessao, dados):
    org = dados["orgA"].id
    qs.criar_quadro(sessao, org, nome="A", colunas=[{"nome": "x", "tipo": "texto"}])
    qs.criar_quadro(sessao, org, nome="B", colunas=[{"nome": "x", "tipo": "texto"}])
    qs.gravar_linhas(sessao, org, "B", [{"x": "segredo de B"}], autor=Autor(origem="pessoa"))
    link, token = links.criar(sessao, org, "A", nome="só A")
    aberto = links.abrir(sessao, token)
    assert aberto.quadro_id == qs.obter_quadro(sessao, org, "A").id


def test_mcp_lista_sem_ver_o_link_e_revoga_com_confirmacao(sessao, dados, monkeypatch):
    import json

    import mcp_ferramentas as leitura
    import mcp_ferramentas_escrita as escrita
    import mcp_ferramentas_quadros as mq

    class _Fake:
        def __init__(self, s):
            self._s = s

        def __getattr__(self, n):
            return getattr(self._s, n)

        def commit(self):
            self._s.flush()

        def close(self):
            pass

    monkeypatch.setattr(escrita, "CriadorDeSessao", lambda: _Fake(sessao))
    monkeypatch.setattr(leitura, "CriadorDeSessao", lambda: _Fake(sessao))
    org = dados["orgA"].id
    qs.criar_quadro(sessao, org, nome="A", colunas=[{"nome": "x", "tipo": "texto"}])
    link, token = links.criar(sessao, org, "A", nome="Looker")
    lista = mq.listar_links_quadro(str(dados["observador"].id), str(org), "A")
    assert "Looker" in lista and token not in lista
    previa = json.loads(mq.revogar_link_quadro(str(dados["admin"].id), str(org), "A", str(link.id), False))
    assert previa["simulado"] and sessao.get(QuadroLink, link.id).revogado_em is None
    feito = json.loads(mq.revogar_link_quadro(str(dados["admin"].id), str(org), "A", str(link.id), True))
    assert feito["link"]["estado"] == "revogado"


def test_data_relativa():
    assert links.data_relativa("2026-09-01") == "2026-09-01"
    assert len(links.data_relativa("hoje-90")) == 10
    assert links.data_relativa("hoje") <= links.data_relativa("hoje+1")
