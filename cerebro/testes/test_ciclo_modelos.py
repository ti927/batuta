"""Ciclo de vida dos modelos de IA (2026-10-02).

A OpenAI desligou o vídeo (Sora) em 24/09/2026 e o Batuta só soube por acaso. Estes
testes são a primeira trava: todo modelo que o Batuta oferece precisa estar no
registro (com a data de saída), e nenhum modelo PADRÃO pode estar perto de sair —
quando a data se aproximar, a suíte falha e obriga a trocar ANTES do cliente ver.
"""

from datetime import date

import pytest

from instrumentos import (
    descrever_imagem,
    gerar_arquivo,
    gerar_imagem,
    gerar_video,
    ler_documento,
    ler_pagina,
    montar_imagem,
    pesquisar_web,
)
from mensageria import transcricao
from orquestracao import ciclo_modelos as cm
from orquestracao import llm
from orquestracao.modelos_ia import MODELOS_POR_PROVEDOR, provedor_do_modelo


def test_todo_modelo_oferecido_esta_no_registro():
    oferecidos = {
        cm.TEXTO: [m for ms in MODELOS_POR_PROVEDOR.values() for m in ms]
        + descrever_imagem.MODELOS_VISAO,
        cm.IMAGEM: list(gerar_imagem.CATALOGO_IMAGEM),
        cm.VIDEO: list(gerar_video.CATALOGO_VIDEO),
        cm.TRANSCRICAO: [transcricao.MODELO],
    }
    for uso, ids in oferecidos.items():
        for modelo in ids:
            registro = cm.obter(modelo)
            assert registro is not None, f"{modelo} não está em ciclo_modelos.REGISTRO"
            assert registro.uso == uso, modelo


def test_nada_desligado_aparece_para_escolher():
    for ms in MODELOS_POR_PROVEDOR.values():
        for modelo in ms:
            assert cm.obter(modelo).situacao != cm.DESLIGADO, modelo
    for modelo in gerar_imagem.CATALOGO_IMAGEM:
        assert cm.obter(modelo).situacao == cm.ATIVO, modelo


@pytest.mark.parametrize(
    "onde, modelo",
    [
        ("padrão dos agentes e do roteamento (llm.MODELO_PADRAO)", llm.MODELO_PADRAO),
        ("padrão do Gerar imagem", gerar_imagem.MODELO_PADRAO),
        ("padrão do Montar imagem", montar_imagem.ConfigMontagem().modelo),
        ("padrão do Ler imagem", descrever_imagem.ConfigDescrever().modelo),
        ("padrão do Pesquisar na web", pesquisar_web.ConfigPesquisa().modelo),
        ("padrão do Ler página", ler_pagina.ConfigLeitura().modelo),
        ("padrão do Ler documento", ler_documento.ConfigDocumento().modelo),
        ("padrão do Gerar arquivo", gerar_arquivo.ConfigArquivo().modelo),
        ("transcrição dos áudios do Telegram", transcricao.MODELO),
    ],
)
def test_nenhum_padrao_esta_perto_de_sair(onde, modelo):
    """Se este teste falhar, a empresa da IA vai tirar do ar um modelo que o Batuta
    usa por padrão: troque o padrão (e veja o `substituto` no registro)."""
    registro = cm.obter(modelo)
    assert registro is not None, f"{onde}: {modelo} não está no registro"
    assert registro.situacao != cm.DESLIGADO, f"{onde}: {modelo} já foi desligado"
    dias = cm.dias_para_sair(modelo)
    assert dias is None or dias > cm.JANELA_ALERTA_DIAS, (
        f"{onde}: {modelo} sai em {registro.sai_em:%d/%m/%Y} ({dias} dias). "
        f"Troque para {registro.substituto or 'outro modelo'}."
    )


def test_imagem_que_sai_se_auto_cura():
    """Todo modelo de imagem descontinuado/desligado precisa estar na auto-cura do
    Gerar imagem, senão um instrumento antigo quebra no dia em que ele sair."""
    for m in cm.REGISTRO:
        if m.uso == cm.IMAGEM and m.situacao != cm.ATIVO:
            assert m.id in gerar_imagem.MODELOS_LEGADOS, m.id


