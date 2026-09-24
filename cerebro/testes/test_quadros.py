"""Quadros — Entrega 1 do Cérebro (docs/CEREBRO-PLANO.md §5).

O que se prova aqui é a camada ÚNICA (`quadros.servico`) que agente, tela, IA criadora
e MCP vão usar: tipos e validação, chave, tudo-ou-nada, simular, filtro único, "só a
mais recente de", totais pelo banco, "já existe?", histórico e isolamento entre
organizações. Os casos vêm do uso real que motivou a frente (Radar IA e Painel Lure).
"""

import uuid

import pytest

from modelos import Organizacao, Usuario
from quadros import limites, tipos
from quadros import servico as qs
from quadros.servico import Autor, ErroQuadro

PESSOA = Autor(origem="pessoa")


@pytest.fixture
def org(sessao):
    u = Usuario(nome="dono", email=f"d-{uuid.uuid4().hex[:6]}@x.com", ativo=True)
    sessao.add(u)
    sessao.flush()
    o = Organizacao(nome="Org Q", dono_id=u.id)
    sessao.add(o)
    sessao.flush()
    return o


@pytest.fixture
def outra_org(sessao):
    u = Usuario(nome="outro", email=f"o-{uuid.uuid4().hex[:6]}@x.com", ativo=True)
    sessao.add(u)
    sessao.flush()
    o = Organizacao(nome="Org Outra", dono_id=u.id)
    sessao.add(o)
    sessao.flush()
    return o


def _radar(sessao, org):
    """O quadro do Radar IA: uma linha por (data da rodada, pergunta)."""
    return qs.criar_quadro(
        sessao, org.id,
        nome="Radar – respostas",
        descricao="Uma linha por pergunta de cada rodada semanal do Radar.",
        colunas=[
            {"nome": "Data", "tipo": "data"},
            {"nome": "Tema", "tipo": "opcao", "opcoes": ["COF", "PRO", "PES", "EST", "CAP"]},
            {"nome": "Pergunta", "tipo": "numero"},
            {"nome": "Lure citada", "tipo": "opcao", "opcoes": ["sim", "não", "falhou"]},
            {"nome": "Empresas citadas", "tipo": "texto_longo"},
        ],
        chave=["Data", "Pergunta"],
    )


# ───────────────────────────── tipos ─────────────────────────────


@pytest.mark.parametrize(
    "tipo,entrada,guardado",
    [
        ("numero", "1.234,56", 1234.56),
        ("numero", "1.234.567", 1234567),
        ("numero", "1.5", 1.5),
        ("numero", "1,234.56", 1234.56),
        ("numero", "12,5", 12.5),
        ("numero", 7.0, 7),
        ("dinheiro", "R$ 3,14159", 3.14),
        ("data", "21/09/2026", "2026-09-21"),
        ("data", "2026-09-21T10:00:00Z", "2026-09-21"),
        ("data_hora", "2026-09-21T14:30", "2026-09-21T17:30:00Z"),  # sem fuso = Brasília
        ("data_hora", "2026-09-21T14:30:00Z", "2026-09-21T14:30:00Z"),
        ("sim_nao", "Não", False),
        ("sim_nao", "sim", True),
        ("texto", "  oi  ", "oi"),
    ],
)
def test_normalizar_aceita_formas_generosas_e_guarda_uma_so(tipo, entrada, guardado):
    assert tipos.normalizar({"tipo": tipo}, entrada, tamanho_texto_longo=100) == guardado


def test_opcao_devolve_a_forma_cadastrada():
    col = {"tipo": "opcao", "opcoes": ["Não", "Sim"]}
    assert tipos.normalizar(col, "nao", tamanho_texto_longo=10) == "Não"


@pytest.mark.parametrize(
    "tipo,entrada,trecho",
    [
        ("data", "teste", "não é uma data"),
        ("data", "31/02/2026", "não é uma data que exista"),
        ("numero", "doze", "não é um número"),
        ("numero", True, "sim/não"),
        ("numero", "1.000", "ambíguo"),
        ("dinheiro", "1,000", "ambíguo"),
        ("sim_nao", "talvez", "não é sim ou não"),
        ("texto", "x" * 501, "texto longo"),
    ],
)
def test_normalizar_recusa_com_motivo(tipo, entrada, trecho):
    with pytest.raises(tipos.ValorInvalido) as e:
        tipos.normalizar({"tipo": tipo}, entrada, tamanho_texto_longo=100)
    assert trecho in str(e.value)


