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
        "banco_sql",
        {"host": "db.x", "banco": "erp", "usuario": "u", "senha": "zzz9", "porta": 6543},
    )
    assert "senha" not in publica
    assert publica["host"] == "db.x" and publica["porta"] == 6543
    assert segredos == {"senha": "zzz9"}


def test_preparar_config_segredo_omitido_ou_vazio_nao_entra():
    _, s1 = encaixe.preparar_config("banco_sql", {"host": "x", "banco": "b", "usuario": "u"})
    _, s2 = encaixe.preparar_config(
        "banco_sql", {"host": "x", "banco": "b", "usuario": "u", "senha": "   "}
    )
    assert s1 == {} and s2 == {}


# ───────────────────────── Cofre: salvar/resumo/decifrar ─────────────────────


def _instrumento(sessao, dados, tipo="banco_sql"):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="i", tipo=tipo, configuracao={}
    )
    sessao.add(inst)
    sessao.flush()
    return inst


def test_salvar_cifra_resumo_e_decifra(sessao, dados):
    inst = _instrumento(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"senha": "minhasenha"})

    # No banco está cifrado, nunca em claro.
    reg = sessao.scalars(
        select(SegredoInstrumento).where(SegredoInstrumento.instrumento_id == inst.id)
    ).first()
    assert reg is not None and reg.valor_cifrado != "minhasenha"

    assert si.resumo(sessao, inst.id) == {"senha": "enha"}  # 4 últimos
    assert si.decifrar(sessao, inst.id) == {"senha": "minhasenha"}


def test_salvar_omitido_preserva_o_atual(sessao, dados):
    inst = _instrumento(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"senha": "primeira"})
    si.salvar_segredos(sessao, inst.id, {})  # nada informado
    assert si.decifrar(sessao, inst.id)["senha"] == "primeira"
    si.salvar_segredos(sessao, inst.id, {"senha": "segunda"})  # troca
    assert si.decifrar(sessao, inst.id)["senha"] == "segunda"


def test_anexar_decifra_em_atributo_transitorio(sessao, dados):
    inst = _instrumento(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"senha": "secreta99"})
    si.anexar_aos_instrumentos(sessao, [inst])
    assert inst.segredos_decifrados == {"senha": "secreta99"}


# ──────────────────────────── Rota: CRUD com segredo ─────────────────────────


def _criar_wp(cliente, dados, senha="abcd1234"):
    return cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={
            "nome": "WP",
            "tipo": "banco_sql",
            "configuracao": {"host": "db.x", "banco": "erp", "usuario": "u", "senha": senha},
        },
    )


def test_criar_separa_e_mascara_segredo(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    r = _criar_wp(cliente, dados)
    assert r.status_code == 201
    corpo = r.json()
    # o valor nunca volta; a config pública não tem o segredo; só ultimos4 em segredos
    assert "senha" not in (corpo["configuracao"] or {})
    assert corpo["segredos"]["senha"] == "1234"
    assert "abcd1234" not in json.dumps(corpo)


def test_editar_sem_reinformar_preserva_segredo(cliente, entrar, dados):
    entrar(dados["admin"])
    inst_id = _criar_wp(cliente, dados).json()["id"]
    # edita só o nome (sem senha) → segredo permanece
    r = cliente.put(
        f"/instrumentos/{inst_id}",
        json={"nome": "WP2", "configuracao": {"host": "db.x", "banco": "erp", "usuario": "u"}},
    )
    assert r.status_code == 200
    assert r.json()["segredos"]["senha"] == "1234"
    # reinforma com novo valor → troca (ultimos4 muda)
    r2 = cliente.put(
        f"/instrumentos/{inst_id}",
        json={"nome": "WP2", "configuracao": {
            "host": "db.x", "banco": "erp", "usuario": "u", "senha": "novo9876"}},
    )
    assert r2.json()["segredos"]["senha"] == "9876"
