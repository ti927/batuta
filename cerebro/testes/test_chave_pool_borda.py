"""Testes da resolução na borda: o instrumento sem chave própria reusa a chave de IA
do pool, e o toggle `compartilhavel` decide o fallback da consultoria (`chaves.py`).

(A caixa-forte de credenciais nomeadas saiu em 2026-10-02; os testes dela saíram junto.)"""

import chaves as ch
import cofre
import segredos_instrumento as si
from modelos import ChaveApi, Instrumento
from orquestracao.llm import usar_chaves


def _instrumento(sessao, dados, tipo, *, configuracao=None):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="x", tipo=tipo,
        configuracao=configuracao or {},
    )
    sessao.add(inst)
    sessao.flush()
    return inst


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