def test_id_de_coluna_estavel_e_sem_colisao():
    assert tipos.id_de_coluna("Lure citada?", set()) == "lure_citada"
    assert tipos.id_de_coluna("Lure citada", {"lure_citada"}) == "lure_citada_2"
    assert tipos.id_de_coluna("2026", set()) == "c_2026"


# ───────────────────────────── quadro ─────────────────────────────


def test_criar_quadro_colunas_chave_obrigatoria(sessao, org):
    r = _radar(sessao, org)
    q = r["quadro"]
    assert q["chave"] == ["Data", "Pergunta"]
    obrig = {c["nome"]: c["obrigatoria"] for c in q["colunas"]}
    assert obrig["Data"] and obrig["Pergunta"] and not obrig["Tema"]
    assert {lim["chave"] for lim in q["limites"]} == set(limites.LIMITES)


def test_nome_unico_por_org_sem_diferenciar_maiuscula(sessao, org, outra_org):
    _radar(sessao, org)
    with pytest.raises(ErroQuadro, match="Já existe"):
        qs.criar_quadro(sessao, org.id, nome="radar – RESPOSTAS", colunas=[{"nome": "a", "tipo": "texto"}])
    # Outra organização pode ter o mesmo nome.
    qs.criar_quadro(sessao, outra_org.id, nome="Radar – respostas", colunas=[{"nome": "a", "tipo": "texto"}])


@pytest.mark.parametrize(
    "colunas,chave,trecho",
    [
        ([], None, "pelo menos uma coluna"),
        ([{"nome": "a", "tipo": "cor"}], None, "não existe"),
        ([{"nome": "a", "tipo": "texto"}, {"nome": "A", "tipo": "texto"}], None, "Já existe uma coluna"),
        ([{"nome": "_x", "tipo": "texto"}], None, "reservado"),
        ([{"nome": "estado", "tipo": "opcao"}], None, "lista de opções"),
        ([{"nome": "obs", "tipo": "texto_longo"}], ["obs"], "não pode fazer parte da chave"),
        ([{"nome": "a", "tipo": "texto"}], ["b"], "não existe no quadro"),
    ],
)
def test_criar_quadro_recusa(sessao, org, colunas, chave, trecho):
    with pytest.raises(ErroQuadro) as e:
        qs.criar_quadro(sessao, org.id, nome="Q", colunas=colunas, chave=chave)
    assert trecho in e.value.mensagem


def test_criar_simulado_nao_grava(sessao, org):
    r = qs.criar_quadro(sessao, org.id, nome="Teste", colunas=[{"nome": "a", "tipo": "texto"}], simular=True)
    assert r["simulado"] is True
    assert qs.listar_quadros(sessao, org.id) == []


def test_obter_por_nome_ou_id_e_isolamento(sessao, org, outra_org):
    r = _radar(sessao, org)
    assert qs.obter_quadro(sessao, org.id, "RADAR – respostas").id == uuid.UUID(r["quadro_id"])
    assert qs.obter_quadro(sessao, org.id, r["quadro_id"]).nome == "Radar – respostas"
    # A outra organização não enxerga — nem pelo id.
    with pytest.raises(ErroQuadro, match="Não achei"):
        qs.obter_quadro(sessao, outra_org.id, r["quadro_id"])
    with pytest.raises(ErroQuadro):
        qs.consultar(sessao, outra_org.id, r["quadro_id"])
    with pytest.raises(ErroQuadro):
        qs.gravar_linhas(sessao, outra_org.id, r["quadro_id"], [{"Data": "2026-09-21", "Pergunta": 1}], autor=PESSOA)


# ───────────────────────────── gravar ─────────────────────────────


def _linhas_rodada(data, sim=(1,)):
    return [
        {"Data": data, "Tema": "COF", "Pergunta": p, "Lure citada": "sim" if p in sim else "não"}
        for p in range(1, 5)
    ]


