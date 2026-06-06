"""Testes do cofre de segredos de instrumentos (Fase 7-B).

Cobrem a separação config-pública × segredo, a cifragem (valor nunca em claro
nem reexibido), o "preserva ao omitir" e a injeção decifrada na execução.
"""

import json
import uuid

from sqlalchemy import select

import instrumentos as encaixe
import segredos_instrumento as si
from modelos import Instrumento, SegredoInstrumento


# ───────────────────────── Encaixe: separar segredos ─────────────────────────


def test_preparar_config_separa_segredo():
    publica, segredos = encaixe.preparar_config(
        "publicar_wordpress",
        {"site_url": "https://x.com", "senha_app": "zzz9", "status": "publish"},
    )
    assert "senha_app" not in publica
    assert publica["site_url"] == "https://x.com" and publica["status"] == "publish"
    assert segredos == {"senha_app": "zzz9"}


def test_preparar_config_segredo_omitido_ou_vazio_nao_entra():
    _, s1 = encaixe.preparar_config("publicar_wordpress", {"site_url": "https://x"})
    _, s2 = encaixe.preparar_config("publicar_wordpress", {"senha_app": "   "})
    assert s1 == {} and s2 == {}


# ───────────────────────── Cofre: salvar/resumo/decifrar ─────────────────────


def _instrumento(sessao, dados, tipo="publicar_wordpress"):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="i", tipo=tipo, configuracao={}
    )
    sessao.add(inst)
    sessao.flush()
    return inst


def test_salvar_cifra_resumo_e_decifra(sessao, dados):
    inst = _instrumento(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"senha_app": "minhasenha"})

    # No banco está cifrado, nunca em claro.
    reg = sessao.scalars(
        select(SegredoInstrumento).where(SegredoInstrumento.instrumento_id == inst.id)
    ).first()
    assert reg is not None and reg.valor_cifrado != "minhasenha"

    assert si.resumo(sessao, inst.id) == {"senha_app": "enha"}  # 4 últimos
    assert si.decifrar(sessao, inst.id) == {"senha_app": "minhasenha"}


def test_salvar_omitido_preserva_o_atual(sessao, dados):
    inst = _instrumento(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"senha_app": "primeira"})
    si.salvar_segredos(sessao, inst.id, {})  # nada informado
    assert si.decifrar(sessao, inst.id)["senha_app"] == "primeira"
    si.salvar_segredos(sessao, inst.id, {"senha_app": "segunda"})  # troca
    assert si.decifrar(sessao, inst.id)["senha_app"] == "segunda"


def test_anexar_decifra_em_atributo_transitorio(sessao, dados):
    inst = _instrumento(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"senha_app": "secreta99"})
    si.anexar_aos_instrumentos(sessao, [inst])
    assert inst.segredos_decifrados == {"senha_app": "secreta99"}


# ──────────────────────────── Rota: CRUD com segredo ─────────────────────────


def _criar_wp(cliente, dados, senha="abcd1234"):
    return cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={
            "nome": "WP",
            "tipo": "publicar_wordpress",
            "configuracao": {"site_url": "https://x.com", "usuario": "u", "senha_app": senha},
        },
    )


def test_criar_separa_e_mascara_segredo(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    r = _criar_wp(cliente, dados)
    assert r.status_code == 201
    corpo = r.json()
    # o valor nunca volta; a config pública não tem o segredo; só ultimos4 em segredos
    assert "senha_app" not in (corpo["configuracao"] or {})
    assert corpo["segredos"]["senha_app"] == "1234"
    assert "abcd1234" not in json.dumps(corpo)


def test_editar_sem_reinformar_preserva_segredo(cliente, entrar, dados):
    entrar(dados["admin"])
    inst_id = _criar_wp(cliente, dados).json()["id"]
    # edita só o nome (sem senha_app) → segredo permanece
    r = cliente.put(
        f"/instrumentos/{inst_id}",
        json={"nome": "WP2", "configuracao": {"site_url": "https://x.com"}},
    )
    assert r.status_code == 200
    assert r.json()["segredos"]["senha_app"] == "1234"
    # reinforma com novo valor → troca (ultimos4 muda)
    r2 = cliente.put(
        f"/instrumentos/{inst_id}",
        json={"nome": "WP2", "configuracao": {"senha_app": "novo9876"}},
    )
    assert r2.json()["segredos"]["senha_app"] == "9876"
