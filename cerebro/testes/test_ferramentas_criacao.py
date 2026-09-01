"""Testes das ferramentas da IA criadora — agora sobre o TIME REAL.

As ferramentas escrevem nas tabelas (via criacao.servicos), ligadas a uma conversa.
Garantem que cada operação faz o que diz, que os erros (papel inválido, tipo
desconhecido, ids inexistentes, cadeia furada, parede de ativação) voltam como DADO
(a IA corrige na conversa), e que a parede recusa ativar ação irreversível sem portão."""

import json

from criacao.ferramentas import (
    ContextoCriacao,
    catalogo_de_instrumentos,
    ferramenta_por_nome,
)
from modelos import Automacao, ConversaCriacao, Execucao


def _setup(sessao, dados):
    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id, criada_por_id=dados["admin"].id
    )
    sessao.add(conversa)
    sessao.flush()
    ctx = ContextoCriacao(sessao=sessao, conversa=conversa, usuario=dados["admin"])
    return ctx, ferramenta_por_nome(ctx)


def _chamar(f, ferramenta, **kwargs):
    return json.loads(f[ferramenta].func(**kwargs))


def test_definir_time_cria_time_real(sessao, dados):
    ctx, f = _setup(sessao, dados)
    r = _chamar(f, "definir_time", nome="Blog SEO", descricao="Artigos")
    assert r["ok"] and r["time_id"]
    assert ctx.time().nome == "Blog SEO"
    # segunda chamada atualiza (não cria outro)
    r2 = _chamar(f, "definir_time", nome="Blog SEO v2")
    assert r2["time_id"] == r["time_id"]
    assert ctx.time().nome == "Blog SEO v2"


