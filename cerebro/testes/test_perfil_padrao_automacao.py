"""Automação nasce com um TIPO DE FLUXO sensato (perfil "interno").

Antes, toda automação nascia sem perfil (`configuracao={}`) e caía no padrão geral
(cutuca em 60 min) sem o usuário perceber — foi o que gerou o "esperou 60 min" que
o maestro estranhou. Agora ela nasce como "Processo interno" (30/15) em todos os
pontos de nascimento (IA criadora e create manual), sem tirar a liberdade de escolher
outro tipo. O duplicar copia o perfil da original (coberto em test_duplicar_automacao).
"""

import agendador
from criacao import servicos
from mensageria import config


def _cadeia_valida(lider_id: str) -> dict:
    return {
        "inicio": lider_id,
        "nos": {lider_id: {"saidas": [{"rotulo": "1", "destino": None}]}},
    }


def test_definir_automacao_nasce_com_perfil_interno(sessao, dados):
    time = servicos.criar_time(sessao, dados["orgA"].id, "T")
    lider = servicos.adicionar_agente(sessao, time, nome="L", papel="lider")
    auto = servicos.definir_automacao(
        sessao, time, nome="Auto", tipo_gatilho="manual",
        cadeia=_cadeia_valida(str(lider.id)),
    )
    assert (auto.configuracao or {}).get("perfil") == "interno"


def test_obter_ou_criar_automacao_nasce_com_perfil_interno(sessao, dados):
    time = servicos.criar_time(sessao, dados["orgA"].id, "T")
    auto = servicos._obter_ou_criar_automacao(sessao, time)
    assert (auto.configuracao or {}).get("perfil") == "interno"


def test_config_efetivo_do_perfil_padrao_cutuca_em_30(sessao, dados):
    """O perfil plantado no nascimento REALMENTE muda a temporização efetiva."""
    time = servicos.criar_time(sessao, dados["orgA"].id, "T")
    auto = servicos._obter_ou_criar_automacao(sessao, time)
    efetivo = config.config_da_automacao(auto)
    assert efetivo["timeout_min"] == 30       # interno cutuca em 30 (global seria 60)
    assert efetivo["nudge_timeout_min"] == 15  # e encerra 15 depois (global seria 30)


def test_criar_pela_rota_sem_perfil_nasce_interno(cliente, entrar, dados, monkeypatch):
    monkeypatch.setattr(agendador, "sincronizar", lambda a: None)
    entrar(dados["operador"])
    r = cliente.post(
        f"/times/{dados['timeA'].id}/automacoes",
        json={"nome": "Sem tipo", "tipo_gatilho": "manual"},
    )
    assert r.status_code == 201, r.text
    assert (r.json().get("configuracao") or {}).get("perfil") == "interno"


def test_criar_pela_rota_respeita_perfil_explicito(cliente, entrar, dados, monkeypatch):
    """Se o formulário manda um tipo, o backend NÃO sobrescreve com o padrão."""
    monkeypatch.setattr(agendador, "sincronizar", lambda a: None)
    entrar(dados["operador"])
    r = cliente.post(
        f"/times/{dados['timeA'].id}/automacoes",
        json={
            "nome": "Atendimento",
            "tipo_gatilho": "manual",
            "configuracao": {"perfil": "atendimento"},
        },
    )
    assert r.status_code == 201, r.text
    assert (r.json().get("configuracao") or {}).get("perfil") == "atendimento"