def test_modelo_desligado_ainda_resolve_o_provedor():
    # Um agente antigo com Gemini 1.5 precisa falhar com o recado certo, não com
    # "provedor desconhecido".
    assert provedor_do_modelo("gemini-1.5-pro") == "google"
    assert provedor_do_modelo("claude-haiku-4-5-20251001") == "anthropic"


def test_alerta_fala_portugues_de_gente():
    hoje = date(2026, 10, 2)
    assert cm.alerta("gpt-image-1", hoje) == (
        "A OpenAI desliga o modelo gpt-image-1 em 23/10/2026. Troque para gpt-image-2."
    )
    assert cm.alerta("sora-2", hoje) == "A OpenAI desligou o modelo sora-2 em 24/09/2026."
    # longe da janela de alerta: nada a dizer ainda
    assert cm.alerta("whisper-1", hoje) is None
    assert cm.alerta("whisper-1", date(2027, 1, 10)) is not None
    # ativo ou desconhecido: nada a dizer
    assert cm.alerta("claude-sonnet-5-5", hoje) is None
    assert cm.alerta("modelo-que-nao-existe", hoje) is None


def test_apelido_acha_o_mesmo_modelo():
    assert cm.obter("claude-haiku-4-5-20251001") is cm.obter("claude-haiku-4-5")


def test_rota_de_modelos_entrega_o_registro_com_aviso_e_custo(cliente, entrar, dados):
    entrar(dados["observador"])
    r = cliente.get("/modelos")
    assert r.status_code == 200
    por_id = {m["id"]: m for m in r.json()}
    assert por_id["sora-2"]["situacao"] == cm.DESLIGADO
    assert por_id["sora-2"]["alerta"].startswith("A OpenAI desligou")
    assert por_id["claude-sonnet-5-5"]["custo_mtok"] == [2.0, 10.0]
    assert por_id["gpt-image-2"]["custo_mtok"] is None  # imagem não é por token
    assert por_id["gemini-3.8-flash"]["custo_mtok"] == [0.75, 3.75]


# ── Erro honesto quando a empresa da IA desliga o modelo ─────────────────────────


@pytest.mark.parametrize(
    "erro, modelo, esperado",
    [
        ("Error code: 404 - {'error': {'type': 'not_found_error', 'message': 'model: claude-x'}}",
         "claude-x", "A Anthropic não reconhece mais o modelo claude-x"),
        ("Error code: 404 - {'error': {'message': 'The model `gpt-4o-mini` does not exist', "
         "'code': 'model_not_found'}}", "gpt-4o-mini", "A OpenAI não reconhece mais"),
        ("404 models/gemini-1.5-pro is not found for API version v1beta",
         "gemini-1.5-pro", "Sugestão: gemini-3.8-flash"),
    ],
)
def test_modelo_desligado_vira_recado_honesto(erro, modelo, esperado):
    assert esperado in llm.modelo_indisponivel(erro, modelo)


@pytest.mark.parametrize(
    "erro", ["Error code: 429 - rate limit exceeded", "404 file not found", "Connection reset"]
)
def test_outro_erro_nao_vira_troque_o_modelo(erro):
    assert llm.modelo_indisponivel(erro, "gpt-4o") is None


def test_agente_com_modelo_desligado_falha_claro_e_sem_retentar(monkeypatch):
    import uuid

    import orquestracao.agente as agente_mod
    from instrumentos.base import FalhaInstrumento
    from modelos import Agente

    class App:
        def invoke(self, _entrada, _config=None):
            raise RuntimeError(
                "Error code: 404 - {'error': {'message': 'The model `gpt-4o-mini` does "
                "not exist', 'code': 'model_not_found'}}"
            )

    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m, **k: object())
    monkeypatch.setattr(agente_mod, "create_agent", lambda *a, **k: App())
    ag = Agente(time_id=uuid.uuid4(), nome="Redator", papel="agente", modelo_ia="gpt-4o-mini")
    ag.id = uuid.uuid4()
    with pytest.raises(FalhaInstrumento) as e:
        agente_mod.executar_agente(ag, [], "escreva")
    assert "A OpenAI não reconhece mais o modelo gpt-4o-mini" in str(e.value)
    assert "Troque o modelo de IA do agente 'Redator'" in str(e.value)
    assert e.value.retentavel is False and e.value.codigo == "ia.modelo_desligado"
