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
    assert r["portao_acao_abandono"] == "cancelar"
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
    auto = _auto(sessao, dados, {"perfil": "disparo"})
    r = cfg.config_da_automacao(auto)
    assert r["portao_forma"] == "direto"
    assert r["max_turnos"] == 5


def test_ajuste_do_no_e_o_mais_especifico():
    r = cfg.com_ajuste_do_no(dict(cfg.GLOBAL), {"config": {"portao_max_rodadas": 3}})
    assert r["portao_max_rodadas"] == 3
