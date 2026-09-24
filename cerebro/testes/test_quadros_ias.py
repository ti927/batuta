"""Quadros — Entrega 3 do Cérebro: as IAs operam (docs/CEREBRO-PLANO.md §7 e §8).

Prova-se: a IA criadora cria/lê/altera/importa quadros na organização da conversa; o
MCP opera um quadro de ponta a ponta com `simular`, papéis e isolamento; apagar/excluir
só simulam sem `confirmar`; o instrumento guarda o ID do quadro (renomear não quebra) e
é recusado na hora se o quadro não existe; o CSV vira quadro; e o diagnóstico da
execução mostra o que ela gravou de fato.
"""

import json

import pytest

import mcp_ferramentas_quadros as mq
from criacao import servicos
from criacao.ferramentas import ContextoCriacao, ferramenta_por_nome
from criacao.servicos import ConflitoDominio
from modelos import Automacao, ConversaCriacao, Execucao
from quadros import importacao
from quadros import servico as qs
from quadros.servico import Autor

CSV_RADAR = (
    "Data;Tema;Pergunta;Lure citada\n"
    "21/09/2026;COF;1;sim\n"
    "21/09/2026;COF;2;não\n"
    "14/09/2026;COF;1;não\n"
)


class _SessaoFake:
    """A sessão do teste com `close()` inerte e `commit` virando `flush` (mesmo molde de
    test_mcp_escrita_real)."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def commit(self):
        self._s.flush()

    def close(self):
        pass


@pytest.fixture
def mcp(sessao, monkeypatch):
    import mcp_ferramentas as leitura
    import mcp_ferramentas_escrita as escrita

    monkeypatch.setattr(escrita, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(leitura, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    return sessao


def _j(texto):
    return json.loads(texto)


# ───────────────────────────── importação ─────────────────────────────


def test_sugere_colunas_pelos_valores():
    s = importacao.sugerir_colunas(CSV_RADAR)
    assert s["linhas_no_csv"] == 3
    assert {c["nome"]: c["tipo"] for c in s["colunas"]} == {
        "Data": "data", "Tema": "texto", "Pergunta": "numero", "Lure citada": "sim_nao",
    }


def test_importar_tudo_ou_nada_com_numeracao_do_arquivo(sessao, dados):
    org = dados["orgA"].id
    qs.criar_quadro(
        sessao, org, nome="Radar",
        colunas=[{"nome": "Data", "tipo": "data"}, {"nome": "Tema", "tipo": "texto"},
                 {"nome": "Pergunta", "tipo": "numero"}, {"nome": "Lure citada", "tipo": "texto"}],
    )
    ruim = CSV_RADAR + "teste;COF;3;sim\n"
    with pytest.raises(qs.ErroQuadro) as e:
        importacao.importar_csv(sessao, org, "Radar", ruim, autor=Autor(origem="importacao"))
    assert e.value.detalhes[0]["linha"] == 5  # cabeçalho = linha 1
    assert qs.contar_linhas(sessao, qs.obter_quadro(sessao, org, "Radar").id) == 0
    r = importacao.importar_csv(sessao, org, "Radar", CSV_RADAR, autor=Autor(origem="importacao"))
    assert r["criadas"] == 3


def test_importar_coluna_a_mais_recusa_ou_ignora(sessao, dados):
    org = dados["orgA"].id
    qs.criar_quadro(sessao, org, nome="Só data", colunas=[{"nome": "Data", "tipo": "data"}])
    with pytest.raises(qs.ErroQuadro, match="não existem no quadro"):
        importacao.importar_csv(sessao, org, "Só data", CSV_RADAR, autor=Autor(origem="importacao"))
    r = importacao.importar_csv(
        sessao, org, "Só data", CSV_RADAR, autor=Autor(origem="importacao"),
        ignorar_colunas_extras=True,
    )
    assert r["criadas"] == 3 and set(r["colunas_ignoradas"]) == {"Tema", "Pergunta", "Lure citada"}


# ───────────────────── o instrumento guarda o ID e confere ─────────────────────


def test_instrumento_guarda_o_id_e_sobrevive_a_renomear(sessao, dados):
    org, time = dados["orgA"].id, dados["timeA"]
    qs.criar_quadro(sessao, org, nome="Briefing", colunas=[{"nome": "Tema", "tipo": "texto"}])
    inst, _ = servicos.configurar_instrumento(
        sessao, time, nome="Ler briefing", tipo="quadro",
        configuracao={"quadro": "briefing", "acesso": "ler"},
    )
    qid = str(qs.obter_quadro(sessao, org, "Briefing").id)
    assert inst.configuracao["quadro"] == qid
    qs.alterar_quadro(sessao, org, "Briefing", [{"acao": "renomear", "nome": "Briefing por tema"}])
    usos = qs.quem_usa(sessao, org, "Briefing por tema")
    assert [u["instrumento"] for u in usos] == ["Ler briefing"]


def test_instrumento_recusa_quadro_inexistente_ou_de_outra_org(sessao, dados):
    qs.criar_quadro(sessao, dados["orgB"].id, nome="Da outra", colunas=[{"nome": "a", "tipo": "texto"}])
    for ref in ("Não existe", "Da outra"):
        with pytest.raises(ConflitoDominio, match="Não achei o quadro"):
            servicos.configurar_instrumento(
                sessao, dados["timeA"], nome="x", tipo="quadro", configuracao={"quadro": ref},
            )


def test_rota_de_instrumento_tambem_confere(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    r = cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={"nome": "q", "tipo": "quadro", "configuracao": {"quadro": "Nenhum"}},
    )
    assert r.status_code == 422 and "Não achei o quadro" in r.text


# ───────────────────────────── IA criadora ─────────────────────────────


@pytest.fixture
def criadora(sessao, dados):
    conversa = ConversaCriacao(organizacao_id=dados["orgA"].id, time_id=dados["timeA"].id)
    sessao.add(conversa)
    sessao.flush()
    return ferramenta_por_nome(ContextoCriacao(sessao=sessao, conversa=conversa, usuario=dados["operador"]))


def test_criadora_monta_quadro_e_da_o_instrumento(sessao, dados, criadora):
    r = _j(criadora["criar_quadro"].invoke({
        "nome": "Briefing por tema",
        "colunas": [{"nome": "Tema", "tipo": "opcao", "opcoes": ["COF", "PRO"]},
                    {"nome": "Briefing", "tipo": "texto_longo"}],
        "chave": ["Tema"], "descricao": "Uma linha por tema.",
    }))
    assert r["ok"] and r["quadro"]["chave"] == ["Tema"]
    inst = _j(criadora["configurar_instrumento"].invoke({
        "nome": "Briefing (leitura)", "tipo": "quadro",
        "configuracao": {"quadro": "Briefing por tema", "acesso": "ler"},
    }))
    assert inst["ok"]
    lista = _j(criadora["listar_quadros"].invoke({}))
    assert lista["quadros"][0]["usado_por"][0]["acesso"] == "ler"
    ver = _j(criadora["ver_quadro"].invoke({"quadro": "briefing por tema"}))
    assert ver["quadro"]["total_linhas"] == 0


def test_criadora_alterar_simular_e_recusa_explicada(criadora):
    criadora["criar_quadro"].invoke({"nome": "Q", "colunas": [{"nome": "a", "tipo": "texto"}]})
    sim = _j(criadora["alterar_quadro"].invoke({
        "quadro": "Q", "operacoes": [{"acao": "adicionar_coluna", "coluna": {"nome": "b", "tipo": "numero"}}],
        "simular": True,
    }))
    assert sim["ok"] and sim["simulado"]
    ruim = _j(criadora["alterar_quadro"].invoke({"quadro": "Q", "operacoes": [{"acao": "voar"}]}))
    assert ruim["ok"] is False and "Não conheço a ação" in ruim["erro"]


def test_criadora_importa_csv_criando_quadro_em_dois_tempos(sessao, dados, criadora):
    previa = _j(criadora["importar_csv_quadro"].invoke({"csv": CSV_RADAR, "criar_com_nome": "Radar"}))
    assert previa["simulado"] and len(previa["colunas_sugeridas"]) == 4
    assert qs.listar_quadros(sessao, dados["orgA"].id) == []
    feito = _j(criadora["importar_csv_quadro"].invoke({
        "csv": CSV_RADAR, "criar_com_nome": "Radar", "chave": ["Data", "Pergunta", "Tema"],
        "simular": False,
    }))
    assert feito["ok"] and feito["criadas"] == 3
    c = qs.consultar(sessao, dados["orgA"].id, "Radar")
    assert c["linhas"][0]["carimbo"]["origem"] == "ia_criadora"


# ───────────────────────────── MCP ─────────────────────────────


def _sub(dados, papel):
    return str(dados[papel].id)


def test_mcp_ponta_a_ponta(mcp, dados):
    org = str(dados["orgA"].id)
    op = _sub(dados, "operador")
    criado = _j(mq.criar_quadro(
        op, org, "Contas a pagar",
        [{"nome": "NF", "tipo": "texto"}, {"nome": "Valor", "tipo": "dinheiro"},
         {"nome": "Estado", "tipo": "opcao", "opcoes": ["pendente", "pago"]}],
        ["NF"], "Uma linha por nota fiscal.", None, False,
    ))
    assert criado["ok"]
    sim = _j(mq.gravar_linhas(op, org, "Contas a pagar", [{"NF": "1", "Valor": "10,50", "Estado": "pendente"}], "acrescentar", True))
    assert sim["simulado"] and sim["criadas"] == 1
    feito = _j(mq.gravar_linhas(op, org, "Contas a pagar", [
        {"NF": "1", "Valor": "10,50", "Estado": "pendente"},
        {"NF": "2", "Valor": 90, "Estado": "pendente"},
    ], "acrescentar", False))
    assert feito["criadas"] == 2
    ed = _j(mq.editar_linhas(op, org, "Contas a pagar", {"Estado": "pago"}, None, [{"coluna": "NF", "valor": "2"}], False))
    assert ed["mudadas"] == 1
    tot = _j(mq.totais_quadro(
        _sub(dados, "observador"), org, "Contas a pagar",
        [{"funcao": "soma", "coluna": "Valor"}], ["Estado"], None, None,
    ))
    assert {g["grupo"]["Estado"]: g["valores"]["soma de Valor"] for g in tot["resultados"]} == {"pago": 90, "pendente": 10.5}
    c = _j(mq.consultar_quadro(_sub(dados, "observador"), org, "Contas a pagar", None, ["NF"], None, 1, 0, None, None))
    assert c["total"] == 2 and c["proximo"] == 1 and c["linhas"][0]["carimbo"]["origem"] == "mcp"
    h = _j(mq.historico_linha(op, org, "Contas a pagar", c["linhas"][0]["id"]))
    assert [a["acao"] for a in h["alteracoes"]] == ["criou"]
    exp = _j(mq.exportar_quadro(op, org, "Contas a pagar", None))
    assert exp["csv"].splitlines()[0] == "NF,Valor,Estado" and exp["exportadas"] == 2


def test_mcp_apagar_e_excluir_so_simulam_sem_confirmar(mcp, dados):
    org = str(dados["orgA"].id)
    op, adm = _sub(dados, "operador"), _sub(dados, "admin")
    mq.criar_quadro(op, org, "Q", [{"nome": "a", "tipo": "texto"}], None, None, None, False)
    mq.gravar_linhas(op, org, "Q", [{"a": "x"}, {"a": "y"}], "acrescentar", False)
    previa = _j(mq.apagar_linhas(op, org, "Q", None, [{"coluna": "a", "valor": "x"}], None, False))
    assert previa["simulado"] and previa["apagadas"] == 1 and "PRÉVIA" in previa["aviso"]
    assert qs.contar_linhas(mcp, qs.obter_quadro(mcp, dados["orgA"].id, "Q").id) == 2
    _j(mq.apagar_linhas(op, org, "Q", None, [{"coluna": "a", "valor": "x"}], None, True))
    assert qs.contar_linhas(mcp, qs.obter_quadro(mcp, dados["orgA"].id, "Q").id) == 1
    ex_previa = _j(mq.excluir_quadro(adm, org, "Q", False))
    assert ex_previa["simulado"] and qs.listar_quadros(mcp, dados["orgA"].id)
    _j(mq.excluir_quadro(adm, org, "Q", True))
    assert qs.listar_quadros(mcp, dados["orgA"].id) == []


def test_mcp_papeis_e_isolamento(mcp, dados):
    """As negações desfazem a transação da ferramenta — no teste isso desfaria o que foi
    criado antes (tudo corre numa transação só), então as leituras vêm primeiro e as
    negações são conferidas pela resposta."""
    org = str(dados["orgA"].id)
    mq.criar_quadro(_sub(dados, "operador"), org, "Q", [{"nome": "a", "tipo": "texto"}], None, None, None, False)
    # Observador lê.
    assert _j(mq.listar_quadros(_sub(dados, "observador"), org))["quadros"][0]["nome"] == "Q"
    # Quem é de outra organização não enxerga.
    estranho = mq.listar_quadros(_sub(dados, "estranho"), org)
    assert '"quadros"' not in estranho
    # Observador não grava; operador não exclui quadro (é de admin).
    for negado in (
        mq.gravar_linhas(_sub(dados, "observador"), org, "Q", [{"a": "x"}], "acrescentar", False),
        mq.excluir_quadro(_sub(dados, "operador"), org, "Q", True),
    ):
        assert '"ok": true' not in negado and "linhas_apagadas" not in negado and "criadas" not in negado
        # A negação é HONESTA (diz que falta permissão), nunca o erro genérico.
        from mcp_ferramentas import ERRO_INESPERADO
        assert ERRO_INESPERADO not in negado and negado.strip()


def test_mcp_importar_csv_simula_por_padrao(mcp, dados):
    org = str(dados["orgA"].id)
    op = _sub(dados, "operador")
    previa = _j(mq.importar_csv(op, org, CSV_RADAR, None, "Radar", None, None, False, "acrescentar", True))
    assert previa["simulado"] and qs.listar_quadros(mcp, dados["orgA"].id) == []


# ─────────────────────── diagnóstico: o que foi gravado ───────────────────────


def test_diagnostico_mostra_o_que_a_execucao_gravou(sessao, dados):
    import diagnostico_execucao

    org, time = dados["orgA"].id, dados["timeA"]
    auto = Automacao(time_id=time.id, nome="A", tipo_gatilho="manual")
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(automacao_id=auto.id, estado="concluida")
    sessao.add(ex)
    sessao.flush()
    qs.criar_quadro(sessao, org, nome="Log", colunas=[{"nome": "msg", "tipo": "texto"}])
    qs.gravar_linhas(sessao, org, "Log", [{"msg": "a"}, {"msg": "b"}], autor=Autor(origem="agente", execucao_id=ex.id))
    d = diagnostico_execucao.diagnosticar(sessao, ex.id)
    assert d["quadros_gravados"] == [{
        "quadro_id": str(qs.obter_quadro(sessao, org, "Log").id), "quadro": "Log",
        "linhas_com_o_carimbo_desta_execucao": 2, "criou": 2, "mudou": 0, "apagou": 0,
    }]
    outra = Execucao(automacao_id=auto.id, estado="concluida")
    sessao.add(outra)
    sessao.flush()
    assert diagnostico_execucao.diagnosticar(sessao, outra.id)["quadros_gravados"] == []


def test_cinto_do_instrumento_quadro_no_catalogo_da_criadora():
    from criacao.ferramentas import catalogo_de_instrumentos

    tipos_ = {t["tipo"]: t for t in catalogo_de_instrumentos()}
    assert "quadro" in tipos_


def test_fora_da_lista_da_tela_ate_a_entrega_4(cliente, entrar, dados):
    entrar(dados["operador"])
    tipos_ = [t["tipo"] for t in cliente.get("/instrumentos/tipos").json()]
    assert "quadro" not in tipos_
