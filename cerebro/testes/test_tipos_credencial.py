"""Testes do registro de tipos de credencial (Passo 2 da FASE Caixa-forte).

Confere que os tipos esperados existem com seus campos e — o mais importante —
que cada campo de uma credencial BATE com um campo real da Config de TODO
instrumento que declara aceitar aquele tipo. Esse casamento é o que faz a mescla
na borda (Passo 4) encontrar o campo; se um nome divergir, a credencial não
preencheria nada. Não toca no banco."""

import instrumentos as encaixe
import tipos_credencial as tc


def test_tipos_esperados_registrados():
    tipos = {t.tipo for t in tc.tipos_disponiveis()}
    assert {"wordpress", "sql", "telegram_bot", "token_bearer"} <= tipos


def test_wordpress_carrega_usuario_e_senha_juntos():
    wp = tc.obter_tipo("wordpress")
    assert wp is not None
    assert wp.nomes_campos == ("usuario", "senha_app")
    # usuario é identidade (visível); senha_app é segredo (mascarado).
    assert wp.campos_secretos == ("senha_app",)


def test_obter_tipo_desconhecido_devolve_none():
    assert tc.obter_tipo("inexistente") is None


def test_campos_da_credencial_existem_na_config_do_instrumento():
    """Para cada instrumento que aceita um tipo de credencial, todos os campos
    desse tipo precisam existir na Config do instrumento (mesmo nome) — senão a
    borda não saberia onde injetar o valor."""
    for inst in encaixe.tipos_disponiveis():
        aceitos = getattr(inst, "tipos_credencial_aceitos", ())
        campos_config = set(inst.Config.model_fields)
        for tipo_cred in aceitos:
            tcred = tc.obter_tipo(tipo_cred)
            assert tcred is not None, (
                f"{inst.tipo} aceita credencial '{tipo_cred}' não registrada"
            )
            # Só os campos INJETÁVEIS: os de exibição (titular/validade de um
            # certificado, derivados do segredo) não vão para instrumento nenhum.
            faltando = [c for c in tcred.nomes_injetaveis if c not in campos_config]
            assert not faltando, (
                f"{inst.tipo} aceita '{tipo_cred}', mas a Config não tem {faltando}"
            )


def test_instrumentos_de_pool_nao_aceitam_credencial_nomeada():
    """gerar_imagem/busca_web usam a CHAVE COMPARTILHADA (pool, balde 1), não
    credencial nomeada — não devem listar tipos aceitos."""
    for nome in ("gerar_imagem", "busca_web"):
        inst = encaixe.obter_tipo(nome)
        if inst is not None:
            assert getattr(inst, "tipos_credencial_aceitos", ()) == ()
