"""Testes das ferramentas da IA criadora (Fase 9).

As ferramentas mutam apenas o documento `Rascunho` em memória — sem banco, sem
LLM. Garantem que cada operação faz o que diz e que os erros (papel inválido,
tipo desconhecido, refs inexistentes, cadeia furada) voltam como dado, não como
exceção (a IA corrige na conversa)."""

import json

from criacao.ferramentas import (
    EstadoCriacao,
    catalogo_de_instrumentos,
    ferramenta_por_nome,
)


def _estado():
    e = EstadoCriacao()
    return e, ferramenta_por_nome(e)


def _chamar(ferramentas, _ferramenta, **kwargs):
    return json.loads(ferramentas[_ferramenta].func(**kwargs))


def test_definir_time():
    e, f = _estado()
    r = _chamar(f, "definir_time", nome="Blog SEO", descricao="Artigos")
    assert r["ok"]
    assert e.rascunho.time_nome == "Blog SEO"
    assert e.rascunho.time_descricao == "Artigos"


def test_adicionar_agente_e_um_lider_so():
    e, f = _estado()
    r1 = _chamar(f, "adicionar_agente", nome="Chefe", papel="lider")
    assert r1["ok"] and r1["ref"]
    # segundo líder é barrado
    r2 = _chamar(f, "adicionar_agente", nome="Outro chefe", papel="lider")
    assert r2["ok"] is False
    # agente comum entra normal
    r3 = _chamar(f, "adicionar_agente", nome="Redator", papel="agente")
    assert r3["ok"]
    assert len(e.rascunho.agentes) == 2


def test_papel_invalido_recusado():
    e, f = _estado()
    r = _chamar(f, "adicionar_agente", nome="X", papel="rei")
    assert r["ok"] is False


def test_editar_agente():
    e, f = _estado()
    ref = _chamar(f, "adicionar_agente", nome="X")["ref"]
    r = _chamar(f, "editar_agente", ref=ref, nome="Y", soul_md="gentil")
    assert r["ok"]
    a = e.rascunho.agente_por_ref(ref)
    assert a.nome == "Y" and a.soul_md == "gentil"
    # editar inexistente falha
    assert _chamar(f, "editar_agente", ref="zzz", nome="Z")["ok"] is False


def test_remover_agente_limpa_cadeia():
    e, f = _estado()
    a1 = _chamar(f, "adicionar_agente", nome="A", papel="lider")["ref"]
    a2 = _chamar(f, "adicionar_agente", nome="B", papel="agente")["ref"]
    cadeia = {
        "inicio": a1,
        "nos": {
            a1: {"saidas": [{"rotulo": "1", "quando": "x", "destino": a2}]},
            a2: {"saidas": [{"rotulo": "1", "quando": "fim", "destino": None}]},
        },
    }
    assert _chamar(f, "montar_cadeia", cadeia=cadeia)["ok"]
    # remove o B: some dos nós e das saídas
    assert _chamar(f, "remover_agente", ref=a2)["ok"]
    nos = e.rascunho.automacao.cadeia["nos"]
    assert a2 not in nos
    assert all(
        s["destino"] != a2 for s in nos[a1]["saidas"]
    )


def test_configurar_instrumento_valido_marca_segredos_pendentes():
    e, f = _estado()
    r = _chamar(f, "configurar_instrumento", nome="Busca", tipo="busca_web")
    assert r["ok"] and r["ref"]
    assert r["segredos_pendentes"] == ["chave_api"]
    assert e.rascunho.instrumentos[0].tipo == "busca_web"


def test_configurar_instrumento_tipo_desconhecido():
    e, f = _estado()
    r = _chamar(f, "configurar_instrumento", nome="X", tipo="nao_existe")
    assert r["ok"] is False


def test_configurar_instrumento_config_invalida():
    e, f = _estado()
    # chamar_api_rest exige 'url'; sem ela, a validação recusa
    r = _chamar(f, "configurar_instrumento", nome="API", tipo="chamar_api_rest")
    assert r["ok"] is False


def test_encaixar_instrumento():
    e, f = _estado()
    ag = _chamar(f, "adicionar_agente", nome="A")["ref"]
    inst = _chamar(f, "configurar_instrumento", nome="Busca", tipo="busca_web")["ref"]
    assert _chamar(f, "encaixar_instrumento", agente_ref=ag, instrumento_ref=inst)["ok"]
    assert e.rascunho.agente_por_ref(ag).cinto == [inst]
    # refs inexistentes falham
    assert _chamar(f, "encaixar_instrumento", agente_ref="zz", instrumento_ref=inst)["ok"] is False


