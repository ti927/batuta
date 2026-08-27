"""O vigia dos ELOS (`saude_elos`): sondas, transições com evento, auto-cura,
reconexão por botão e as rotas da página de status.

Nasceu do incidente de 2026-08-27 (rede até o pooler congelada por ~30 min sem
ninguém saber): cada ligação da corrente agora tem sonda ativa, e cada queda/volta
deixa rastro no banco de logs.
"""

import httpx
import pytest

import saude_elos
from saude_elos import Elo, EloDegradado


@pytest.fixture(autouse=True)
def _estado_limpo(monkeypatch):
    """Cada teste começa com o vigia zerado e sem escrever evento de verdade."""
    monkeypatch.setattr(saude_elos, "_estado", {})
    monkeypatch.setattr(saude_elos, "_proxima", {})


@pytest.fixture
def eventos(monkeypatch):
    capturados = []
    monkeypatch.setattr(
        saude_elos, "registrar_evento", lambda **k: capturados.append(k)
    )
    return capturados


def _elo(sonda, *, reconectar=None, auto_cura=False, id="teste"):
    return Elo(id, "Elo de teste", "interno", 30, sonda, reconectar, auto_cura)


def test_sonda_ok_vira_verde(eventos):
    elo = _elo(lambda: "tudo certo")
    saude_elos._aplicar_resultado(elo, saude_elos._sondar_um(elo))

    foto = saude_elos.foto()
    (registro,) = foto["elos"]
    assert registro["estado"] == "ok"
    assert registro["detalhe"] == "tudo certo"
    assert registro["latencia_ms"] >= 0 and registro["verificado_em"]
    assert foto["saudavel"] is True
    assert eventos == []  # primeira sonda não é transição — sem alarme falso


def test_falha_vira_caido_com_erro_traduzido():
    def sonda():
        raise httpx.ConnectError("connection refused")

    elo = _elo(sonda)
    saude_elos._aplicar_resultado(elo, saude_elos._sondar_um(elo))

    (registro,) = saude_elos.foto()["elos"]
    assert registro["estado"] == "caido"
    assert "não foi possível conectar" in registro["erro"]


def test_ressalva_vira_degradado():
    def sonda():
        raise EloDegradado("o Telegram está falhando ao entregar pra gente")

    elo = _elo(sonda)
    saude_elos._aplicar_resultado(elo, saude_elos._sondar_um(elo))

    (registro,) = saude_elos.foto()["elos"]
    assert registro["estado"] == "degradado"
    assert "falhando ao entregar" in registro["erro"]
    assert saude_elos.foto()["saudavel"] is False


def test_transicao_gera_evento_caiu_e_voltou(eventos):
    vivo = {"ok": True}

    def sonda():
        if not vivo["ok"]:
            raise RuntimeError("morreu")
        return None

    elo = _elo(sonda)
    saude_elos._aplicar_resultado(elo, saude_elos._sondar_um(elo))  # ok (sem evento)
    vivo["ok"] = False
    saude_elos._aplicar_resultado(elo, saude_elos._sondar_um(elo))  # ok → caido
    vivo["ok"] = True
    saude_elos._aplicar_resultado(elo, saude_elos._sondar_um(elo))  # caido → ok

    acoes = [e["acao"] for e in eventos]
    assert acoes == ["elo.caiu", "elo.voltou"]
    assert eventos[0]["nivel"] == "error" and eventos[0]["detalhe"]["elo"] == "teste"


def test_auto_cura_apos_falhas_seguidas(eventos):
    """2 falhas seguidas num elo com auto-cura → reconecta sozinho e re-sonda."""
    estado = {"vivo": False, "curas": 0}

    def sonda():
        if not estado["vivo"]:
            raise RuntimeError("pool congelado")
        return None

    def reconectar():
        estado["curas"] += 1
        estado["vivo"] = True

    elo = _elo(sonda, reconectar=reconectar, auto_cura=True)
    saude_elos._aplicar_resultado(elo, saude_elos._sondar_um(elo))  # falha 1: espera
    assert estado["curas"] == 0
    saude_elos._aplicar_resultado(elo, saude_elos._sondar_um(elo))  # falha 2: cura

    assert estado["curas"] == 1
    (registro,) = saude_elos.foto()["elos"]
    assert registro["estado"] == "ok"  # curou e a re-sonda confirmou
    assert any(
        e["acao"] == "elo.reconectado" and e["detalhe"]["curado"] for e in eventos
    )


def test_reconectar_por_botao(monkeypatch, eventos):
    estado = {"vivo": False}

    def sonda():
        if not estado["vivo"]:
            raise RuntimeError("fora")
        return None

    elo = _elo(sonda, reconectar=lambda: estado.update(vivo=True))
    monkeypatch.setattr(saude_elos, "montar_elos", lambda: [elo])

    resultado = saude_elos.reconectar_elo("teste")
    assert resultado["estado"] == "ok"
    with pytest.raises(KeyError):
        saude_elos.reconectar_elo("nao-existe")


def test_rota_exige_login(cliente):
    assert cliente.get("/saude/elos").status_code in (401, 403)


def test_rota_lista_elos(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.get("/saude/elos")
    assert r.status_code == 200
    corpo = r.json()
    assert {"agora", "elos", "caidos", "degradados", "saudavel"} <= set(corpo)


def test_reconectar_e_so_de_admin_da_consultoria(cliente, entrar, dados, monkeypatch):
    entrar(dados["admin"])  # admin de ORG, não da consultoria
    monkeypatch.setenv("CONSULTORIA_ADMINS", "outra-pessoa@x.com")
    assert cliente.post("/saude/elos/banco/reconectar").status_code == 403

    monkeypatch.setenv("CONSULTORIA_ADMINS", dados["admin"].email)
    assert cliente.post("/saude/elos/nao-existe/reconectar").status_code == 404
