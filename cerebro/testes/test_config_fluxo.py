"""Resolução da config EFETIVA de uma conversa (fonte única, cascata).

Cobre a cascata global < canal < perfil do fluxo < ajustes do fluxo < nó. Atendimento
puro (sem automação) para em global<canal — igual a hoje (sem regressão).
"""

from mensageria import config as cfg
from modelos import Automacao, Conversa, Execucao, Instrumento


def _inst(sessao, dados, configuracao=None):
    i = Instrumento(
        time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
        configuracao=configuracao or {},
    )
    sessao.add(i)
    sessao.flush()
    return i


def _auto(sessao, dados, configuracao=None):
    a = Automacao(
        time_id=dados["timeA"].id, nome="F", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={"inicial": "n", "nos": []}, ativa=False,
        configuracao=configuracao or {},
    )
    sessao.add(a)
    sessao.flush()
    return a


def _exec(sessao, auto):
    e = Execucao(automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"})
    sessao.add(e)
    sessao.flush()
    return e


def _conversa(sessao, inst, execucao=None):
    c = Conversa(
        instrumento_id=inst.id, contato_chave="x", estado="aberta",
        execucao_id=(execucao.id if execucao else None),
    )
    sessao.add(c)
    sessao.flush()
    return c


def test_atendimento_puro_usa_global_e_canal(sessao, dados):
    inst = _inst(sessao, dados, {"max_turnos": 10})
    r = cfg.resolver_config(sessao, _conversa(sessao, inst))
    assert r["max_turnos"] == 10  # canal sobrepõe global
    assert r["teto_usd"] == 1.0  # global
    assert r["saudacao_abertura"] == cfg.SAUDACAO_PADRAO  # global (ligada)


def test_canal_ignora_chaves_estranhas(sessao, dados):
    inst = _inst(sessao, dados, {"token_bot": "x", "destinatario_padrao": "9", "teto_usd": 0.2})
    r = cfg.resolver_config(sessao, _conversa(sessao, inst))
    assert r["teto_usd"] == 0.2
    assert "token_bot" not in r and "destinatario_padrao" not in r


def test_perfil_interno_sobrepoe_o_canal(sessao, dados):
    inst = _inst(sessao, dados)
    auto = _auto(sessao, dados, {"perfil": "interno"})
    conv = _conversa(sessao, inst, _exec(sessao, auto))
    r = cfg.resolver_config(sessao, conv)
    assert r["saudacao_abertura"] == ""  # interno desliga a saudação
    assert r["timeout_min"] == 30
    assert r["portao_acao_abandono"] == "estacionar"  # parada e retomável (padrão)
    assert r["max_turnos"] == 20


def test_ajustes_do_fluxo_vencem_o_perfil(sessao, dados):
    inst = _inst(sessao, dados)
    auto = _auto(sessao, dados, {"perfil": "interno", "ajustes": {"timeout_min": 99}})
    conv = _conversa(sessao, inst, _exec(sessao, auto))
    r = cfg.resolver_config(sessao, conv)
    assert r["timeout_min"] == 99  # ajuste do fluxo vence o perfil
    assert r["max_turnos"] == 20  # resto do perfil interno permanece


def test_perfil_desconhecido_cai_no_global(sessao, dados):
    inst = _inst(sessao, dados)
    auto = _auto(sessao, dados, {"perfil": "fantasma"})
    conv = _conversa(sessao, inst, _exec(sessao, auto))
    r = cfg.resolver_config(sessao, conv)
    assert r["max_turnos"] == 40  # global


def test_config_da_automacao_sem_conversa(sessao, dados):
    # (Fatia 3) "disparo" saiu dos presets; a forma "direto" continua sendo um VALOR
    # válido, escolhido por ajuste do fluxo (não mais empacotado num preset).
    auto = _auto(sessao, dados, {"perfil": "interno", "ajustes": {"portao_forma": "direto"}})
    r = cfg.config_da_automacao(auto)
    assert r["portao_forma"] == "direto"  # ajuste do fluxo vence o default do perfil
    assert r["max_turnos"] == 20          # default do perfil interno (global seria 40)


def test_ajuste_do_no_e_o_mais_especifico():
    r = cfg.com_ajuste_do_no(dict(cfg.GLOBAL), {"config": {"portao_max_rodadas": 3}})
    assert r["portao_max_rodadas"] == 3


def test_painel_config_tem_perfis_grupos_e_opcoes():
    p = cfg.painel_config()
    ids = {x["id"] for x in p["perfis"]}
    assert ids == {"interno", "atendimento"}  # (Fatia 3) de 4 presets → 2 honestos
    interno = next(x for x in p["perfis"] if x["id"] == "interno")
    assert interno["defaults"]["saudacao_abertura"] == ""  # perfil aplica o default
    # campos de escolha trazem as opções (fonte única, sem duplicar no front)
    forma = next(
        c for g in p["grupos"] for c in g["campos"] if c["chave"] == "portao_forma"
    )
    assert {o["valor"] for o in forma["opcoes"]} == {"conversa", "direto"}


def test_automacao_guarda_configuracao_de_fluxo(sessao, dados):
    from modelos import Automacao
    auto = Automacao(
        time_id=dados["timeA"].id, nome="F", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={"inicial": "n", "nos": []}, ativa=False,
        configuracao={"perfil": "interno", "ajustes": {"teto_usd": 0.3}},
    )
    sessao.add(auto)
    sessao.flush()
    sessao.refresh(auto)
    assert auto.configuracao["perfil"] == "interno"
    assert auto.configuracao["ajustes"]["teto_usd"] == 0.3


# ── Lei nº 1 de 2026-09-14: nenhum teto secreto ────────────────────────────────


def test_todo_limite_do_codigo_esta_na_cascata():
    """Nenhum limite pode viver só como constante de módulo. Os que interrompem
    trabalho de verdade — passos da execução e os tetos do vigia de turno preso —
    eram fixos em `cadeia.py` e `sweeper.py`: não apareciam em tela nenhuma e não
    havia como mudá-los. Agora estão na cascata, com o MESMO valor de antes."""
    from orquestracao.cadeia import MAX_PASSOS

    assert cfg.GLOBAL["max_passos"] == MAX_PASSOS
    assert cfg.GLOBAL["teto_turno_preso_min"] == cfg.TETO_TURNO_PRESO_MIN
    assert (
        cfg.GLOBAL["teto_turno_preso_portao_min"]
        == cfg.TETO_TURNO_PRESO_PORTAO_MIN
    )


def test_todo_limite_aparece_na_tela():
    """Todo limite da cascata tem um botão com rótulo em português. Se alguém criar um
    teto novo e esquecer de expô-lo, este teste quebra — é a trava da lei do maestro."""
    expostos = {c["chave"] for g in cfg.CAMPOS for c in g["campos"]}
    limites = {
        "max_turnos", "teto_usd", "max_passos", "teto_usd_execucao",
        "teto_min_passo", "teto_min_execucao", "portao_max_rodadas",
        "teto_turno_preso_min", "teto_turno_preso_portao_min",
    }
    assert limites <= expostos, f"limite sem botão na tela: {limites - expostos}"


def test_resumo_dos_limites_diz_os_numeros_efetivos():
    efetivo = cfg._mesclar(cfg.GLOBAL, {"portao_max_rodadas": 3, "max_passos": 7})
    texto = " ".join(cfg.resumo_dos_limites(efetivo))
    assert "3 idas-e-vindas" in texto
    assert "7 passos" in texto
    # Teto desligado é dito com todas as letras, não mostrado como "0".
    assert "sem teto" in texto


def test_explicacao_do_limite_diz_o_que_onde_e_que_nada_se_perdeu():
    """O recado que substitui o 'Vou te encaminhar para um atendente humano. Um
    instante.' — que escondia o motivo e vinha junto do canal ficando surdo."""
    msg = cfg.explicacao_limite_portao(
        "custo", cfg.GLOBAL, valor_atual="US$ 0,50"
    )
    assert "US$ 0,50" in msg
    assert "Nada se perdeu" in msg
    assert cfg.URL_APP in msg
    assert cfg.ONDE_MUDAR in msg
    # aponta o botão pelo nome que a pessoa vê na tela, não pela chave técnica
    assert "teto_usd" not in msg


def test_painel_publica_os_limites_de_cada_perfil():
    painel = cfg.painel_config()
    assert painel["onde_mudar"] == cfg.ONDE_MUDAR
    assert painel["limites_padrao"]
    for perfil in painel["perfis"]:
        assert perfil["limites"], f"perfil {perfil['id']} sem resumo de limites"