def test_gravar_normaliza_e_carimba(sessao, org):
    _radar(sessao, org)
    r = qs.gravar_linhas(
        sessao, org.id, "Radar – respostas",
        [{"data": "21/09/2026", "tema": "cof", "pergunta": "1", "lure citada": "Sim"}],
        autor=Autor(origem="agente"),
    )
    assert r["criadas"] == 1 and r["simulado"] is False
    c = qs.consultar(sessao, org.id, "Radar – respostas")
    linha = c["linhas"][0]
    assert linha["valores"]["Data"] == "2026-09-21"
    assert linha["valores"]["Tema"] == "COF"
    assert linha["valores"]["Pergunta"] == 1
    assert linha["carimbo"]["origem"] == "agente"


def test_gravacao_tudo_ou_nada_com_motivo_por_linha(sessao, org):
    """O caso "descarte a linha 'teste'" do Painel: a linha ruim recusa a gravação
    inteira, com o motivo apontando a linha e a coluna — nada entra pela metade."""
    _radar(sessao, org)
    linhas = _linhas_rodada("2026-09-21")
    linhas[2]["Data"] = "teste"
    linhas[3]["Tema"] = "RH"
    with pytest.raises(ErroQuadro) as e:
        qs.gravar_linhas(sessao, org.id, "Radar – respostas", linhas, autor=PESSOA)
    assert "Nada foi gravado" in e.value.mensagem
    assert {(d["linha"], d["coluna"]) for d in e.value.detalhes} == {(3, "Data"), (4, "Tema")}
    assert qs.consultar(sessao, org.id, "Radar – respostas")["total"] == 0


def test_coluna_inexistente_lista_as_colunas(sessao, org):
    _radar(sessao, org)
    with pytest.raises(ErroQuadro) as e:
        qs.gravar_linhas(sessao, org.id, "Radar – respostas", [{"Dia": "2026-09-21", "Pergunta": 1}], autor=PESSOA)
    assert "“Data”" in e.value.detalhes[0]["motivo"]


def test_acrescentar_recusa_chave_repetida_e_pela_chave_atualiza(sessao, org):
    _radar(sessao, org)
    qs.gravar_linhas(sessao, org.id, "Radar – respostas", _linhas_rodada("2026-09-21"), autor=PESSOA)
    with pytest.raises(ErroQuadro) as e:
        qs.gravar_linhas(sessao, org.id, "Radar – respostas", [_linhas_rodada("2026-09-21")[0]], autor=PESSOA)
    assert "pela_chave" in e.value.detalhes[0]["motivo"]

    r = qs.gravar_linhas(
        sessao, org.id, "Radar – respostas",
        [
            {"Data": "21/09/2026", "Pergunta": 2, "Lure citada": "sim"},  # muda
            {"Data": "2026-09-21", "Pergunta": 3, "Lure citada": "não"},  # igual
            {"Data": "2026-09-28", "Pergunta": 1, "Tema": "COF", "Lure citada": "não"},  # nova
        ],
        autor=PESSOA, modo="pela_chave",
    )
    assert (r["criadas"], r["atualizadas"], r["sem_mudanca"]) == (1, 1, 1)
    linha = qs.consultar(
        sessao, org.id, "Radar – respostas",
        filtros=[{"coluna": "Data", "valor": "2026-09-21"}, {"coluna": "Pergunta", "valor": 2}],
    )["linhas"][0]
    # Só a coluna informada mudou; o Tema continua o que era.
    assert linha["valores"]["Lure citada"] == "sim" and linha["valores"]["Tema"] == "COF"
    assert linha["carimbo"]["versao"] == 2


def test_chave_repetida_dentro_da_mesma_gravacao(sessao, org):
    _radar(sessao, org)
    l = _linhas_rodada("2026-09-21")[:1] * 2
    with pytest.raises(ErroQuadro) as e:
        qs.gravar_linhas(sessao, org.id, "Radar – respostas", l, autor=PESSOA)
    assert "linha 1" in e.value.detalhes[0]["motivo"]


def test_pela_chave_exige_quadro_com_chave(sessao, org):
    qs.criar_quadro(sessao, org.id, nome="Log", colunas=[{"nome": "msg", "tipo": "texto"}])
    with pytest.raises(ErroQuadro, match="não tem chave"):
        qs.gravar_linhas(sessao, org.id, "Log", [{"msg": "oi"}], autor=PESSOA, modo="pela_chave")


