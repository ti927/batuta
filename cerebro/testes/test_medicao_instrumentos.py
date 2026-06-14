"""Testes da contabilização de instrumentos com IA paga na BORDA (categoria
`instrumento`): o `gerar_imagem` é cobrado por imagem e o custo é apurado a partir
dos `instrumentos_acionados` que o motor devolve, sem tocar o núcleo."""

import medicao_instrumentos as mi
import precos
from modelos import Agente, AgenteInstrumento, Instrumento


def _agente_com_imagem(sessao, dados, modelo="dall-e-3", tamanho="1024x1024"):
    ag = Agente(time_id=dados["timeA"].id, nome="Artista", papel="agente")
    sessao.add(ag)
    sessao.flush()
    inst = Instrumento(
        time_id=dados["timeA"].id,
        nome="capa",
        tipo="gerar_imagem",
        configuracao={"modelo": modelo, "tamanho": tamanho},
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
    assert e["custo_usd"] == round(precos.custo_por_imagem("dall-e-3", "1024x1024"), 6)


def test_ignora_ferramenta_nao_paga(sessao, dados):
    ag, _ = _agente_com_imagem(sessao, dados)
    # Outra ferramenta (id8 que não bate com nenhum instrumento pago) é ignorada.
    assert mi.uso_de_instrumentos_pagos(sessao, ag.id, ["busca_web_deadbeef"]) == []


def test_vazio_sem_acionados(sessao, dados):
    ag, _ = _agente_com_imagem(sessao, dados)
    assert mi.uso_de_instrumentos_pagos(sessao, ag.id, []) == []
    assert mi.uso_de_instrumentos_pagos(sessao, ag.id, None) == []


def test_respeita_tamanho_da_config(sessao, dados):
    ag, inst = _agente_com_imagem(sessao, dados, tamanho="1792x1024")
    nome = f"capa_{inst.id.hex[:8]}"
    entradas = mi.uso_de_instrumentos_pagos(sessao, ag.id, [nome])
    assert entradas[0]["custo_usd"] == round(
        precos.custo_por_imagem("dall-e-3", "1792x1024"), 6
    )
