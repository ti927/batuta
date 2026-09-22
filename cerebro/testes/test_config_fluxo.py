"""Resolução da config EFETIVA de uma conversa (fonte única, cascata).

Cobre a cascata global < canal < ajustes do fluxo < agente do passo. Atendimento
puro (sem automação) para em global<canal — igual a hoje (sem regressão).

E cobre as duas mudanças de 2026-09-22: a partição por DONO (canal/agente/fluxo) e a
morte da camada "Tipo de fluxo", que guardava uma etiqueta cujos números moravam no
código — e por isso o botão que a exibia nunca conseguiu se explicar.
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


def test_os_ajustes_do_fluxo_sobrepoem_o_canal(sessao, dados):
    """O fluxo carrega os PRÓPRIOS números (o preset foi carimbado no nascimento)."""
    inst = _inst(sessao, dados)
    auto = _auto(sessao, dados, cfg.configuracao_inicial("interno"))
    conv = _conversa(sessao, inst, _exec(sessao, auto))
    r = cfg.resolver_config(sessao, conv)
    assert r["timeout_min"] == 30
    assert r["portao_acao_abandono"] == "estacionar"  # parada e retomável (padrão)
    assert r["max_turnos"] == 20
    # A saudação NÃO entra nesta conta: ela é do canal (2026-09-22).
    assert r["saudacao_abertura"] == cfg.SAUDACAO_PADRAO  # o canal é que manda


def test_a_etiqueta_perfil_virou_historico_inerte(sessao, dados):
    """Uma linha legada que ainda carregue `perfil` não pode mais mudar nada.

    Era este o defeito de origem: a etiqueta apontava para números que moravam no
    código, então o efetivo de uma automação nunca estava no dado dela — e o botão
    "Fluxo" existia para mostrar números que não estavam em lugar nenhum.
    """
    inst = _inst(sessao, dados)
    auto = _auto(sessao, dados, {"perfil": "interno"})  # só a etiqueta, sem ajustes
    r = cfg.resolver_config(sessao, _conversa(sessao, inst, _exec(sessao, auto)))
    assert r["timeout_min"] == cfg.GLOBAL["timeout_min"]  # 60, o padrão do Batuta
    assert r["max_turnos"] == cfg.GLOBAL["max_turnos"]


def test_o_fluxo_nao_apaga_mais_a_saudacao_do_bot(sessao, dados):
    """A regressão que originou a arrumação de 2026-09-22.

    O bot tinha uma saudação escrita à mão ("Sou o assistente de reembolsos…"); o
    perfil "interno" — padrão de toda automação nova — fixava `saudacao_abertura: ""`,
    e como `_mesclar` só ignora `None`, esse vazio explícito vencia. A pessoa
    configurava o bot e o texto dela sumia sem aviso. Agora a saudação é do CANAL, e
    nenhuma camada de fluxo alcança essa chave.
    """
    minha = "Olá! Sou o assistente de reembolsos da Lure."
    inst = _inst(sessao, dados, {"saudacao_abertura": minha})
    # Pior caso: alguém deixou o ajuste de atendimento no fluxo.
    auto = _auto(
        sessao, dados, {"ajustes": {"saudacao_abertura": "", "max_turnos": 7}}
    )
    r = cfg.resolver_config(sessao, _conversa(sessao, inst, _exec(sessao, auto)))
    assert r["saudacao_abertura"] == minha
    assert r["max_turnos"] == 7  # o que é do fluxo continua valendo normalmente


def test_ajuste_de_canal_no_fluxo_fica_inerte_sem_migracao(sessao, dados):
    """Duas automações em produção tinham chaves de atendimento nos `ajustes`. Elas
    ficam INERTES por código — não foi preciso tocar o banco."""
    inst = _inst(sessao, dados, {"dias_uteis_apenas": True})
    auto = _auto(sessao, dados, {"ajustes": {"dias_uteis_apenas": False}})
    r = cfg.resolver_config(sessao, _conversa(sessao, inst, _exec(sessao, auto)))
    assert r["dias_uteis_apenas"] is True  # o canal é o dono


def test_ajustes_do_fluxo_vencem_o_padrao_do_batuta(sessao, dados):
    inst = _inst(sessao, dados)
    ajustes = {**cfg.PRESETS["interno"], "timeout_min": 99}
    auto = _auto(sessao, dados, {"ajustes": ajustes})
    conv = _conversa(sessao, inst, _exec(sessao, auto))
    r = cfg.resolver_config(sessao, conv)
    assert r["timeout_min"] == 99
    assert r["max_turnos"] == 20   # o resto do que o modelo carimbou permanece
    assert r["teto_usd_execucao"] == cfg.GLOBAL["teto_usd_execucao"]  # não carimbado


def test_configuracao_vazia_cai_no_padrao_do_batuta(sessao, dados):
    inst = _inst(sessao, dados)
    auto = _auto(sessao, dados, {})
    conv = _conversa(sessao, inst, _exec(sessao, auto))
    r = cfg.resolver_config(sessao, conv)
    assert r["max_turnos"] == 40  # global


def test_config_da_automacao_sem_conversa(sessao, dados):
    auto = _auto(
        sessao, dados,
        {"ajustes": {**cfg.PRESETS["interno"], "portao_forma": "direto"}},
    )
    r = cfg.config_da_automacao(auto)
    assert r["portao_forma"] == "direto"
    assert r["max_turnos"] == 20          # o modelo carimbou (o padrão seria 40)


def test_ajuste_do_no_e_o_mais_especifico():
    r = cfg.com_ajuste_do_no(dict(cfg.GLOBAL), {"config": {"portao_max_rodadas": 3}})
    assert r["portao_max_rodadas"] == 3


def test_painel_config_tem_presets_grupos_e_opcoes():
    p = cfg.painel_config()
    ids = {x["id"] for x in p["presets"]}
    assert ids == {"interno", "atendimento"}
    interno = next(x for x in p["presets"] if x["id"] == "interno")
    assert interno["defaults"]["timeout_min"] == 30
    # `ajustes` é o que o botão "partir de um modelo" carimba — a tela precisa dos
    # números crus, não só do efetivo já mesclado.
    assert interno["ajustes"]["timeout_min"] == 30
    # Cada grupo diz de QUEM é a regra — sem isso a tela volta a mostrar dois níveis
    # sem distinguir um do outro, que foi a origem desta arrumação.
    assert {g["nivel"] for g in p["grupos"]} <= {"fluxo", "agente"}
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


def test_painel_publica_os_limites_de_cada_preset():
    painel = cfg.painel_config()
    assert painel["onde_mudar"] == cfg.ONDE_MUDAR
    assert painel["limites_padrao"]
    for preset in painel["presets"]:
        assert preset["limites"], f"preset {preset['id']} sem resumo de limites"
