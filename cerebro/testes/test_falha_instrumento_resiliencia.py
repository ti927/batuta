"""Resiliência a falha de instrumento (decisão do maestro 2026-06-18).

Uma falha de instrumento de LEITURA (busca, consulta) NÃO deve derrubar a
execução inteira — o agente recebe o erro e decide. Já uma falha de AÇÃO
IRREVERSÍVEL (publicar/enviar/gravar) continua derrubando, para nunca fingir que
a ação aconteceu (PRODUTO §16). O critério é o mesmo da parede de ativação
(`acao_irreversivel`), exercitado aqui no nível da ferramenta do agente.
"""

import json
import uuid

import pytest

import instrumentos as encaixe
import orquestracao.agente as agente_mod
from instrumentos.base import FalhaInstrumento
from modelos import Instrumento


def _ferramenta(tipo_str: str, configuracao: dict, monkeypatch):
    """Monta a ferramenta única de um instrumento com `acionar` sempre falhando,
    e devolve (tool, falhas) para inspecionar o efeito."""
    tipo = encaixe.obter_tipo(tipo_str)
    inst = Instrumento(
        time_id=uuid.uuid4(), nome="Teste", tipo=tipo_str, configuracao=configuracao
    )
    inst.id = uuid.uuid4()
    config = tipo.Config.model_validate(configuracao)

    def explode(t, c, a):
        raise FalhaInstrumento("o provedor recusou (teste)")

    monkeypatch.setattr(agente_mod, "acionar_com_retentativa", explode)
    falhas: list[str] = []
    erros: list[dict] = []
    tool = agente_mod._ferramenta_unica(inst, tipo, config, falhas, {}, erros)
    return tool, falhas, erros


def test_falha_de_leitura_nao_derruba_execucao(monkeypatch):
    # busca_web = leitura (acao_irreversivel False)
    tool, falhas, erros = _ferramenta("busca_web", {}, monkeypatch)
    saida = json.loads(tool.func(consulta="reforma tributária 2026"))
    assert saida["ok"] is False
    assert "dica" in saida  # o agente é orientado a seguir/tentar de novo
    assert falhas == []  # NÃO entra na lista que derruba a execução
    # mas o erro CRU é registrado (para o diagnóstico dizer o que aconteceu).
    assert len(erros) == 1
    assert erros[0]["irreversivel"] is False and "recusou" in erros[0]["erro"]


def test_falha_de_escrita_derruba_execucao(monkeypatch):
    # enviar_telegram = ação irreversível (manda para fora)
    tool, falhas, erros = _ferramenta("enviar_telegram", {"token_bot": "x"}, monkeypatch)
    saida = json.loads(tool.func(destinatario="123", mensagem="oi"))
    assert saida["ok"] is False
    assert len(falhas) == 1  # vira falha fatal e visível
    assert len(erros) == 1 and erros[0]["irreversivel"] is True


def test_turno_misto_so_a_escrita_conta(monkeypatch):
    """No MESMO turno (lista `falhas` compartilhada), uma busca que falha NÃO conta
    como fatal, mas uma escrita que falha conta — então a execução só é derrubada
    pela escrita."""

    def explode(t, c, a):
        raise FalhaInstrumento("o provedor recusou (teste)")

    monkeypatch.setattr(agente_mod, "acionar_com_retentativa", explode)
    falhas: list[str] = []
    erros: list[dict] = []

    busca = encaixe.obter_tipo("busca_web")
    inst_b = Instrumento(
        time_id=uuid.uuid4(), nome="Busca", tipo="busca_web", configuracao={}
    )
    inst_b.id = uuid.uuid4()
    tool_b = agente_mod._ferramenta_unica(inst_b, busca, busca.Config(), falhas, {}, erros)

    tg = encaixe.obter_tipo("enviar_telegram")
    inst_t = Instrumento(
        time_id=uuid.uuid4(), nome="Telegram", tipo="enviar_telegram",
        configuracao={"token_bot": "x"},
    )
    inst_t.id = uuid.uuid4()
    tool_t = agente_mod._ferramenta_unica(
        inst_t, tg, tg.Config.model_validate({"token_bot": "x"}), falhas, {}, erros
    )

    json.loads(tool_b.func(consulta="x"))  # leitura falha → não conta
    json.loads(tool_t.func(destinatario="1", mensagem="oi"))  # escrita falha → conta

    assert len(falhas) == 1
    assert "Telegram" in falhas[0]  # só a escrita derruba
    # ambos os erros CRUS são registrados para o diagnóstico (leitura + escrita).
    assert len(erros) == 2 and {e["irreversivel"] for e in erros} == {True, False}
