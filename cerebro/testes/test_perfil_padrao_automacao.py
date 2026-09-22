"""Automação nasce com números sensatos À VISTA, não com uma etiqueta.

Duas correções empilhadas, e a segunda só faz sentido sabendo da primeira.

A primeira (2026-08): toda automação nascia sem nada (`configuracao={}`) e caía no
padrão do Batuta (cutuca em 60 min) sem o usuário perceber — foi o que gerou o
"esperou 60 min" que o maestro estranhou. Passou a nascer como "Processo interno"
(30/15).

A segunda (2026-09-22): o "Processo interno" era uma ETIQUETA. `configuracao` guardava
`{"perfil": "interno"}` e os números moravam no código, aplicados a cada leitura como
uma camada da cascata. Consequência: o efetivo de uma automação nunca estava no dado
dela — para saber o que o próprio fluxo fazia era preciso perguntar a um endpoint. O
botão "Fluxo" existia justamente para mostrar números que não estavam em lugar nenhum,
e por isso nunca conseguiu se explicar ("até hoje não entendi pra que serve").

Agora o modelo é SEMENTE: carimba os valores em `configuracao.ajustes` no nascimento e
sai de cena. A automação carrega os próprios números, visíveis e editáveis.

A prova de que a segunda correção não mudou comportamento é
`test_config_efetivo_do_padrao_cutuca_em_30`, que sobreviveu intacto às duas.
"""

import agendador
from criacao import servicos
from mensageria import config


def _cadeia_valida(lider_id: str) -> dict:
    return {
        "inicio": lider_id,
        "nos": {lider_id: {"saidas": [{"rotulo": "1", "destino": None}]}},
    }


def _ajustes(auto) -> dict:
    return (auto.configuracao or {}).get("ajustes") or {}


def test_definir_automacao_nasce_com_os_numeros_carimbados(sessao, dados):
    time = servicos.criar_time(sessao, dados["orgA"].id, "T")
    lider = servicos.adicionar_agente(sessao, time, nome="L", papel="lider")
    auto = servicos.definir_automacao(
        sessao, time, nome="Auto", tipo_gatilho="manual",
        cadeia=_cadeia_valida(str(lider.id)),
    )
    assert _ajustes(auto)["timeout_min"] == 30
    # A etiqueta não existe mais: o número está no dado, não no código.
    assert "perfil" not in (auto.configuracao or {})


def test_obter_ou_criar_automacao_nasce_com_os_numeros_carimbados(sessao, dados):
    time = servicos.criar_time(sessao, dados["orgA"].id, "T")
    auto = servicos._obter_ou_criar_automacao(sessao, time)
    assert _ajustes(auto)["timeout_min"] == 30
    assert "perfil" not in (auto.configuracao or {})


def test_config_efetivo_do_padrao_cutuca_em_30(sessao, dados):
    """A PROVA DE NÃO-REGRESSÃO: o efetivo continua exatamente o mesmo.

    Esta asserção sobreviveu intacta à troca de etiqueta por número. Se ela cair, a
    migração `prs00preset001` mudou comportamento — que é justamente o que ela promete
    não fazer.
    """
    time = servicos.criar_time(sessao, dados["orgA"].id, "T")
    auto = servicos._obter_ou_criar_automacao(sessao, time)
    efetivo = config.config_da_automacao(auto)
    assert efetivo["timeout_min"] == 30        # interno cutuca em 30 (padrão seria 60)
    assert efetivo["nudge_timeout_min"] == 15  # e encerra 15 depois (padrão seria 30)


def test_criar_pela_rota_sem_modelo_nasce_interno(cliente, entrar, dados, monkeypatch):
    monkeypatch.setattr(agendador, "sincronizar", lambda a: None)
    entrar(dados["operador"])
    r = cliente.post(
        f"/times/{dados['timeA'].id}/automacoes",
        json={"nome": "Sem tipo", "tipo_gatilho": "manual"},
    )
    assert r.status_code == 201, r.text
    ajustes = (r.json().get("configuracao") or {}).get("ajustes") or {}
    assert ajustes["timeout_min"] == 30


def test_criar_pela_rota_respeita_o_modelo_escolhido(cliente, entrar, dados, monkeypatch):
    """Um corpo que traga `perfil` é o formulário dizendo QUAL modelo carimbar.

    Descartá-lo faria a automação nascer diferente do que foi pedido, em silêncio — e
    silêncio é o defeito que esta frente inteira veio matar.
    """
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
    ajustes = (r.json().get("configuracao") or {}).get("ajustes") or {}
    assert ajustes["timeout_min"] == 60   # o do "atendimento", não o do padrão
    assert ajustes["max_turnos"] == 40


def test_criar_pela_rota_nao_pisa_em_ajustes_que_vieram(cliente, entrar, dados, monkeypatch):
    """Quem já manda os ajustes prontos (a tela nova) não é sobrescrito pelo modelo."""
    monkeypatch.setattr(agendador, "sincronizar", lambda a: None)
    entrar(dados["operador"])
    r = cliente.post(
        f"/times/{dados['timeA'].id}/automacoes",
        json={
            "nome": "Na mão",
            "tipo_gatilho": "manual",
            "configuracao": {"ajustes": {"timeout_min": 7}},
        },
    )
    assert r.status_code == 201, r.text
    assert (r.json()["configuracao"]["ajustes"]) == {"timeout_min": 7}
