"""Testes da contabilização de instrumentos com IA paga na BORDA (categoria
`instrumento`): o `gerar_imagem` é cobrado por imagem e o custo é apurado a partir
dos `instrumentos_acionados` que o motor devolve, sem tocar o núcleo."""

import medicao_instrumentos as mi
import precos
from modelos import Agente, AgenteInstrumento, Instrumento


def _agente_com_imagem(
    sessao, dados, modelo="gpt-image-1", tamanho="1024x1024", qualidade="medium"
):
    ag = Agente(time_id=dados["timeA"].id, nome="Artista", papel="agente")
    sessao.add(ag)
    sessao.flush()
    inst = Instrumento(
        time_id=dados["timeA"].id,
        nome="capa",
        tipo="gerar_imagem",
        configuracao={"modelo": modelo, "tamanho": tamanho, "qualidade": qualidade},
    )
    sessao.add(inst)
    sessao.flush()
    sessao.add(AgenteInstrumento(agente_id=ag.id, instrumento_id=inst.id))
    sessao.flush()
    return ag, inst


def test_conta_uma_entrada_por_imagem_gerada(sessao, dados):
    ag, inst = _agente_com_imagem(sessao, dados)
    # O nome da ferramenta acionada embute o id8 do instrumento (ver agente.py).
    nome = f"capa_{inst.id.hex[:8]}"
    entradas = mi.uso_de_instrumentos_pagos(sessao, ag.id, [nome, nome])  # 2 imagens
    assert len(entradas) == 2
    e = entradas[0]
    assert e["categoria"] == "instrumento"
    assert e["origem"] == "organizacao"  # chave do próprio instrumento, não a chave-mãe
    assert e["imagens"] == 1
    assert e["custo_usd"] == round(
        precos.custo_por_imagem("gpt-image-1", "1024x1024", "medium"), 6
    )


def test_ignora_ferramenta_nao_paga(sessao, dados):
    ag, _ = _agente_com_imagem(sessao, dados)
    # Outra ferramenta (id8 que não bate com nenhum instrumento pago) é ignorada.
    assert mi.uso_de_instrumentos_pagos(sessao, ag.id, ["busca_web_deadbeef"]) == []


def test_vazio_sem_acionados(sessao, dados):
    ag, _ = _agente_com_imagem(sessao, dados)
    assert mi.uso_de_instrumentos_pagos(sessao, ag.id, []) == []
    assert mi.uso_de_instrumentos_pagos(sessao, ag.id, None) == []


def test_respeita_qualidade_da_config(sessao, dados):
    # O preço da imagem varia sobretudo pela QUALIDADE (a maior alavanca de custo).
    ag, inst = _agente_com_imagem(sessao, dados, qualidade="high")
    nome = f"capa_{inst.id.hex[:8]}"
    entradas = mi.uso_de_instrumentos_pagos(sessao, ag.id, [nome])
    assert entradas[0]["custo_usd"] == round(
        precos.custo_por_imagem("gpt-image-1", "1024x1024", "high"), 6
    )
    assert precos.custo_por_imagem(
        "gpt-image-1", "", "high"
    ) > precos.custo_por_imagem("gpt-image-1", "", "medium")


def test_origem_segue_o_pool_quando_sem_chave_propria(sessao, dados):
    # Sem segredo próprio → reusa o pool; a origem é a do pool (ex.: consultoria).
    ag, inst = _agente_com_imagem(sessao, dados)
    nome = f"capa_{inst.id.hex[:8]}"
    entradas = mi.uso_de_instrumentos_pagos(
        sessao, ag.id, [nome], origens={"openai": "consultoria"}
    )
    assert entradas[0]["origem"] == "consultoria"


def test_origem_organizacao_quando_tem_chave_propria(sessao, dados):
    # Com segredo próprio → a chave é da organização, mesmo que o pool seja outro.
    import segredos_instrumento as si

    ag, inst = _agente_com_imagem(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"chave_api": "OWN"})
    nome = f"capa_{inst.id.hex[:8]}"
    entradas = mi.uso_de_instrumentos_pagos(
        sessao, ag.id, [nome], origens={"openai": "consultoria"}
    )
    assert entradas[0]["origem"] == "organizacao"
