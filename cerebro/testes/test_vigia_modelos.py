"""Vigia dos modelos de IA em uso (2026-10-02): pergunta a cada empresa de IA a lista
de modelos dela e acusa o que o Batuta usa e não existe mais. As listas das empresas
são simuladas aqui — o vigia de verdade faz a consulta gratuita de cada uma."""

import pytest

import vigia_modelos as vm
from modelos import Agente


def _listas(monkeypatch, **por_provedor):
    for provedor, ids in por_provedor.items():
        monkeypatch.setitem(vm.LISTAR, provedor, lambda chave, cli, ids=ids: set(ids))


def test_modelos_em_uso_junta_agentes_conversa_instrumentos_e_fixos(sessao, dados):
    sessao.add(Agente(time_id=dados["timeA"].id, nome="Redator", papel="agente",
                      modelo_ia="gpt-4o-mini"))
    sessao.flush()
    uso = vm.modelos_em_uso(sessao)
    assert any("agente Redator" in q for q in uso["gpt-4o-mini"])
    assert "roteamento das automações" in uso["claude-haiku-4-5"]
    assert "transcrição dos áudios do Telegram" in uso["whisper-1"]
    assert any(q.startswith("IA de conversa de") for q in uso["claude-sonnet-5"])


def test_modelo_que_sumiu_derruba_o_elo_e_diz_quem_usa(monkeypatch):
    _listas(monkeypatch, openai={"gpt-4o", "gpt-5.6-luna"})
    uso = {"gpt-4o-mini": ["agente Redator (Blog)"], "gpt-4o": ["agente Revisor (Blog)"]}
    sumidos, _ = vm.conferir(uso, {"openai": "sk"}, cli=None)
    assert sumidos == [
        "gpt-4o-mini não existe mais na OpenAI — usado por agente Redator (Blog)"
    ]


def test_apelido_e_versao_datada_contam_como_existente(monkeypatch):
    # A Anthropic lista a versão datada; o Batuta chama pelo apelido.
    _listas(monkeypatch, anthropic={"claude-haiku-4-5-20251001", "claude-sonnet-5-5"})
    uso = {"claude-haiku-4-5": ["roteamento"], "claude-sonnet-5-5": ["agente X"]}
    sumidos, _ = vm.conferir(uso, {"anthropic": "k"}, cli=None)
    assert sumidos == []


def test_provedor_sem_chave_nao_e_conferido(monkeypatch):
    _listas(monkeypatch, google=set())
    sumidos, _ = vm.conferir({"gemini-3.8-flash": ["agente Y"]}, {}, cli=None)
    assert sumidos == []


def test_modelo_que_sai_em_breve_vira_aviso(monkeypatch):
    _listas(monkeypatch, openai={"gpt-image-1"})
    _, saindo = vm.conferir({"gpt-image-1": ["instrumento Arte (Blog)"]}, {"openai": "k"}, cli=None)
    assert len(saindo) == 1 and "gpt-image-1" in saindo[0] and "Arte" in saindo[0]


def test_sonda_cai_registra_evento_e_degrada(monkeypatch):
    import saude_elos

    eventos = []
    monkeypatch.setattr(vm, "registrar_evento", lambda **k: eventos.append(k))
    monkeypatch.setattr(vm, "modelos_em_uso", lambda s: {"gpt-4o-mini": ["agente R"]})
    monkeypatch.setattr("chaves.resolver_chaves_por_organizacao", lambda s, o: ({"openai": "k"}, {}))
    _listas(monkeypatch, openai=set())
    with pytest.raises(vm.ModeloSumiu, match="gpt-4o-mini não existe mais"):
        vm.sonda()
    assert eventos and eventos[0]["acao"] == "modelo.desligado"

    monkeypatch.setattr(vm, "modelos_em_uso", lambda s: {"gpt-image-1": ["instrumento A"]})
    _listas(monkeypatch, openai={"gpt-image-1"})
    with pytest.raises(saude_elos.EloDegradado, match="23/10/2026"):
        vm.sonda()


def test_muitos_usuarios_viram_e_mais_n():
    assert vm._quem(["a", "b", "c", "d", "e"]) == "a, b, c e mais 2"


def test_desligado_no_registro_derruba_mesmo_se_a_empresa_ainda_lista(monkeypatch):
    # Caso real: a OpenAI seguiu listando o sora-2 depois de desligá-lo (24/09/2026).
    _listas(monkeypatch, openai={"sora-2"})
    sumidos, saindo = vm.conferir({"sora-2": ["instrumento Vídeo (Blog)"]}, {"openai": "k"}, cli=None)
    assert len(sumidos) == 1 and "desligou o modelo sora-2" in sumidos[0] and saindo == []
