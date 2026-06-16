"""Testes do resumo do time (GET /times/{id}/resumo) — a visão de saúde que
alimenta a barra de abas (contadores) e a aba Início (agregados). Só leitura;
montamos as coleções na transação revertida e conferimos contadores e agregados."""

from modelos import Agente, Automacao, Conversa, Execucao, Instrumento


def _montar_time(sessao, time):
    """Popula o time com 2 agentes, 1 instrumento (canal), 1 automação manual,
    3 execuções (concluída/falhou/aguardando) e 2 conversas (1 aberta, 1 fechada)."""
    sessao.add_all(
        [
            Agente(time_id=time.id, nome="Líder", papel="lider"),
            Agente(time_id=time.id, nome="Redator", papel="agente"),
        ]
    )
    instr = Instrumento(time_id=time.id, nome="Canal", tipo="enviar_telegram")
    sessao.add(instr)
    auto = Automacao(
        time_id=time.id, nome="Fluxo", tipo_gatilho="manual", cadeia=[], ativa=True
    )
    sessao.add(auto)
    sessao.flush()

    sessao.add_all(
        [
            Execucao(automacao_id=auto.id, estado="concluida"),
            Execucao(automacao_id=auto.id, estado="falhou"),
            Execucao(automacao_id=auto.id, estado="aguardando_humano"),
        ]
    )
    sessao.add_all(
        [
            Conversa(
                instrumento_id=instr.id, canal="telegram",
                contato_chave="111", estado="aberta",
            ),
            Conversa(
                instrumento_id=instr.id, canal="telegram",
                contato_chave="222", estado="fechada",
            ),
        ]
    )
    sessao.flush()


def test_resumo_conta_colecoes_e_agregados(cliente, entrar, dados, sessao):
    _montar_time(sessao, dados["timeA"])
    entrar(dados["observador"])  # leitura: qualquer membro

    r = cliente.get(f"/times/{dados['timeA'].id}/resumo")
    assert r.status_code == 200
    corpo = r.json()

    assert corpo["agentes"] == 2
    assert corpo["instrumentos"] == 1
    assert corpo["automacoes"] == 1
    assert corpo["execucoes"] == 3
    assert corpo["conversas"] == 2

    assert corpo["ativo"] is True  # automação ativa
    assert corpo["gatilho"] == "manual"
    assert corpo["pendencias"] == 1  # 1 aguardando_humano
    assert corpo["taxa_sucesso"] == 0.5  # 1 concluída de 2 finalizadas
    assert corpo["conversas_em_andamento"] == 1  # 1 aberta, 1 fechada
    assert corpo["custo_acumulado_usd"] == 0.0  # sem uso registrado


def test_resumo_time_vazio(cliente, entrar, dados):
    entrar(dados["admin"])
    r = cliente.get(f"/times/{dados['timeA'].id}/resumo")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["agentes"] == 0
    assert corpo["automacoes"] == 0
    assert corpo["ativo"] is False
    assert corpo["gatilho"] is None
    assert corpo["taxa_sucesso"] is None
    assert corpo["pendencias"] == 0


def test_resumo_isolado_por_organizacao(cliente, entrar, dados):
    # Estranho (membro só da Org B) não enxerga o time da Org A.
    entrar(dados["estranho"])
    r = cliente.get(f"/times/{dados['timeA'].id}/resumo")
    assert r.status_code in (403, 404)