def test_agente_exige_time_primeiro(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    assert _chamar(f, "adicionar_agente", nome="X")["ok"] is False


def test_adicionar_agente_e_um_lider_so(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    r1 = _chamar(f, "adicionar_agente", nome="Chefe", papel="lider")
    assert r1["ok"] and r1["id"]
    assert _chamar(f, "adicionar_agente", nome="Outro", papel="lider")["ok"] is False
    assert _chamar(f, "adicionar_agente", nome="Redator", papel="agente")["ok"]
    assert _chamar(f, "adicionar_agente", nome="X", papel="rei")["ok"] is False


def test_editar_agente(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    aid = _chamar(f, "adicionar_agente", nome="X")["id"]
    assert _chamar(f, "editar_agente", agente_id=aid, nome="Y", soul_md="gentil")["ok"]
    assert _chamar(f, "editar_agente", agente_id="00000000-0000-0000-0000-000000000000", nome="Z")["ok"] is False


def test_atualizar_resumo_escreve_o_resumo_do_projeto(sessao, dados):
    # A IA mantém o "resumo do projeto" (painel 'Sobre este time') por ferramenta —
    # é diferente da descrição do time e da memória de longo prazo.
    ctx, f = _setup(sessao, dados)
    r = _chamar(f, "atualizar_resumo", resumo="  Time de blog; público é o decisor.  ")
    assert r["ok"]
    assert ctx.conversa.resumo == "Time de blog; público é o decisor."  # com trim
    # texto vazio zera (NULL)
    assert _chamar(f, "atualizar_resumo", resumo="   ")["ok"]
    assert ctx.conversa.resumo is None


def test_remover_agente_limpa_cadeia(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    a1 = _chamar(f, "adicionar_agente", nome="A", papel="lider")["id"]
    a2 = _chamar(f, "adicionar_agente", nome="B", papel="agente")["id"]
    cadeia = {
        "inicio": a1,
        "nos": {
            a1: {"saidas": [{"rotulo": "1", "quando": "x", "destino": a2}]},
            a2: {"saidas": [{"rotulo": "1", "quando": "fim", "destino": None}]},
        },
    }
    assert _chamar(f, "montar_cadeia", cadeia=cadeia)["ok"]
    assert _chamar(f, "remover_agente", agente_id=a2)["ok"]
    visto = json.loads(f["ver_time"].func())
    # cadeia é grafo (lista de nós): indexa por id
    nos = {n["id"]: n for n in visto["automacao"]["cadeia"]["nos"]}
    assert a2 not in nos
    assert all(s["destino"] != a2 for s in nos[a1]["saidas"])


def test_configurar_instrumento_marca_segredos_pendentes(sessao, dados, monkeypatch):
    # Sem chave Tavily em lugar nenhum (cofre vazio pelo conftest + .env sem a
    # variável): aí sim a chave da busca conta como pendente.
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    r = _chamar(f, "configurar_instrumento", nome="Busca", tipo="busca_web")
    assert r["ok"] and r["id"]
    assert r["segredos_pendentes"] == ["chave_api"]


def test_configurar_instrumento_tipo_desconhecido_e_config_invalida(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    assert _chamar(f, "configurar_instrumento", nome="X", tipo="nao_existe")["ok"] is False
    # chamar_api_rest exige 'url'
    assert _chamar(f, "configurar_instrumento", nome="API", tipo="chamar_api_rest")["ok"] is False


def test_encaixar_instrumento(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    ag = _chamar(f, "adicionar_agente", nome="A")["id"]
    inst = _chamar(f, "configurar_instrumento", nome="Busca", tipo="busca_web")["id"]
    assert _chamar(f, "encaixar_instrumento", agente_id=ag, instrumento_id=inst)["ok"]
    visto = json.loads(f["ver_time"].func())
    agente = next(a for a in visto["agentes"] if a["id"] == ag)
    assert agente["cinto"] == [inst]
    assert _chamar(f, "encaixar_instrumento", agente_id="00000000-0000-0000-0000-000000000000", instrumento_id=inst)["ok"] is False


def test_montar_cadeia_grafo_normaliza(sessao, dados):
    """A IA monta um grafo simplificado (bifurcação + gate, sem posições nem nós
    estruturais); a normalização completa ids/posições e cria gatilho/fim."""
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    cacador = _chamar(f, "adicionar_agente", nome="Cacador", papel="lider")["id"]
    validador = _chamar(f, "adicionar_agente", nome="Validador")["id"]
    cadeia = {
        "inicial": "n_cacador",
        "nos": [
            {"id": "n_cacador", "tipo": "agente", "ref": cacador,
             "saidas": [{"rotulo": "tema", "destino": "n_val"}]},
            {"id": "n_val", "tipo": "agente", "ref": validador, "gate": True,
             "saidas": [
                 {"rotulo": "aprovado", "quando": "a pessoa aprovar o tema",
                  "destino": "fim"},
                 {"rotulo": "refazer", "quando": "a pessoa pedir outro tema",
                  "destino": "n_cacador"},  # loop
             ]},
        ],
    }
    assert _chamar(f, "montar_cadeia", cadeia=cadeia)["ok"]
    visto = json.loads(f["ver_time"].func())
    g = visto["automacao"]["cadeia"]
    nos = {n["id"]: n for n in g["nos"]}
    assert g["inicial"] == "n_cacador"
    # nós estruturais criados; gate preservado; loop preservado
    assert "gatilho" in nos and "fim" in nos
    assert nos["n_val"]["gate"] is True
    assert any(s["destino"] == "n_cacador" for s in nos["n_val"]["saidas"])
    # posições e ids de saída preenchidos
    assert all("x" in n and "y" in n for n in g["nos"])
    assert all(s.get("id") for s in nos["n_cacador"]["saidas"])


def test_montar_cadeia_invalida(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    a = _chamar(f, "adicionar_agente", nome="Solo", papel="lider")["id"]
    cadeia = {"inicio": a, "nos": {a: {"saidas": [{"rotulo": "1", "quando": "x", "destino": "fantasma"}]}}}
    assert _chamar(f, "montar_cadeia", cadeia=cadeia)["ok"] is False


def test_definir_gatilho_e_malformado(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    assert _chamar(f, "definir_gatilho", tipo_gatilho="manual")["ok"]
    assert _chamar(
        f, "definir_gatilho", tipo_gatilho="agendamento",
        configuracao_gatilho={"frequencia": "semanal", "dia_semana": 0, "hora": 8, "minuto": 0},
    )["ok"]
    # dia_semana em texto → recusa (regressão: a IA escrevia 'segunda-feira')
    assert _chamar(
        f, "definir_gatilho", tipo_gatilho="agendamento",
        configuracao_gatilho={"frequencia": "semanal", "dia_semana": "segunda-feira", "hora": 8},
    )["ok"] is False
    assert _chamar(f, "definir_gatilho", tipo_gatilho="telepatia")["ok"] is False


# ───────────── Várias automações por time (a IA cria/edita cada uma por id) ─────────────

_CADEIA_MIN = lambda lider: {  # noqa: E731 (cadeia mínima válida: 1 nó → fim)
    "inicio": lider, "nos": {lider: {"saidas": [{"rotulo": "1", "quando": "x", "destino": None}]}}
}


def test_varias_automacoes_por_time(sessao, dados):
    """A IA cria uma 2ª automação SEM sobrescrever a 1ª; o retrato mostra as duas."""
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    lider = _chamar(f, "adicionar_agente", nome="Chefe", papel="lider")["id"]
    assert _chamar(f, "montar_cadeia", cadeia=_CADEIA_MIN(lider))["ok"]  # cria a 1ª
    r = _chamar(f, "criar_automacao", nome="Segunda")
    assert r["ok"] and r["id"]
    visto = json.loads(f["ver_time"].func())
    assert len(visto["automacoes"]) == 2
    assert "Segunda" in {a["nome"] for a in visto["automacoes"]}
    # compat: 'automacao' (singular, para o canvas) segue sendo a PRIMEIRA
    assert visto["automacao"]["id"] == visto["automacoes"][0]["id"]


def test_definir_gatilho_por_id_nao_toca_a_outra(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    lider = _chamar(f, "adicionar_agente", nome="Chefe", papel="lider")["id"]
    _chamar(f, "montar_cadeia", cadeia=_CADEIA_MIN(lider))
    id2 = _chamar(f, "criar_automacao", nome="Segunda")["id"]
    assert _chamar(f, "definir_gatilho", tipo_gatilho="webhook", automacao_id=id2)["ok"]
    porid = {a["id"]: a for a in json.loads(f["ver_time"].func())["automacoes"]}
    assert porid[id2]["tipo_gatilho"] == "webhook"
    id1 = next(i for i in porid if i != id2)
    assert porid[id1]["tipo_gatilho"] == "manual"  # a 1ª ficou intocada


def test_acao_ambigua_com_varias_pede_qual(sessao, dados):
    """Com mais de uma automação e SEM automacao_id, a ferramenta recusa pedindo qual."""
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    lider = _chamar(f, "adicionar_agente", nome="Chefe", papel="lider")["id"]
    _chamar(f, "montar_cadeia", cadeia=_CADEIA_MIN(lider))
    _chamar(f, "criar_automacao", nome="Segunda")
    r = _chamar(f, "definir_gatilho", tipo_gatilho="webhook")  # ambíguo
    assert r["ok"] is False
    assert "automaç" in r["erro"].lower() or "qual" in r["erro"].lower()


def test_ativar_desativar_por_id(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    lider = _chamar(f, "adicionar_agente", nome="Chefe", papel="lider")["id"]
    _chamar(f, "montar_cadeia", cadeia=_CADEIA_MIN(lider))
    id2 = _chamar(f, "criar_automacao", nome="Segunda")["id"]
    assert _chamar(f, "ativar_time", automacao_id=id2)["ok"]  # liga a 2ª
    porid = {a["id"]: a for a in json.loads(f["ver_time"].func())["automacoes"]}
    assert porid[id2]["ativa"] is True
    assert porid[next(i for i in porid if i != id2)]["ativa"] is False  # 1ª segue off
    assert _chamar(f, "desativar_time", automacao_id=id2)["ok"]


def test_renomear_automacao(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    lider = _chamar(f, "adicionar_agente", nome="Chefe", papel="lider")["id"]
    _chamar(f, "montar_cadeia", cadeia=_CADEIA_MIN(lider))
    aid = json.loads(f["ver_time"].func())["automacao"]["id"]
    assert _chamar(f, "renomear_automacao", automacao_id=aid, nome="Postar no blog")["ok"]
    assert json.loads(f["ver_time"].func())["automacao"]["nome"] == "Postar no blog"


def test_estimar_custo_calcula_sem_gravar(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    _chamar(f, "adicionar_agente", nome="Chefe", papel="lider", modelo_ia="claude-haiku-4-5")
    r = _chamar(
        f, "estimar_custo", execucoes_por_mes=100,
        tokens_entrada_por_execucao=2000, tokens_saida_por_execucao=1000,
    )
    assert r["ok"] and r["por_mes_usd"] > 0


def test_ativar_nao_exige_mais_portao(sessao, dados):
    """A PAREDE morreu: a IA criadora ativa um time com agente de ação irreversível
    sem precisar desenhar portão nenhum antes."""
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="Blog")
    lider = _chamar(f, "adicionar_agente", nome="Guardião", papel="lider")["id"]
    pub = _chamar(f, "adicionar_agente", nome="Publicador")["id"]
    inst = _chamar(f, "configurar_instrumento", nome="WP", tipo="publicar_wordpress")["id"]
    _chamar(f, "encaixar_instrumento", agente_id=pub, instrumento_id=inst)
    _chamar(f, "definir_gatilho", tipo_gatilho="manual")
    cadeia = {
        "inicio": lider,
        "nos": {
            lider: {"saidas": [{"rotulo": "1", "destino": pub}]},
            pub: {"saidas": [{"rotulo": "1", "destino": None}]},
        },
    }
    _chamar(f, "montar_cadeia", cadeia=cadeia)
    assert _chamar(f, "ativar_time")["ok"]


def test_listar_tipos_traz_campos_e_irreversivel(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    catalogo = json.loads(f["listar_tipos_instrumento"].func())
    por_tipo = {c["tipo"]: c for c in catalogo}
    wp = por_tipo["publicar_wordpress"]
    campos = {c["nome"]: c for c in wp["campos"]}
    assert campos["site_url"]["secreto"] is False
    assert campos["senha_app"]["secreto"] is True
    assert wp["acao_irreversivel"] is True
    assert por_tipo["busca_web"]["acao_irreversivel"] is False


def test_catalogo_marca_obrigatorio_e_secreto():
    catalogo = {c["tipo"]: c for c in catalogo_de_instrumentos()}
    campos = {c["nome"]: c for c in catalogo["chamar_api_rest"]["campos"]}
    assert campos["url"]["obrigatorio"] is True and campos["url"]["secreto"] is False
    assert campos["token_bearer"]["secreto"] is True


def test_sugerir_proximos_passos_corta_em_4(sessao, dados):
    ctx, f = _setup(sessao, dados)
    _chamar(f, "sugerir_proximos_passos", chips=["a", "b", "c", "d", "e"])
    assert ctx.chips == ["a", "b", "c", "d"]


def test_ver_time_sem_time(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    r = json.loads(f["ver_time"].func())
    assert r.get("time") is None


# ───────────────── diagnóstico de execução (escopo das tools) ─────────────────

def _automacao_com_exec(sessao, time_id, estado, **kw):
    auto = Automacao(
        time_id=time_id, nome="A", tipo_gatilho="manual", configuracao_gatilho={},
        cadeia={}, ativa=True,
    )
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(automacao_id=auto.id, estado=estado, entrada={"texto": "x"}, **kw)
    sessao.add(ex)
    sessao.flush()
    return ex


def test_listar_execucoes_escopa_ao_time(sessao, dados):
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    ex_meu = _automacao_com_exec(sessao, ctx.conversa.time_id, "falhou", resultado={"erro": "y"})
    ex_outro = _automacao_com_exec(sessao, dados["timeA"].id, "falhou")  # outro time
    r = _chamar(f, "listar_execucoes")
    ids = {e["execucao_id"] for e in r["execucoes"]}
    assert str(ex_meu.id) in ids
    assert str(ex_outro.id) not in ids


def test_diagnosticar_execucao_de_outro_time_recusa(sessao, dados):
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    ex_outro = _automacao_com_exec(sessao, dados["timeA"].id, "falhou", resultado={"erro": "z"})
    r = _chamar(f, "diagnosticar_execucao", execucao_id=str(ex_outro.id))
    assert r["ok"] is False


def test_diagnosticar_sem_id_pega_mais_recente_com_problema(sessao, dados):
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    # uma concluída (ignorada por não ter problema) e uma falhada (a alvo)
    _automacao_com_exec(sessao, ctx.conversa.time_id, "concluida", resultado={"texto": "ok"})
    ex_falhou = _automacao_com_exec(
        sessao, ctx.conversa.time_id, "falhou",
        resultado={"erro": "Error code: 529 overloaded_error"},
    )
    r = _chamar(f, "diagnosticar_execucao")
    assert r["ok"] and r["diagnostico"]["execucao_id"] == str(ex_falhou.id)
    assert any(a["codigo"] == "ia_sobrecarregada" for a in r["diagnostico"]["avisos"])


def test_buscar_no_historico_acha_antigo_e_ignora_a_janela(sessao, dados):
    """Parte C (iceberg): a busca varre só os turnos JÁ DOBRADOS (mensagens[:resumo_ate]);
    os recentes (na janela) já estão no contexto, então NÃO entram no resultado."""
    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id,
        resumo_ate=4,  # os 4 primeiros saíram da janela (estão no resumo)
        mensagens=[
            {"papel": "usuario", "conteudo": "combinamos usar tom FORMAL no blog"},
            {"papel": "ia", "conteudo": "ok, registrei o tom formal"},
            {"papel": "usuario", "conteudo": "assunto qualquer"},
            {"papel": "ia", "conteudo": "certo"},
            {"papel": "usuario", "conteudo": "recente falando de tom de novo"},
            {"papel": "ia", "conteudo": "tom recente"},
        ],
    )
    sessao.add(conversa)
    sessao.flush()
    ctx = ContextoCriacao(sessao=sessao, conversa=conversa, usuario=dados["admin"])
    f = ferramenta_por_nome(ctx)

    r = _chamar(f, "buscar_no_historico", consulta="formal")
    assert r["ok"] and len(r["achados"]) >= 1
    assert "tom FORMAL" in " ".join(a["conteudo"] for a in r["achados"])
    # "recente" está na janela (idx >= resumo_ate) → NÃO é varrido pela busca.
    r2 = _chamar(f, "buscar_no_historico", consulta="recente")
    assert r2["ok"] and r2["achados"] == []


def test_buscar_no_historico_vazio_erra_e_sem_match_ok(sessao, dados):
    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id,
        resumo_ate=2,
        mensagens=[
            {"papel": "usuario", "conteudo": "algo antigo"},
            {"papel": "ia", "conteudo": "resposta antiga"},
        ],
    )
    sessao.add(conversa)
    sessao.flush()
    ctx = ContextoCriacao(sessao=sessao, conversa=conversa, usuario=dados["admin"])
    f = ferramenta_por_nome(ctx)

    assert _chamar(f, "buscar_no_historico", consulta="   ")["ok"] is False  # vazio
    achou = _chamar(f, "buscar_no_historico", consulta="inexistente-xyz")
    assert achou["ok"] and achou["achados"] == []  # sem casar, mas responde ok
