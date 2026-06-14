"""Testes do inventário unificado de credenciais de instrumento e da rotação."""

import segredos_instrumento as si
from modelos import Instrumento


def _inst(sessao, dados, tipo, nome="x", configuracao=None):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome=nome, tipo=tipo, configuracao=configuracao or {}
    )
    sessao.add(inst)
    sessao.flush()
    return inst


def test_inventario_lista_credenciais_da_org(cliente, entrar, dados, sessao):
    tel = _inst(sessao, dados, "enviar_telegram", "bot")
    _inst(sessao, dados, "gerar_pdf", "pdf")  # sem segredo → não entra
    img = _inst(sessao, dados, "gerar_imagem", "img")
    si.salvar_segredos(sessao, tel.id, {"token_bot": "abc123456"})

    entrar(dados["admin"])
    r = cliente.get(f"/organizacoes/{dados['orgA'].id}/credenciais")
    assert r.status_code == 200
    corpo = r.json()
    tipos = {c["tipo"] for c in corpo}
    assert "gerar_pdf" not in tipos  # instrumento sem segredo fica fora
    assert {"enviar_telegram", "gerar_imagem"} <= tipos

    c_tel = next(c for c in corpo if c["instrumento_id"] == str(tel.id))
    campo = c_tel["campos"][0]
    assert campo["campo"] == "token_bot" and campo["definido"] is True
    assert campo["compartilhada"] is False

    c_img = next(c for c in corpo if c["instrumento_id"] == str(img.id))
    ci = c_img["campos"][0]
    # gerar_imagem reusa a chave OpenAI da org → marcado como compartilhado, sem
    # precisar de valor próprio.
    assert ci["compartilhada"] is True and ci["servico"] == "openai"
    assert ci["definido"] is False


def test_inventario_exige_admin(cliente, entrar, dados):
    entrar(dados["operador"])
    r = cliente.get(f"/organizacoes/{dados['orgA'].id}/credenciais")
    assert r.status_code == 403


def test_rotacionar_segredo_troca_e_mascara(cliente, entrar, dados, sessao):
    inst = _inst(sessao, dados, "enviar_telegram", "bot")
    entrar(dados["operador"])
    r = cliente.put(
        f"/instrumentos/{inst.id}/segredos", json={"segredos": {"token_bot": "tok998877"}}
    )
    assert r.status_code == 200
    # devolve o resumo mascarado (4 últimos), nunca o valor.
    assert r.json().get("token_bot") and "998877"[-4:] in r.json()["token_bot"]


def test_rotacionar_ignora_campo_desconhecido(cliente, entrar, dados, sessao):
    inst = _inst(sessao, dados, "enviar_telegram", "bot")
    entrar(dados["operador"])
    r = cliente.put(
        f"/instrumentos/{inst.id}/segredos",
        json={"segredos": {"campo_que_nao_existe": "x", "token_bot": "tok112233"}},
    )
    assert r.status_code == 200
    assert "campo_que_nao_existe" not in r.json()
    assert r.json().get("token_bot")
