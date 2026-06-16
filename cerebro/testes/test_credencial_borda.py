"""Testes da resolução na borda (Passo 4 da FASE Caixa-forte).

Um instrumento que referencia uma credencial nomeada recebe os campos dela
mesclados em `segredos_decifrados`, com a prioridade inline próprio > credencial
central > pool de serviço. Também cobre o toggle `compartilhavel` no fallback da
consultoria (`chaves.py`). Núcleo intocado — tudo na borda."""

import chaves as ch
import cofre
import credenciais_cofre as cc
import segredos_instrumento as si
from modelos import ChaveApi, Credencial, Instrumento
from orquestracao.llm import usar_chaves


def _credencial(sessao, org_id, tipo, dados):
    cred = Credencial(organizacao_id=org_id, nome="cred", tipo=tipo)
    cc.gravar(cred, dados)
    sessao.add(cred)
    sessao.flush()
    return cred


def _instrumento(sessao, dados, tipo, *, credencial_id=None, configuracao=None):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="x", tipo=tipo,
        configuracao=configuracao or {}, credencial_id=credencial_id,
    )
    sessao.add(inst)
    sessao.flush()
    return inst


# ───────────────────────── credencial → borda ─────────────────────────


def test_instrumento_recebe_o_saco_da_credencial(sessao, dados):
    cred = _credencial(
        sessao, dados["orgA"].id, "wordpress",
        {"usuario": "editor", "senha_app": "segredo123"},
    )
    inst = _instrumento(sessao, dados, "publicar_wordpress", credencial_id=cred.id)
    si.anexar_aos_instrumentos(sessao, [inst])
    assert inst.segredos_decifrados == {"usuario": "editor", "senha_app": "segredo123"}


def test_inline_proprio_vence_a_credencial(sessao, dados):
    cred = _credencial(
        sessao, dados["orgA"].id, "wordpress",
        {"usuario": "central", "senha_app": "senha-central"},
    )
    inst = _instrumento(sessao, dados, "publicar_wordpress", credencial_id=cred.id)
    si.salvar_segredos(sessao, inst.id, {"senha_app": "senha-propria"})
    si.anexar_aos_instrumentos(sessao, [inst])
    # A senha inline própria vence; o usuário (só na credencial) é preenchido por ela.
    assert inst.segredos_decifrados["senha_app"] == "senha-propria"
    assert inst.segredos_decifrados["usuario"] == "central"


def test_sem_credencial_pool_segue_funcionando(sessao, dados):
    inst = _instrumento(sessao, dados, "gerar_imagem", configuracao={"modelo": "dall-e-3"})
    with usar_chaves({"openai": "POOL-KEY"}):
        si.anexar_aos_instrumentos(sessao, [inst])
    assert inst.segredos_decifrados.get("chave_api") == "POOL-KEY"


# ─────────────── toggle compartilhavel no fallback (chaves.py) ───────────────


def test_chave_consultoria_nao_compartilhavel_nao_cai_no_fallback(sessao, dados):
    sessao.add(
        ChaveApi(
            organizacao_id=None, provedor="openai",
            valor_cifrado=cofre.cifrar("MAE-KEY"), ultimos4="-KEY",
            ativa=True, compartilhavel=False,
        )
    )
    sessao.flush()
    # A organização não tem chave própria → sem fallback (consultoria é privada).
    assert ch.resolver_chave(sessao, dados["orgA"].id, provedor="openai") is None


def test_chave_consultoria_compartilhavel_cai_no_fallback(sessao, dados):
    sessao.add(
        ChaveApi(
            organizacao_id=None, provedor="openai",
            valor_cifrado=cofre.cifrar("MAE-KEY"), ultimos4="-KEY",
            ativa=True, compartilhavel=True,
        )
    )
    sessao.flush()
    assert ch.resolver_chave(sessao, dados["orgA"].id, provedor="openai") == "MAE-KEY"
