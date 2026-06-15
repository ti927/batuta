"""Testes do cofre da caixa-forte de credenciais (Passo 3 da FASE Caixa-forte).

Cobre o ciclo cifra→decifra do saco, o resumo mascarado (identidade visível,
segredo só últimos 4), a preservação de campo em branco na edição e a contagem
`usado_por`."""

import credenciais_cofre as cc
from modelos import Credencial, Instrumento


def _credencial(org_id, tipo="wordpress"):
    return Credencial(organizacao_id=org_id, nome="WP Blog", tipo=tipo)


def test_grava_e_decifra_o_saco_inteiro():
    cred = _credencial(None)
    cc.gravar(cred, {"usuario": "editor", "senha_app": "abcd 1234 zzz9"})
    assert cc.decifrar(cred) == {"usuario": "editor", "senha_app": "abcd 1234 zzz9"}
    # O blob cifrado não revela o segredo em claro.
    assert "zzz9" not in cred.dados_cifrado


def test_resumo_mascara_segredo_e_mostra_identidade():
    cred = _credencial(None)
    cc.gravar(cred, {"usuario": "editor", "senha_app": "supersenha9"})
    assert cred.resumo["usuario"] == {"secreto": False, "valor": "editor"}
    assert cred.resumo["senha_app"] == {"secreto": True, "ultimos4": "nha9"}


def test_campo_em_branco_preserva_o_valor_atual():
    cred = _credencial(None)
    cc.gravar(cred, {"usuario": "editor", "senha_app": "senha-antiga"})
    # Edição trocando só o usuário; senha em branco deve ser preservada.
    cc.gravar(cred, {"usuario": "novo-editor", "senha_app": ""})
    assert cc.decifrar(cred) == {"usuario": "novo-editor", "senha_app": "senha-antiga"}


def test_descarta_campos_fora_do_tipo():
    cred = _credencial(None)
    cc.gravar(cred, {"usuario": "u", "senha_app": "s", "intruso": "x"})
    assert "intruso" not in cc.decifrar(cred)


def test_usado_por_conta_instrumentos_que_apontam(sessao, dados):
    cred = _credencial(dados["orgA"].id)
    cc.gravar(cred, {"usuario": "u", "senha_app": "s"})
    sessao.add(cred)
    sessao.flush()
    assert cc.usado_por(sessao, cred.id) == 0
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="pub", tipo="publicar_wordpress",
        configuracao={}, credencial_id=cred.id,
    )
    sessao.add(inst)
    sessao.flush()
    assert cc.usado_por(sessao, cred.id) == 1
