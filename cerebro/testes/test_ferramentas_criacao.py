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
from modelos import ConversaCriacao


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
    nos = visto["automacao"]["cadeia"]["nos"]
    assert a2 not in nos
    assert all(s["destino"] != a2 for s in nos[a1]["saidas"])


def test_configurar_instrumento_marca_segredos_pendentes(sessao, dados):
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


def test_estimar_custo_calcula_sem_gravar(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    _chamar(f, "adicionar_agente", nome="Chefe", papel="lider", modelo_ia="claude-haiku-4-5")
    r = _chamar(
        f, "estimar_custo", execucoes_por_mes=100,
        tokens_entrada_por_execucao=2000, tokens_saida_por_execucao=1000,
    )
    assert r["ok"] and r["por_mes_usd"] > 0


def test_ativar_recusa_acao_irreversivel_sem_portao(sessao, dados):
    _ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="Blog")
    lider = _chamar(f, "adicionar_agente", nome="Guardião", papel="lider")["id"]
    pub = _chamar(f, "adicionar_agente", nome="Publicador")["id"]
    inst = _chamar(f, "configurar_instrumento", nome="WP", tipo="publicar_wordpress")["id"]
    _chamar(f, "encaixar_instrumento", agente_id=pub, instrumento_id=inst)
    _chamar(f, "definir_gatilho", tipo_gatilho="manual")
    sem_portao = {
        "inicio": lider,
        "nos": {
            lider: {"saidas": [{"rotulo": "1", "destino": pub}]},
            pub: {"saidas": [{"rotulo": "1", "destino": None}]},
        },
    }
    _chamar(f, "montar_cadeia", cadeia=sem_portao)
    assert _chamar(f, "ativar_time")["ok"] is False  # parede
    com_portao = {
        "inicio": lider,
        "nos": {
            lider: {"pausa_humano": True, "saidas": [{"rotulo": "1", "destino": pub}]},
            pub: {"saidas": [{"rotulo": "1", "destino": None}]},
        },
    }
    _chamar(f, "montar_cadeia", cadeia=com_portao)
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
