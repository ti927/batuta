"""Serviços de domínio — a porta única que a IA e as rotas usam para escrever no
time real. Cobre as regras (líder único, cadeia válida, instrumento de outro time,
limpeza de cadeia ao remover agente) e a parede de ativação via serviço."""

import pytest

from criacao import servicos
from criacao.servicos import ConflitoDominio
from modelos import Automacao


def test_criar_time_e_agentes(sessao, dados):
    time = servicos.criar_time(sessao, dados["orgA"].id, "Blog", "SEO")
    assert time.id is not None
    lider = servicos.adicionar_agente(sessao, time, nome="Chefe", papel="lider")
    assert lider.papel == "lider"
    # segundo líder é recusado
    with pytest.raises(ConflitoDominio):
        servicos.adicionar_agente(sessao, time, nome="Outro", papel="lider")


def test_configurar_instrumento_separa_segredos(sessao, dados):
    time = servicos.criar_time(sessao, dados["orgA"].id, "T")
    inst, pendentes = servicos.configurar_instrumento(
        sessao, time, nome="WP", tipo="publicar_wordpress",
        configuracao={"site_url": "https://x.com", "usuario": "ana"},
    )
    assert inst.tipo == "publicar_wordpress"
    # senha_app não foi informada → fica pendente; e nunca entra na config pública
    assert "senha_app" in pendentes
    assert "senha_app" not in (inst.configuracao or {})


def test_encaixar_de_outro_time_recusa(sessao, dados):
    t1 = servicos.criar_time(sessao, dados["orgA"].id, "T1")
    t2 = servicos.criar_time(sessao, dados["orgA"].id, "T2")
    ag = servicos.adicionar_agente(sessao, t1, nome="A")
    inst, _ = servicos.configurar_instrumento(sessao, t2, nome="Busca", tipo="busca_web")
    with pytest.raises(ConflitoDominio):
        servicos.encaixar(sessao, ag, inst)


def test_definir_automacao_upsert_e_cadeia_invalida(sessao, dados):
    time = servicos.criar_time(sessao, dados["orgA"].id, "T")
    lider = servicos.adicionar_agente(sessao, time, nome="L", papel="lider")
    cadeia = {
        "inicio": str(lider.id),
        "nos": {str(lider.id): {"saidas": [{"rotulo": "1", "destino": None}]}},
    }
    a1 = servicos.definir_automacao(
        sessao, time, nome="Auto", tipo_gatilho="manual", cadeia=cadeia
    )
    assert a1.ativa is False
    # segunda chamada faz UPSERT (mesma automação, não cria outra)
    a2 = servicos.definir_automacao(
        sessao, time, nome="Auto v2", tipo_gatilho="manual", cadeia=cadeia
    )
    assert a2.id == a1.id and a2.nome == "Auto v2"
    # cadeia apontando para agente inexistente → recusa
    with pytest.raises(ConflitoDominio):
        servicos.definir_automacao(
            sessao, time, nome="X", tipo_gatilho="manual",
            cadeia={"inicio": "fantasma", "nos": {"fantasma": {"saidas": []}}},
        )


def test_ativar_passa_pela_parede(sessao, dados):
    time = servicos.criar_time(sessao, dados["orgA"].id, "Blog")
    guardiao = servicos.adicionar_agente(sessao, time, nome="Guardião", papel="lider")
    pub = servicos.adicionar_agente(sessao, time, nome="Publicador")
    inst, _ = servicos.configurar_instrumento(
        sessao, time, nome="WP", tipo="publicar_wordpress"
    )
    servicos.encaixar(sessao, pub, inst)
    sem_portao = {
        "inicio": str(guardiao.id),
        "nos": {
            str(guardiao.id): {"saidas": [{"rotulo": "1", "destino": str(pub.id)}]},
            str(pub.id): {"saidas": [{"rotulo": "1", "destino": None}]},
        },
    }
    auto = servicos.definir_automacao(
        sessao, time, nome="Pub", tipo_gatilho="manual", cadeia=sem_portao
    )
    # sem portão antes do publicador → ativar recusa
    with pytest.raises(ConflitoDominio):
        servicos.ativar(sessao, auto)
    # com portão no nó do guardião → ativa
    com_portao = dict(sem_portao)
    com_portao["nos"] = dict(sem_portao["nos"])
    com_portao["nos"][str(guardiao.id)] = {
        "pausa_humano": True,
        "saidas": [{"rotulo": "1", "destino": str(pub.id)}],
    }
    servicos.definir_automacao(sessao, time, nome="Pub", tipo_gatilho="manual", cadeia=com_portao)
    auto = servicos.ativar(sessao, auto)
    assert auto.ativa is True


def test_remover_agente_limpa_cadeia(sessao, dados):
    time = servicos.criar_time(sessao, dados["orgA"].id, "T")
    lider = servicos.adicionar_agente(sessao, time, nome="L", papel="lider")
    ag = servicos.adicionar_agente(sessao, time, nome="A")
    cadeia = {
        "inicio": str(lider.id),
        "nos": {
            str(lider.id): {"saidas": [{"rotulo": "1", "destino": str(ag.id)}]},
            str(ag.id): {"saidas": [{"rotulo": "1", "destino": None}]},
        },
    }
    auto = servicos.definir_automacao(sessao, time, nome="A", tipo_gatilho="manual", cadeia=cadeia)
    servicos.remover_agente(sessao, ag)
    sessao.refresh(auto)
    # o nó do agente sumiu e a saída do líder que apontava para ele também
    assert str(ag.id) not in auto.cadeia["nos"]
    assert auto.cadeia["nos"][str(lider.id)]["saidas"] == []