def test_obrigatoria_faltando_na_criacao(sessao, org):
    qs.criar_quadro(
        sessao, org.id, nome="Contas",
        colunas=[{"nome": "Fornecedor", "tipo": "texto", "obrigatoria": True}, {"nome": "Valor", "tipo": "dinheiro"}],
    )
    with pytest.raises(ErroQuadro) as e:
        qs.gravar_linhas(sessao, org.id, "Contas", [{"Valor": "10"}], autor=PESSOA)
    assert "Fornecedor" in e.value.detalhes[0]["motivo"]


def test_simular_gravacao_nao_grava_mas_conta(sessao, org):
    _radar(sessao, org)
    r = qs.gravar_linhas(sessao, org.id, "Radar – respostas", _linhas_rodada("2026-09-21"), autor=PESSOA, simular=True)
    assert r["simulado"] is True and r["criadas"] == 4
    assert qs.consultar(sessao, org.id, "Radar – respostas")["total"] == 0


def test_limite_de_linhas_por_gravacao_e_visivel_e_ajustavel(sessao, org):
    qs.criar_quadro(
        sessao, org.id, nome="Pequeno", colunas=[{"nome": "n", "tipo": "numero"}],
        limites={"linhas_por_gravacao": 2},
    )
    with pytest.raises(ErroQuadro) as e:
        qs.gravar_linhas(sessao, org.id, "Pequeno", [{"n": i} for i in range(3)], autor=PESSOA)
    assert "até 2" in e.value.mensagem and limites.ONDE_MUDAR in e.value.mensagem
    qs.alterar_quadro(sessao, org.id, "Pequeno", [{"acao": "ajustar_limite", "limite": "linhas_por_gravacao", "valor": None}])
    assert qs.gravar_linhas(sessao, org.id, "Pequeno", [{"n": i} for i in range(3)], autor=PESSOA)["criadas"] == 3
    with pytest.raises(ErroQuadro, match="aceita de 1 a"):
        qs.alterar_quadro(sessao, org.id, "Pequeno", [{"acao": "ajustar_limite", "limite": "linhas_por_gravacao", "valor": 10**9}])


# ──────────────────────── consultar / filtros ────────────────────────


def _duas_rodadas(sessao, org):
    _radar(sessao, org)
    qs.gravar_linhas(sessao, org.id, "Radar – respostas", _linhas_rodada("2026-09-14", sim=()), autor=PESSOA)
    qs.gravar_linhas(sessao, org.id, "Radar – respostas", _linhas_rodada("2026-09-21", sim=(1, 3)), autor=PESSOA)


def test_filtros_operadores_e_normalizacao_do_valor(sessao, org):
    _duas_rodadas(sessao, org)

    def total(filtros):
        return qs.consultar(sessao, org.id, "Radar – respostas", filtros=filtros)["total"]

    assert total([{"coluna": "Data", "operador": ">=", "valor": "15/09/2026"}]) == 4
    assert total([{"coluna": "Lure citada", "valor": "SIM"}]) == 2
    assert total([{"coluna": "Lure citada", "operador": "≠", "valor": "sim"}]) == 6
    assert total([{"coluna": "Pergunta", "operador": "em", "valor": [1, "2"]}]) == 4
    assert total([{"coluna": "Empresas citadas", "operador": "vazio"}]) == 8
    assert total([{"coluna": "_origem", "valor": "pessoa"}]) == 8


def test_filtro_invalido_explica(sessao, org):
    _radar(sessao, org)
    with pytest.raises(ErroQuadro, match="não tem a coluna"):
        qs.consultar(sessao, org.id, "Radar – respostas", filtros=[{"coluna": "Semana", "valor": 1}])
    with pytest.raises(ErroQuadro, match="Operador “parecido” não existe"):
        qs.consultar(sessao, org.id, "Radar – respostas", filtros=[{"coluna": "Data", "operador": "parecido", "valor": 1}])
    with pytest.raises(ErroQuadro, match="não é uma data"):
        qs.consultar(sessao, org.id, "Radar – respostas", filtros=[{"coluna": "Data", "valor": "teste"}])
    with pytest.raises(ErroQuadro, match="só vale para colunas de texto"):
        qs.consultar(sessao, org.id, "Radar – respostas", filtros=[{"coluna": "Pergunta", "operador": "contem", "valor": 1}])