def test_montar_cadeia_invalida():
    e, f = _estado()
    a = _chamar(f, "adicionar_agente", nome="Solo", papel="lider")["ref"]
    cadeia = {
        "inicio": a,
        "nos": {a: {"saidas": [{"rotulo": "1", "quando": "x", "destino": "fantasma"}]}},
    }
    assert _chamar(f, "montar_cadeia", cadeia=cadeia)["ok"] is False


def test_definir_gatilho():
    e, f = _estado()
    r = _chamar(f, "definir_gatilho", tipo_gatilho="manual")
    assert r["ok"]
    assert e.rascunho.automacao.gatilho.tipo_gatilho == "manual"


def test_definir_gatilho_agendamento_valido():
    e, f = _estado()
    r = _chamar(
        f,
        "definir_gatilho",
        tipo_gatilho="agendamento",
        configuracao_gatilho={"frequencia": "semanal", "dia_semana": 0, "hora": 8, "minuto": 0},
    )
    assert r["ok"]
    assert e.rascunho.automacao.gatilho.configuracao_gatilho["dia_semana"] == 0


def test_definir_gatilho_malformado_recusado():
    """Regressão: a IA escrevia 'segunda-feira' (texto) em vez do inteiro 0-6, e o
    agendador quebra com isso. Agora o erro volta para a IA corrigir."""
    e, f = _estado()
    # dia_semana em texto
    r1 = _chamar(
        f,
        "definir_gatilho",
        tipo_gatilho="agendamento",
        configuracao_gatilho={"frequencia": "semanal", "dia_semana": "segunda-feira", "hora": 8},
    )
    assert r1["ok"] is False
    # frequência ausente
    r2 = _chamar(
        f, "definir_gatilho", tipo_gatilho="agendamento", configuracao_gatilho={"hora": 8}
    )
    assert r2["ok"] is False
    # tipo desconhecido
    assert _chamar(f, "definir_gatilho", tipo_gatilho="telepatia")["ok"] is False


def test_estimar_custo():
    e, f = _estado()
    _chamar(f, "adicionar_agente", nome="Chefe", papel="lider", modelo_ia="claude-haiku-4-5")
    r = _chamar(
        f,
        "estimar_custo",
        execucoes_por_mes=100,
        tokens_entrada_por_execucao=2000,
        tokens_saida_por_execucao=1000,
    )
    assert r["ok"]
    assert e.rascunho.custo_estimado.por_mes_usd is not None
    assert e.rascunho.custo_estimado.por_mes_usd > 0


def test_listar_tipos_instrumento_traz_os_campos():
    """A IA precisa enxergar os CAMPOS de cada instrumento (com obrigatório/
    secreto) — é o que destrava perguntar pelos dados certos (ex.: URL do blog)."""
    e, f = _estado()
    catalogo = json.loads(f["listar_tipos_instrumento"].func())
    por_tipo = {c["tipo"]: c for c in catalogo}
    assert "busca_web" in por_tipo and "publicar_wordpress" in por_tipo

    wp = por_tipo["publicar_wordpress"]
    campos = {c["nome"]: c for c in wp["campos"]}
    # campos públicos de conexão que a IA deve PERGUNTAR e preencher
    assert "site_url" in campos and campos["site_url"]["secreto"] is False
    assert "usuario" in campos and campos["usuario"]["secreto"] is False
    # o segredo, que a IA NÃO preenche (vai para o cofre depois)
    assert "senha_app" in campos and campos["senha_app"]["secreto"] is True


def test_catalogo_de_instrumentos_marca_obrigatorio_e_secreto():
    catalogo = {c["tipo"]: c for c in catalogo_de_instrumentos()}
    rest = catalogo["chamar_api_rest"]
    campos = {c["nome"]: c for c in rest["campos"]}
    # 'url' é obrigatório e público; 'token_bearer' é secreto
    assert campos["url"]["obrigatorio"] is True and campos["url"]["secreto"] is False
    assert campos["token_bearer"]["secreto"] is True


def test_sugerir_proximos_passos():
    e, f = _estado()
    _chamar(f, "sugerir_proximos_passos", chips=["Sim", "Não", "Me explica", "Outro", "Quinto"])
    assert e.chips == ["Sim", "Não", "Me explica", "Outro"]  # corta em 4


def test_ver_rascunho_reflete_estado():
    e, f = _estado()
    _chamar(f, "definir_time", nome="T")
    visto = json.loads(f["ver_rascunho"].func())
    assert visto["time_nome"] == "T"
