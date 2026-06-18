"""Testes da medição de uso refinada por origem da chave (Fase 7.6).

Cobrem a agregação `por_origem` (cliente × consultoria × legado) e o endpoint
consolidado `/uso/resumo`, incluindo o isolamento entre organizações.
"""

from types import SimpleNamespace

import precos
from modelos import Automacao, Execucao, PassoExecucao


def _passo(uso):
    return SimpleNamespace(saida={"uso": uso})


def test_resumir_uso_separa_por_origem():
    passos = [
        _passo([{"modelo": "haiku", "tokens_entrada": 100, "tokens_saida": 50, "origem": "organizacao"}]),
        _passo([{"modelo": "haiku", "tokens_entrada": 200, "tokens_saida": 80, "origem": "consultoria"}]),
        _passo([{"modelo": "haiku", "tokens_entrada": 10, "tokens_saida": 5}]),  # sem origem
    ]
    r = precos.resumir_uso(passos)
    assert r["tokens_entrada"] == 310 and r["tokens_saida"] == 135
    assert r["por_origem"]["organizacao"]["tokens_entrada"] == 100
    assert r["por_origem"]["consultoria"]["tokens_saida"] == 80
    # Passo sem origem registrada cai em 'desconhecida' (compat. com passos antigos).
    assert r["por_origem"]["desconhecida"]["tokens_entrada"] == 10


# ───────────── por_categoria + Whisper (custo por minuto, pré-calc.) ──────────


def _msg_uso(uso):
    """Mensagem de conversa (mensageria) que guarda a LISTA de uso do turno."""
    from types import SimpleNamespace as NS

    return NS(uso=uso)


def test_entradas_dos_passos_carimba_categoria_execucao():
    # Passo antigo, sem categoria, é colhido como 'execucao' (a fonte) sem mutar.
    e_original = {"modelo": "haiku", "tokens_entrada": 10, "tokens_saida": 5}
    entradas = list(precos.entradas_dos_passos([_passo([e_original])]))
    assert entradas[0]["categoria"] == "execucao"
    assert "categoria" not in e_original  # não mutou o dict guardado


def test_custo_whisper_por_minuto():
    assert precos.custo_whisper(60) == precos.PRECO_WHISPER_MIN  # 1 min
    assert precos.custo_whisper(0) == 0.0


def test_custo_de_entrada_honra_precalc():
    # Itens não-token (Whisper) trazem custo_usd pronto — é o que vale.
    assert precos.custo_de_entrada({"modelo": "whisper-1", "custo_usd": 0.012}) == 0.012
    # Sem custo_usd, estima por token (haiku entrada = 1.0/Mtok).
    por_token = {"modelo": "haiku", "tokens_entrada": 1_000_000, "tokens_saida": 0}
    assert precos.custo_de_entrada(por_token) == 1.0


def test_resumir_uso_separa_por_categoria_e_inclui_mensageria():
    mensagens = [
        _msg_uso(
            [
                {"modelo": "haiku", "tokens_entrada": 300, "tokens_saida": 100,
                 "origem": "consultoria", "categoria": "mensageria"},
                {"modelo": "whisper-1", "segundos": 120, "custo_usd": 0.012,
                 "origem": "consultoria", "categoria": "transcricao"},
            ]
        )
    ]
    r = precos.resumir_uso(mensagens=mensagens)
    assert r["por_categoria"]["mensageria"]["tokens_entrada"] == 300
    # custo pré-calculado do Whisper é honrado na agregação por categoria.
    assert r["por_categoria"]["transcricao"]["custo_usd"] == 0.012
    # e a origem (chave-mãe) soma as duas categorias.
    assert r["por_origem"]["consultoria"]["tokens_entrada"] == 300


def test_custo_por_imagem():
    # Preço por modelo × QUALIDADE (a qualidade é a maior alavanca de custo).
    assert precos.custo_por_imagem("gpt-image-1", qualidade="low") == 0.011
    assert precos.custo_por_imagem("gpt-image-1", qualidade="medium") == 0.042
    assert precos.custo_por_imagem("gpt-image-1", qualidade="high") == 0.167
    # Sem qualidade explícita → medium (o padrão do instrumento).
    assert precos.custo_por_imagem("gpt-image-1") == 0.042
    # Qualidade desconhecida → medium; modelo desconhecido → padrão global.
    assert precos.custo_por_imagem("gpt-image-1", qualidade="ultra") == 0.042
    assert precos.custo_por_imagem("zzz") == precos.PRECO_IMAGEM_PADRAO
    # O mini é mais barato que o base na mesma qualidade.
    assert precos.custo_por_imagem(
        "gpt-image-1-mini", qualidade="high"
    ) < precos.custo_por_imagem("gpt-image-1", qualidade="high")


def test_resumir_uso_agrega_categoria_instrumento():
    from types import SimpleNamespace as NS

    passos = [
        NS(
            saida={
                "uso": [
                    {"modelo": "haiku", "tokens_entrada": 100, "tokens_saida": 50},
                    {"modelo": "dall-e-3", "imagens": 1, "custo_usd": 0.04,
                     "origem": "organizacao", "categoria": "instrumento"},
                ]
            }
        )
    ]
    r = precos.resumir_uso(passos)
    # a imagem entra na categoria 'instrumento' com o custo pré-calculado;
    # a chamada de LLM do mesmo passo cai em 'execucao' (padrão da fonte).
    assert r["por_categoria"]["instrumento"]["custo_usd"] == 0.04
    assert r["por_categoria"]["execucao"]["tokens_entrada"] == 100


def _semear_passo(sessao, time_id, origem, te, ts):
    auto = Automacao(time_id=time_id, nome="Auto", tipo_gatilho="manual")
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(automacao_id=auto.id, estado="concluida")
    sessao.add(ex)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=ex.id,
            ordem=1,
            agente_id=None,
            saida={"uso": [{"modelo": "claude-haiku-4-5", "tokens_entrada": te, "tokens_saida": ts, "origem": origem}]},
            estado="concluido",
        )
    )
    sessao.flush()


def test_resumo_uso_endpoint_agrega_por_origem(cliente, entrar, dados, sessao):
    _semear_passo(sessao, dados["timeA"].id, "organizacao", 100, 40)
    _semear_passo(sessao, dados["timeA"].id, "consultoria", 200, 70)
    entrar(dados["admin"])
    r = cliente.get("/uso/resumo")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["tokens_entrada"] == 300
    assert corpo["por_origem"]["organizacao"]["tokens_saida"] == 40
    assert corpo["por_origem"]["consultoria"]["tokens_entrada"] == 200


def test_resumo_uso_isolado_entre_organizacoes(cliente, entrar, dados, sessao):
    _semear_passo(sessao, dados["timeA"].id, "organizacao", 100, 40)
    # 'estranho' é membro só da Org B; não enxerga o consumo da Org A.
    entrar(dados["estranho"])
    corpo = cliente.get("/uso/resumo").json()
    assert corpo["tokens_entrada"] == 0 and corpo["por_origem"] == {}
