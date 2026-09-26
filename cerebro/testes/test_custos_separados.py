"""Custo separado entre a IA DOS AGENTES e os INSTRUMENTOS (2026-09-26).

Um agente que pensa com o Claude e gera imagem com a OpenAI tem dois custos. O banco
já os guardava em categorias diferentes, mas o resumo do time mostrava um número só,
o registro não dizia QUAL instrumento gastou, e três instrumentos pagos (Exa,
Firecrawl e conector que chama API paga) não eram medidos."""

import medicao_instrumentos as mi
import precos
from custos_time import custos_do_time
from modelos import Agente, AgenteInstrumento, Automacao, Execucao, Instrumento, PassoExecucao


def _agente(sessao, dados, nome="Redator"):
    ag = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
    sessao.add(ag)
    sessao.flush()
    return ag


def _no_cinto(sessao, dados, ag, nome, tipo, configuracao):
    inst = Instrumento(time_id=dados["timeA"].id, nome=nome, tipo=tipo,
                       configuracao=configuracao)
    sessao.add(inst)
    sessao.flush()
    sessao.add(AgenteInstrumento(agente_id=ag.id, instrumento_id=inst.id))
    sessao.flush()
    return inst


def _ferramenta(inst):
    return f"{inst.nome}_{inst.id.hex[:8]}"


# ── Medição: QUAL instrumento gastou, e os que não eram medidos ─────────────────


def test_registro_diz_qual_instrumento_gastou(sessao, dados):
    ag = _agente(sessao, dados)
    inst = _no_cinto(sessao, dados, ag, "capa", "gerar_imagem",
                     {"modelo": "gpt-image-1", "qualidade": "medium"})
    [e] = mi.uso_de_instrumentos_pagos(sessao, ag.id, [_ferramenta(inst)])
    assert e["instrumento_id"] == str(inst.id)
    assert e["instrumento"] == "capa"
    assert e["tipo"] == "gerar_imagem"
    assert e["categoria"] == "instrumento"


def test_busca_exa_passa_a_ser_medida(sessao, dados):
    """US$7/mil buscas (até 10 resultados) + US$1/mil páginas de texto."""
    ag = _agente(sessao, dados)
    inst = _no_cinto(sessao, dados, ag, "exa", "busca_exa",
                     {"tipo_busca": "equilibrada", "max_resultados": 5})
    [e] = mi.uso_de_instrumentos_pagos(sessao, ag.id, [_ferramenta(inst)])
    assert e["custo_usd"] == round(0.007 + 5 * 0.001, 6)
    assert e["tipo"] == "busca_exa"


def test_busca_exa_profunda_e_com_muitos_resultados_custa_mais():
    # deep US$12/mil + 10 resultados além de 10 + 20 páginas de texto
    assert round(precos.custo_por_busca_exa("deep", 20), 6) == round(0.012 + 0.010 + 0.020, 6)


def test_leitura_firecrawl_passa_a_ser_medida(sessao, dados):
    ag = _agente(sessao, dados)
    inst = _no_cinto(sessao, dados, ag, "ler", "ler_site_firecrawl", {})
    [e] = mi.uso_de_instrumentos_pagos(sessao, ag.id, [_ferramenta(inst)])
    assert e["custo_usd"] == precos.PRECO_FIRECRAWL_POR_PAGINA


def test_operacao_de_conector_com_preco_informado_entra(sessao, dados):
    """A ferramenta de uma operação se chama pelo NOME dela; só entra quem tem preço."""
    ag = _agente(sessao, dados)
    inst = _no_cinto(sessao, dados, ag, "Gemini", "conector", {"operacoes": [
        {"nome": "Analisar SERP", "metodo": "POST", "url": "https://x",
         "custo_por_chamada_usd": 0.02},
        {"nome": "Gratis", "metodo": "GET", "url": "https://x"},
    ]})
    entradas = mi.uso_de_instrumentos_pagos(
        sessao, ag.id, ["Analisar_SERP", "Gratis", "Analisar_SERP"]
    )
    assert [e["custo_usd"] for e in entradas] == [0.02, 0.02]
    assert entradas[0]["instrumento_id"] == str(inst.id)
    assert entradas[0]["operacao"] == "Analisar SERP"