def test_so_a_mais_recente_de(sessao, org):
    """"As lacunas da rodada mais recente" — o padrão que o Briefing precisa."""
    _duas_rodadas(sessao, org)
    r = qs.consultar(
        sessao, org.id, "Radar – respostas",
        filtros=[{"coluna": "Lure citada", "valor": "não"}],
        so_o_mais_recente_de="Data",
    )
    assert r["total"] == 2
    assert {ln["valores"]["Data"] for ln in r["linhas"]} == {"2026-09-21"}


def test_so_a_mais_recente_de_quadro_vazio(sessao, org):
    _radar(sessao, org)
    assert qs.consultar(sessao, org.id, "Radar – respostas", so_o_mais_recente_de="Data")["total"] == 0


def test_ordem_numerica_limite_e_proximo(sessao, org):
    _duas_rodadas(sessao, org)
    r = qs.consultar(
        sessao, org.id, "Radar – respostas",
        ordem=["-Data", "Pergunta"], limite=3, colunas=["Data", "Pergunta"],
    )
    assert r["total"] == 8 and r["devolvidas"] == 3 and r["proximo"] == 3
    assert [ln["valores"]["Pergunta"] for ln in r["linhas"]] == [1, 2, 3]
    assert set(r["linhas"][0]["valores"]) == {"Data", "Pergunta"}
    r2 = qs.consultar(sessao, org.id, "Radar – respostas", ordem=["-Data", "Pergunta"], limite=3, deslocamento=6)
    assert r2["devolvidas"] == 2 and r2["proximo"] is None


def test_consulta_acima_do_teto_avisa_em_vez_de_cortar_calado(sessao, org):
    _radar(sessao, org)
    r = qs.consultar(sessao, org.id, "Radar – respostas", limite=10**6)
    assert "aviso" in r


# ───────────────────────────── totais ─────────────────────────────


def test_totais_pelo_banco_agrupados(sessao, org):
    _duas_rodadas(sessao, org)
    r = qs.totais(
        sessao, org.id, "Radar – respostas",
        agrupar_por="Data",
        filtros=[{"coluna": "Lure citada", "valor": "sim"}],
    )
    assert r["resultados"] == [{"grupo": {"Data": "2026-09-21"}, "valores": {"quantidade": 2}}]


def test_totais_soma_media_e_recusa_tipo(sessao, org):
    qs.criar_quadro(
        sessao, org.id, nome="Contas",
        colunas=[{"nome": "Fornecedor", "tipo": "texto"}, {"nome": "Valor", "tipo": "dinheiro"}],
    )
    qs.gravar_linhas(
        sessao, org.id, "Contas",
        [{"Fornecedor": "A", "Valor": "10,50"}, {"Fornecedor": "A", "Valor": "1.000,00"}, {"Fornecedor": "B", "Valor": 5}],
        autor=PESSOA,
    )
    r = qs.totais(
        sessao, org.id, "Contas",
        metricas=[{"funcao": "soma", "coluna": "Valor"}, {"funcao": "max", "coluna": "Valor"}, {"funcao": "contar"}],
    )
    assert r["resultados"][0]["valores"] == {"soma de Valor": 1015.5, "máximo de Valor": 1000, "quantidade": 3}
    por = qs.totais(sessao, org.id, "Contas", agrupar_por=["Fornecedor"], metricas=[{"funcao": "soma", "coluna": "Valor"}])
    assert [g["valores"]["soma de Valor"] for g in por["resultados"]] == [1010.5, 5]
    with pytest.raises(ErroQuadro, match="Só dá para somar"):
        qs.totais(sessao, org.id, "Contas", metricas=[{"funcao": "soma", "coluna": "Fornecedor"}])


# ───────────────────────────── já existe ─────────────────────────────


