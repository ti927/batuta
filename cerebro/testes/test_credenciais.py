"""Testes do CRUD da caixa-forte de credenciais (Passo 5 da FASE Caixa-forte).

Cobre criar/listar/mascarar, nome duplicado, acesso por papel, edição que
preserva segredo em branco, trava de apagar-em-uso, a visibilidade do toggle
`compartilhavel` da consultoria e a validação de tipo ao referenciar no
instrumento."""

import uuid

import credenciais_cofre as cc
from modelos import Credencial, Instrumento


def _cred_consultoria(sessao, *, compartilhavel, nome):
    c = Credencial(organizacao_id=None, nome=nome, tipo="token_bearer",
                   compartilhavel=compartilhavel)
    cc.gravar(c, {"token_bearer": "tok-mae-9999"})
    sessao.add(c)
    sessao.flush()
    return c


def test_tipos_lista_os_esperados(cliente, entrar, dados):
    entrar(dados["operador"])
    r = cliente.get("/credenciais/tipos")
    assert r.status_code == 200
    tipos = {t["tipo"] for t in r.json()}
    assert {"wordpress", "sql", "telegram_bot", "token_bearer"} <= tipos


def test_criar_e_listar_credencial_da_org(cliente, entrar, dados):
    entrar(dados["operador"])
    org = dados["orgA"].id
    r = cliente.post(
        f"/organizacoes/{org}/credenciais",
        json={"nome": "WP Blog", "tipo": "wordpress",
              "dados": {"usuario": "editor", "senha_app": "segredo1234"}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["nome"] == "WP Blog" and body["usado_por"] == 0
    assert body["resumo"]["usuario"] == {"secreto": False, "valor": "editor"}
    assert body["resumo"]["senha_app"]["ultimos4"] == "1234"
    assert "segredo1234" not in r.text  # valor pleno nunca volta

    nomes = {c["nome"] for c in cliente.get(f"/organizacoes/{org}/credenciais").json()}
    assert "WP Blog" in nomes


def test_nome_duplicado_recusado(cliente, entrar, dados):
    entrar(dados["operador"])
    org = dados["orgA"].id
    p = {"nome": "Dup", "tipo": "token_bearer", "dados": {"token_bearer": "t1"}}
    assert cliente.post(f"/organizacoes/{org}/credenciais", json=p).status_code == 201
    assert cliente.post(f"/organizacoes/{org}/credenciais", json=p).status_code == 409


def test_observador_nao_cria(cliente, entrar, dados):
    entrar(dados["observador"])
    r = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/credenciais",
        json={"nome": "x", "tipo": "token_bearer", "dados": {"token_bearer": "t"}},
    )
    assert r.status_code == 403


def test_editar_preserva_segredo_em_branco(cliente, entrar, dados):
    entrar(dados["operador"])
    org = dados["orgA"].id
    cid = cliente.post(
        f"/organizacoes/{org}/credenciais",
        json={"nome": "WP", "tipo": "wordpress",
              "dados": {"usuario": "ed", "senha_app": "senhaAAAA"}},
    ).json()["id"]
    r = cliente.put(
        f"/credenciais/{cid}",
        json={"nome": "WP2", "dados": {"usuario": "ed2", "senha_app": ""}},
    )
    assert r.status_code == 200
    assert r.json()["nome"] == "WP2"
    assert r.json()["resumo"]["senha_app"]["ultimos4"] == "AAAA"  # preservado


def test_apagar_bloqueado_se_em_uso(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    org = dados["orgA"].id
    cid = cliente.post(
        f"/organizacoes/{org}/credenciais",
        json={"nome": "TG", "tipo": "telegram_bot", "dados": {"token_bot": "bot12345"}},
    ).json()["id"]
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="bot", tipo="enviar_telegram",
        configuracao={}, credencial_id=uuid.UUID(cid),
    )
    sessao.add(inst)
    sessao.flush()
    assert cliente.delete(f"/credenciais/{cid}").status_code == 409


def test_toggle_consultoria_controla_visibilidade_na_org(cliente, entrar, dados, sessao):
    _cred_consultoria(sessao, compartilhavel=True, nome="Mae Shared")
    _cred_consultoria(sessao, compartilhavel=False, nome="Mae Privada")
    entrar(dados["operador"])
    nomes = {
        c["nome"]
        for c in cliente.get(f"/organizacoes/{dados['orgA'].id}/credenciais").json()
    }
    assert "Mae Shared" in nomes
    assert "Mae Privada" not in nomes


def test_listar_consultoria_exige_admin_consultoria(cliente, entrar, dados):
    entrar(dados["admin"])  # admin da org, não da consultoria
    assert cliente.get("/credenciais-consultoria").status_code == 403


def test_instrumento_recusa_credencial_de_tipo_errado(cliente, entrar, dados):
    entrar(dados["operador"])
    org = dados["orgA"].id
    cid = cliente.post(
        f"/organizacoes/{org}/credenciais",
        json={"nome": "WPx", "tipo": "wordpress",
              "dados": {"usuario": "u", "senha_app": "s12345"}},
    ).json()["id"]
    r = cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={"nome": "bot", "tipo": "enviar_telegram", "configuracao": {},
              "credencial_id": cid},
    )
    assert r.status_code == 422  # telegram não aceita credencial wordpress


def test_instrumento_aceita_credencial_do_tipo_certo(cliente, entrar, dados):
    entrar(dados["operador"])
    org = dados["orgA"].id
    cid = cliente.post(
        f"/organizacoes/{org}/credenciais",
        json={"nome": "TGok", "tipo": "telegram_bot", "dados": {"token_bot": "b12345"}},
    ).json()["id"]
    r = cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={"nome": "bot", "tipo": "enviar_telegram", "configuracao": {},
              "credencial_id": cid},
    )
    assert r.status_code == 201, r.text
    assert r.json()["credencial_id"] == cid
