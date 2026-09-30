"""A aba Instrumentos (2026-09-30): a lista separa PERSONALIZADOS de PRONTOS, cada
cartão mostra quem usa, quantas ações, a situação e selos — e o ícone do serviço é
buscado pelo cérebro (MCP anuncia; API → site do serviço), sem a tela buscar nada fora.
"""

import base64

import pytest

import icone_servico as ic
import segredos_instrumento as si
from instrumentos.mcp_conexao import _servidor
from modelos import Agente, AgenteInstrumento, Instrumento, Time


def _inst(sessao, time, nome, tipo, cfg=None, **extra):
    i = Instrumento(time_id=time.id, nome=nome, tipo=tipo, configuracao=cfg or {}, **extra)
    sessao.add(i)
    sessao.flush()
    return i


@pytest.fixture
def lista(cliente, entrar, sessao, dados):
    time = dados["timeA"]
    outro = Time(organizacao_id=time.organizacao_id, nome="Outro time")
    sessao.add(outro)
    sessao.flush()
    conector = _inst(sessao, time, "Zernio", "conector", {
        "auth_tipo": "bearer",
        "operacoes": [{"nome": "a", "url": "https://api.zernio.com/v1/x", "custo_por_chamada_usd": 0.01},
                      {"nome": "b", "url": "https://api.zernio.com/v1/y"}]})
    mcp = _inst(sessao, outro, "Servidor", "conectar_mcp", {
        "auth_modo": "bearer", "ferramentas": [{"nome": "x", "usar": True}, {"nome": "y", "usar": False}]},
        escopo="organizacao", conexao={"estado": "falhou", "mensagem": "Recusou a chave."})
    si.salvar_segredos(sessao, mcp.id, {"url": "https://mcp.x/abc", "token_bearer": "t"})
    pronto = _inst(sessao, time, "Imagem", "gerar_imagem", {"provedor": "openai"})
    ag = Agente(time_id=time.id, nome="Publicador", papel="agente")
    ag2 = Agente(time_id=outro.id, nome="De fora", papel="agente")
    sessao.add_all([ag, ag2])
    sessao.flush()
    sessao.add_all([AgenteInstrumento(agente_id=ag.id, instrumento_id=conector.id),
                    AgenteInstrumento(agente_id=ag2.id, instrumento_id=mcp.id)])
    sessao.flush()
    entrar(dados["operador"])
    r = cliente.get(f"/times/{time.id}/instrumentos")
    assert r.status_code == 200
    return {i["nome"]: i for i in r.json()}


def test_personalizado_x_pronto_e_ligacao(lista):
    assert lista["Zernio"]["personalizado"] and lista["Zernio"]["ligacao"] == "api"
    assert lista["Servidor"]["personalizado"] and lista["Servidor"]["ligacao"] == "mcp"
    assert lista["Imagem"]["personalizado"] is False and lista["Imagem"]["ligacao"] is None


def test_acoes_uso_e_casa(lista):
    assert lista["Zernio"]["qtd_acoes"] == 2
    assert lista["Servidor"]["qtd_acoes"] == 1  # só as ferramentas escolhidas
    assert lista["Zernio"]["usado_por_agentes"] == ["Publicador"]
    assert lista["Servidor"]["usado_por_agentes"] == [] and lista["Servidor"]["usado_em_outros_times"] == 1
    assert lista["Servidor"]["time_casa_nome"] == "Outro time"
    assert lista["Zernio"]["time_casa_nome"] is None


def test_situacao_e_pago(lista):
    assert lista["Zernio"]["situacao"] == "falta_chave"  # bearer sem token guardado
    assert lista["Zernio"]["situacao_motivo"] == "Falta preencher a chave."
    assert lista["Servidor"]["situacao"] == "falhou"
    assert lista["Servidor"]["situacao_motivo"] == "Recusou a chave."
    assert lista["Zernio"]["pago"] is True  # operação com custo
    assert lista["Imagem"]["pago"] is True  # tipo pago


def test_lista_pede_o_icone_dos_personalizados_sem_icone(lista, _sem_busca_de_icone):
    # 2 personalizados sem ícone e nunca buscados → 2 buscas em segundo plano
    assert len(_sem_busca_de_icone) == 2


# ───────────────────────────── ícone do serviço ─────────────────────────────

def test_site_do_servico():
    assert ic.site_do_servico("https://api.zernio.com/v1/posts") == "https://zernio.com"
    assert ic.site_do_servico("https://mcp.zapier.com/api/x") == "https://zapier.com"
    assert ic.site_do_servico("https://lureconsultoria.com.br/wp-json") == "https://lureconsultoria.com.br"


@pytest.mark.parametrize("url", [
    "http://zernio.com", "https://localhost/x", "https://cerebro.railway.internal/",
    "https://127.0.0.1/", "https://10.0.0.5/", "https://[::1]/",
])
def test_so_endereco_publico_com_https(url):
    assert ic.endereco_publico(url) is False


def test_icone_do_site_escolhe_o_link_e_vira_data(monkeypatch):
    png = b"\x89PNG\r\n\x1a\nfake"
    pagina = (b'<html><head><link rel="icon" sizes="16x16" href="/p.png">'
              b'<link rel="apple-touch-icon" sizes="180x180" href="/grande.png"></head></html>')
    pedidos = []

    def _baixar(url, limite):
        pedidos.append(url)
        if url == "https://zernio.com":
            return pagina, "text/html"
        if url == "https://zernio.com/grande.png":
            return png, "image/png"
        return None

    monkeypatch.setattr(ic, "_baixar", _baixar)
    icone = ic.icone_do_site("https://zernio.com")
    assert icone == "data:image/png;base64," + base64.b64encode(png).decode()
    assert pedidos[1] == "https://zernio.com/grande.png"  # 180 px antes de 16 px


def test_svg_com_script_nao_entra():
    assert ic._como_data(b"<svg><script>x</script></svg>", "image/svg+xml", "a.svg") is None
    assert ic._como_data(b"<html>", "text/html", "a.html") is None


def test_mcp_usa_o_icone_que_o_servidor_anuncia(monkeypatch):
    monkeypatch.setattr(ic, "icone_do_site", lambda s: pytest.fail("não devia ir ao site"))
    dado = "data:image/png;base64,AAAA"
    assert ic.icone_do_instrumento("conectar_mcp", {}, {"servidor": {"icones": [dado]}}) == dado


def test_mcp_sem_icone_cai_para_o_site(monkeypatch):
    monkeypatch.setattr(ic, "icone_do_site", lambda s: f"site:{s}")
    assert ic.icone_do_instrumento(
        "conectar_mcp", {}, {"servidor": {"site": "https://zernio.com"}}
    ) == "site:https://zernio.com"
    assert ic.icone_do_instrumento(
        "conectar_mcp", {}, {}, "https://mcp.zernio.com/mcp"
    ) == "site:https://zernio.com"


def test_servidor_guarda_titulo_site_e_icones():
    class _Icone:
        def __init__(self, src):
            self.src = src

    class _Info:
        name, version, title = "zernio", "1.0", "Zernio"
        websiteUrl = "https://zernio.com"
        icons = [_Icone("https://zernio.com/i.png"), _Icone("data:image/png;base64," + "A" * 70_000)]

    s = _servidor(_Info())
    assert s["titulo"] == "Zernio" and s["site"] == "https://zernio.com"
    assert s["icones"] == ["https://zernio.com/i.png"]  # o data: enorme fica de fora