def test_ja_existe_substitui_ler_tudo(sessao, org):
    """O Coletor do Painel lia a aba inteira para achar as semanas que faltam."""
    qs.criar_quadro(sessao, org.id, nome="Painel – semanas", colunas=[{"nome": "Semana", "tipo": "data"}], chave=["Semana"])
    qs.gravar_linhas(sessao, org.id, "Painel – semanas", [{"Semana": "2026-09-07"}, {"Semana": "2026-09-14"}], autor=PESSOA)
    r = qs.ja_existe(sessao, org.id, "Painel – semanas", coluna="Semana", valores=["07/09/2026", "2026-09-14", "2026-09-21"])
    assert r["existem"] == ["07/09/2026", "2026-09-14"]
    assert r["faltam"] == ["2026-09-21"]


# ───────────────────────── editar / apagar / histórico ─────────────────────────


def test_editar_por_filtro_exige_criterio_e_registra_historico(sessao, org):
    _duas_rodadas(sessao, org)
    with pytest.raises(ErroQuadro, match="Diga quais linhas"):
        qs.editar_linhas(sessao, org.id, "Radar – respostas", campos={"Tema": "PRO"}, autor=PESSOA)
    sim = qs.editar_linhas(
        sessao, org.id, "Radar – respostas", campos={"Tema": "PRO"},
        filtros=[{"coluna": "Data", "valor": "2026-09-14"}], autor=PESSOA, simular=True,
    )
    assert sim["mudadas"] == 4 and sim["simulado"]
    assert qs.totais(sessao, org.id, "Radar – respostas", filtros=[{"coluna": "Tema", "valor": "PRO"}])["resultados"][0]["valores"]["quantidade"] == 0
    qs.editar_linhas(
        sessao, org.id, "Radar – respostas", campos={"Tema": "PRO"},
        filtros=[{"coluna": "Data", "valor": "2026-09-14"}, {"coluna": "Pergunta", "valor": 1}],
        autor=Autor(origem="mcp"),
    )
    linha = qs.consultar(sessao, org.id, "Radar – respostas", filtros=[{"coluna": "Tema", "valor": "PRO"}])["linhas"][0]
    h = qs.historico_linha(sessao, org.id, "Radar – respostas", linha["id"])["alteracoes"]
    assert [a["acao"] for a in h] == ["criou", "mudou"]
    assert h[1]["antes"]["Tema"] == "COF" and h[1]["depois"]["Tema"] == "PRO"
    assert h[1]["origem"] == "mcp"


def test_editar_nao_esvazia_obrigatoria(sessao, org):
    _duas_rodadas(sessao, org)
    with pytest.raises(ErroQuadro, match="obrigatórias"):
        qs.editar_linhas(
            sessao, org.id, "Radar – respostas", campos={"Pergunta": ""},
            filtros=[{"coluna": "Pergunta", "valor": 1}], autor=PESSOA,
        )


def test_apagar_o_que_uma_execucao_gravou_e_historico_sobrevive(sessao, org):
    """Desfazer uma rodada de teste: apagar tudo o que UMA execução gravou."""
    from modelos import Automacao, Execucao, Time

    t = Time(organizacao_id=org.id, nome="T")
    sessao.add(t)
    sessao.flush()
    a = Automacao(time_id=t.id, nome="A", tipo_gatilho="manual")
    sessao.add(a)
    sessao.flush()
    ex = Execucao(automacao_id=a.id)
    sessao.add(ex)
    sessao.flush()

    _radar(sessao, org)
    qs.gravar_linhas(sessao, org.id, "Radar – respostas", _linhas_rodada("2026-09-14"), autor=PESSOA)
    qs.gravar_linhas(
        sessao, org.id, "Radar – respostas", _linhas_rodada("2026-09-21"),
        autor=Autor(origem="agente", execucao_id=ex.id),
    )
    lid = qs.consultar(sessao, org.id, "Radar – respostas", execucao_id=ex.id)["linhas"][0]["id"]
    with pytest.raises(ErroQuadro, match="Diga quais linhas apagar"):
        qs.apagar_linhas(sessao, org.id, "Radar – respostas", autor=PESSOA)
    r = qs.apagar_linhas(sessao, org.id, "Radar – respostas", execucao_id=str(ex.id), autor=PESSOA)
    assert r["apagadas"] == 4
    assert qs.consultar(sessao, org.id, "Radar – respostas")["total"] == 4
    h = qs.historico_linha(sessao, org.id, "Radar – respostas", lid)["alteracoes"]
    assert [x["acao"] for x in h] == ["criou", "apagou"]