def test_conector_aceita_o_campo_de_preco():
    from instrumentos.conector import OperacaoConector

    op = OperacaoConector(nome="x", url="https://x", custo_por_chamada_usd=0.5)
    assert op.custo_por_chamada_usd == 0.5
    assert OperacaoConector(nome="x", url="https://x").custo_por_chamada_usd == 0.0


# ── O corte: IA dos agentes × instrumentos ─────────────────────────────────────


def test_separar_custos_divide_agente_e_instrumento():
    itens = [
        ({"categoria": "execucao", "custo_usd": 1.0}, "a1"),
        ({"categoria": "mensageria", "custo_usd": 0.5}, "a1"),
        ({"categoria": "instrumento", "custo_usd": 2.0, "instrumento_id": "i1",
          "instrumento": "capa", "tipo": "gerar_imagem"}, "a1"),
        ({"categoria": "instrumento", "custo_usd": 0.3}, "a2"),  # antigo, sem id
        ({"categoria": "transcricao", "custo_usd": 0.1}, None),
    ]
    c = precos.separar_custos(itens)
    assert c["ia_agentes_usd"] == 1.5
    assert c["instrumentos_usd"] == 2.4
    assert c["por_agente"]["a1"] == {"ia_usd": 1.5, "instrumentos_usd": 2.0}
    assert c["por_agente"][""] == {"ia_usd": 0.0, "instrumentos_usd": 0.1}
    assert c["por_instrumento"]["i1"]["nome"] == "capa"
    assert c["por_instrumento"]["anteriores"]["custo_usd"] == 0.3
    assert c["por_instrumento"]["transcricao"]["tipo"] == "transcricao"


def test_custos_do_time_soma_o_mesmo_total_de_sempre(sessao, dados):
    """O corte não pode mudar o total: a soma das partes é o custo acumulado antigo."""
    ag = _agente(sessao, dados)
    inst = _no_cinto(sessao, dados, ag, "capa", "gerar_imagem", {})
    au = Automacao(time_id=dados["timeA"].id, nome="A", tipo_gatilho="manual",
                   cadeia=[], ativa=True)
    sessao.add(au)
    sessao.flush()
    ex = Execucao(automacao_id=au.id, estado="concluida", entrada={"texto": "x"})
    sessao.add(ex)
    sessao.flush()
    uso = [
        {"modelo": "claude-sonnet-5", "tokens_entrada": 100_000, "tokens_saida": 10_000,
         "categoria": "execucao"},
        {"modelo": "gpt-image-1", "custo_usd": 0.042, "categoria": "instrumento",
         "instrumento_id": str(inst.id), "instrumento": "capa", "tipo": "gerar_imagem"},
    ]
    sessao.add(PassoExecucao(execucao_id=ex.id, ordem=1, agente_id=ag.id,
                             entrada={"texto": "x"}, saida={"uso": uso},
                             estado="concluido"))
    sessao.flush()

    c = custos_do_time(sessao, dados["timeA"].id)
    total_antigo = precos.resumir_uso(
        sessao.query(PassoExecucao).filter_by(execucao_id=ex.id).all()
    )
    assert round(c["custo_usd"], 6) == round(total_antigo["custo_usd"], 6)
    assert c["instrumentos_usd"] == 0.042
    assert c["por_agente"][0]["nome"] == "Redator"
    assert c["por_instrumento"][0]["nome"] == "capa"
    assert c["por_instrumento"][0]["chamadas"] == 1


def test_rota_do_resumo_traz_o_corte(cliente, entrar, dados):
    entrar(dados["operador"])
    r = cliente.get(f"/times/{dados['timeA'].id}/resumo")
    assert r.status_code == 200, r.text
    corpo = r.json()
    for campo in ("custo_ia_agentes_usd", "custo_instrumentos_usd",
                  "custo_por_agente", "custo_por_instrumento"):
        assert campo in corpo