# ───────────────────────── alterar a estrutura ─────────────────────────


def test_trocar_tipo_converte_ou_recusa_com_lista(sessao, org):
    qs.criar_quadro(sessao, org.id, nome="Q", colunas=[{"nome": "Quando", "tipo": "texto"}])
    qs.gravar_linhas(sessao, org.id, "Q", [{"Quando": "21/09/2026"}, {"Quando": "teste"}], autor=PESSOA)
    with pytest.raises(ErroQuadro) as e:
        qs.alterar_quadro(sessao, org.id, "Q", [{"acao": "trocar_tipo", "coluna": "Quando", "tipo": "data"}])
    assert e.value.detalhes[0]["valor"] == "teste"
    # Prévia: simular diz o que aconteceria, sem mudar nada.
    sim = qs.alterar_quadro(
        sessao, org.id, "Q",
        [{"acao": "trocar_tipo", "coluna": "Quando", "tipo": "data", "esvaziar_invalidos": True}],
        simular=True,
    )
    assert sim["simulado"] and sim["linhas_afetadas"] == 2
    assert qs.descrever_quadro(qs.obter_quadro(sessao, org.id, "Q"))["colunas"][0]["tipo"] == "texto"
    qs.alterar_quadro(
        sessao, org.id, "Q",
        [{"acao": "trocar_tipo", "coluna": "Quando", "tipo": "data", "esvaziar_invalidos": True}],
    )
    vals = sorted(
        (ln["valores"]["Quando"] or "") for ln in qs.consultar(sessao, org.id, "Q")["linhas"]
    )
    assert vals == ["", "2026-09-21"]


def test_renomear_coluna_nao_perde_dados(sessao, org):
    _duas_rodadas(sessao, org)
    qs.alterar_quadro(sessao, org.id, "Radar – respostas", [{"acao": "renomear_coluna", "coluna": "Lure citada", "nome": "Citou a Lure"}])
    r = qs.consultar(sessao, org.id, "Radar – respostas", filtros=[{"coluna": "Citou a Lure", "valor": "sim"}])
    assert r["total"] == 2


def test_mudar_chave_recusa_duplicata_e_remover_coluna_da_chave(sessao, org):
    _duas_rodadas(sessao, org)
    with pytest.raises(ErroQuadro, match="mesma identificação"):
        qs.alterar_quadro(sessao, org.id, "Radar – respostas", [{"acao": "mudar_chave", "colunas": ["Pergunta"]}])
    with pytest.raises(ErroQuadro, match="faz parte da chave"):
        qs.alterar_quadro(sessao, org.id, "Radar – respostas", [{"acao": "remover_coluna", "coluna": "Data"}])


def test_adicionar_obrigatoria_em_quadro_com_linhas_recusa(sessao, org):
    _duas_rodadas(sessao, org)
    with pytest.raises(ErroQuadro, match="não pode nascer obrigatória"):
        qs.alterar_quadro(
            sessao, org.id, "Radar – respostas",
            [{"acao": "adicionar_coluna", "coluna": {"nome": "Fonte", "tipo": "texto", "obrigatoria": True}}],
        )


def test_alteracao_e_tudo_ou_nada(sessao, org):
    _radar(sessao, org)
    with pytest.raises(ErroQuadro):
        qs.alterar_quadro(
            sessao, org.id, "Radar – respostas",
            [{"acao": "renomear", "nome": "Radar"}, {"acao": "inventada"}],
        )
    assert qs.obter_quadro(sessao, org.id, "Radar – respostas")


def test_excluir_quadro(sessao, org):
    _duas_rodadas(sessao, org)
    sim = qs.excluir_quadro(sessao, org.id, "Radar – respostas", simular=True)
    assert sim["linhas_apagadas"] == 8 and qs.listar_quadros(sessao, org.id)
    qs.excluir_quadro(sessao, org.id, "Radar – respostas")
    assert qs.listar_quadros(sessao, org.id) == []
