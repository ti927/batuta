"""Motor de cadeia no formato de GRAFO (lista de nós tipados).

Cobre o `executar_cadeia`: linear, bifurcação, loop com guarda de passos, portão
(gate) que pausa, nó roteador (classifica sem rodar agente), nó fim como destino e o
mesmo agente em dois nós (no_id distingue).

E o que a Onda 1 (2026-08-31) trouxe — o motor caminhando por ONDAS:
fan-out (segue TODOS os ramos atendidos), junção implícita (nó de convergência roda
uma vez), saída de erro, saída "senão", nunca mais escolha silenciosa, nó sem saída
que avisa e teto de passos por execução.

`executar_agente` e `_rotear_por_llm` são mockados — o motor não chama LLM aqui.
"""

import uuid

import pytest

from modelos import Agente
from orquestracao import cadeia as motor
from orquestracao.cadeia import validar_cadeia


@pytest.fixture
def ag(sessao, dados):
    """Fábrica de agentes reais no time de teste (transação revertida)."""
    def criar(nome):
        a = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
        sessao.add(a)
        sessao.flush()
        return a
    return criar


def _mock_agentes(monkeypatch, saidas_por_nome, ramos_por_nome=None, entradas=None):
    """Mocka `executar_agente`: devolve a saída (e, opcionalmente, os ramos
    declarados) por nome do agente. `ramos_por_nome` aceita str ou lista.
    `entradas` (dict) recebe a entrada que cada nó viu — para provar a junção."""
    ramos_por_nome = ramos_por_nome or {}
    def fake(agente, cinto, entrada, **kwargs):
        if entradas is not None:
            entradas[agente.nome] = entrada
        r = ramos_por_nome.get(agente.nome)
        saida = saidas_por_nome.get(agente.nome, "ok")
        if isinstance(saida, Exception):
            raise saida
        return {
            "saida": saida,
            "instrumentos_acionados": [],
            "uso": [],
            "ramos_escolhidos": [r] if isinstance(r, str) else list(r or []),
        }
    monkeypatch.setattr(motor, "executar_agente", fake)


def _mock_roteador(monkeypatch):
    """Mocka `_rotear_por_llm`: devolve as saídas cujo rótulo == texto (ou nenhuma)."""
    def fake(saida_texto, saidas):
        alvo = (saida_texto or "").strip()
        uso = {"modelo": "x", "tokens_entrada": 0, "tokens_saida": 0}
        return [s for s in saidas if s["rotulo"] == alvo], uso
    monkeypatch.setattr(motor, "_rotear_por_llm", fake)


def test_linear_conclui(sessao, dados, ag, monkeypatch):
    a = ag("Solo")
    _mock_agentes(monkeypatch, {"Solo": "feito"})
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    assert r["resultado"] == "feito"
    # cada passo registra o id do nó
    assert r["passos"][0]["no_id"] == "n1"


def test_bifurcacao_segue_ramo_certo(sessao, dados, ag, monkeypatch):
    cacador = ag("Cacador")
    validador = ag("Validador")
    publicador = ag("Publicador")
    _mock_roteador(monkeypatch)

    cadeia = {
        "inicial": "cacador",
        "nos": [
            {"id": "cacador", "tipo": "agente", "ref": str(cacador.id),
             "saidas": [{"rotulo": "tema", "destino": "validador"}]},
            {"id": "validador", "tipo": "agente", "ref": str(validador.id),
             "saidas": [
                 {"rotulo": "ok", "destino": "publicador"},
                 {"rotulo": "refazer", "destino": "cacador"},
             ]},
            {"id": "publicador", "tipo": "agente", "ref": str(publicador.id),
             "saidas": [{"rotulo": "pub", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }

    # validador diz "ok" → segue para publicador (ramo ok)
    _mock_agentes(monkeypatch, {"Cacador": "tema", "Validador": "ok", "Publicador": "publicado"})
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    nos_visitados = [p["no_id"] for p in r["passos"]]
    assert nos_visitados == ["cacador", "validador", "publicador"]


def _mock_roteador_explode(monkeypatch):
    """`_rotear_por_llm` que estoura se for chamado — prova que o agente declarou e
    o roteador-adivinhador NÃO foi acionado."""
    def fake(saida_texto, saidas):
        raise AssertionError("o roteador não devia ser chamado: o agente declarou")
    monkeypatch.setattr(motor, "_rotear_por_llm", fake)


def test_ramo_declarado_pelo_agente_dispensa_o_roteador(sessao, dados, ag, monkeypatch):
    val = ag("Validador")
    pub = ag("Publicador")
    _mock_roteador_explode(monkeypatch)  # se chamado, falha
    _mock_agentes(
        monkeypatch,
        {"Validador": "texto qualquer", "Publicador": "pub"},
        ramos_por_nome={"Validador": "refazer"},  # agente declara "refazer"
    )
    cadeia = {
        "inicial": "validador",
        "nos": [
            {"id": "validador", "tipo": "agente", "ref": str(val.id),
             "saidas": [
                 {"rotulo": "ok", "destino": "publicador"},
                 {"rotulo": "refazer", "destino": "fim"},
             ]},
            {"id": "publicador", "tipo": "agente", "ref": str(pub.id),
             "saidas": [{"rotulo": "pub", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"  # "refazer" → fim
    assert [p["no_id"] for p in r["passos"]] == ["validador"]
    assert r["passos"][-1]["saida_escolhida"] == "refazer"


def test_rotulo_inexistente_cai_no_roteador(sessao, dados, ag, monkeypatch):
    val = ag("Validador")
    _mock_roteador(monkeypatch)  # fallback ativo
    _mock_agentes(
        monkeypatch,
        {"Validador": "ok"},
        ramos_por_nome={"Validador": "fantasma"},  # rótulo que não existe no nó
    )
    cadeia = {
        "inicial": "validador",
        "nos": [
            {"id": "validador", "tipo": "agente", "ref": str(val.id),
             "saidas": [
                 {"rotulo": "ok", "destino": "fim"},
                 {"rotulo": "refazer", "destino": "validador"},
             ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    # roteador (mock: rótulo == texto "ok") escolhe "ok" → conclui
    assert r["estado"] == "concluida"
    assert r["passos"][-1]["saida_escolhida"] == "ok"


def test_sem_declaracao_usa_o_roteador(sessao, dados, ag, monkeypatch):
    val = ag("Validador")
    _mock_roteador(monkeypatch)
    _mock_agentes(monkeypatch, {"Validador": "ok"})  # não declara ramo
    cadeia = {
        "inicial": "validador",
        "nos": [
            {"id": "validador", "tipo": "agente", "ref": str(val.id),
             "saidas": [
                 {"rotulo": "ok", "destino": "fim"},
                 {"rotulo": "refazer", "destino": "validador"},
             ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    assert r["passos"][-1]["saida_escolhida"] == "ok"


def test_loop_com_guarda_de_passos(sessao, dados, ag, monkeypatch):
    a = ag("Eterno")
    _mock_agentes(monkeypatch, {"Eterno": "de novo"})
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "loop", "destino": "n1"}]},  # volta para si mesmo
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(RuntimeError, match="Máximo de passos"):
        motor.executar_cadeia(sessao, cadeia, "vai", max_passos=3)


def test_gate_pausa(sessao, dados, ag, monkeypatch):
    revisor = ag("Revisor")
    _mock_agentes(monkeypatch, {"Revisor": "Artigo pronto para aprovação"})
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(revisor.id), "gate": True,
             "saidas": [
                 {"rotulo": "aprovado", "destino": "fim"},
                 {"rotulo": "reprovado", "destino": "rev"},
             ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "aguardando_humano"
    assert r["pergunta"] == "Artigo pronto para aprovação"
    # o nó com gate NÃO roteia sozinho (a resposta do humano decide depois)
    assert r["passos"][-1]["saida_escolhida"] is None
    assert r["passos"][-1]["no_id"] == "rev"
    # Fatia 4.1: o passo de PORTÃO é carimbado como espera-por-humano na timeline.
    assert r["passos"][-1]["tipo"] == "espera_humano"


def test_no_roteador_classifica_sem_agente(sessao, dados, ag, monkeypatch):
    destino_a = ag("CaminhoA")
    _mock_agentes(monkeypatch, {"CaminhoA": "cheguei em A"})
    _mock_roteador(monkeypatch)
    cadeia = {
        "inicial": "rot",
        "nos": [
            {"id": "rot", "tipo": "roteador", "nome": "Triagem",
             "saidas": [
                 {"rotulo": "A", "destino": "na"},
                 {"rotulo": "B", "destino": "fim"},
             ]},
            {"id": "na", "tipo": "agente", "ref": str(destino_a.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    # entrada "A" → o roteador (mock) escolhe a saída de rótulo "A" → vai p/ o agente
    r = motor.executar_cadeia(sessao, cadeia, "A")
    assert r["estado"] == "concluida"
    assert r["resultado"] == "cheguei em A"
    primeiro = r["passos"][0]
    assert primeiro["no_id"] == "rot"
    # Fatia 4.1: nó roteador → tipo "roteador"; nó de agente → tipo "agente".
    assert primeiro["tipo"] == "roteador"
    assert r["passos"][1]["tipo"] == "agente"
    assert primeiro["agente_id"] is None  # roteador não roda agente
    assert primeiro["saida_escolhida"] == "A"


def test_mesmo_agente_em_dois_nos(sessao, dados, ag, monkeypatch):
    a = ag("Reaproveitado")
    _mock_agentes(monkeypatch, {"Reaproveitado": "ok"})
    _mock_roteador(monkeypatch)
    cadeia = {
        "inicial": "p1",
        "nos": [
            {"id": "p1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "segue", "destino": "p2"}]},
            {"id": "p2", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "fim", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    nos = [p["no_id"] for p in r["passos"]]
    agentes = [p["agente_id"] for p in r["passos"]]
    assert nos == ["p1", "p2"]               # dois nós distintos
    assert agentes == [str(a.id), str(a.id)]  # o mesmo agente nos dois


def test_validar_rascunho_so_gatilho_e_fim_nao_levanta():
    # rascunho permitido: nada para rodar ainda (sem agente/roteador) → não exige início
    cadeia = {
        "inicial": None,
        "nos": [
            {"id": "gatilho", "tipo": "gatilho", "gatilho": "manual", "saidas": []},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    validar_cadeia(cadeia, set())  # não levanta


def test_validar_executavel_sem_inicio_erro_acionavel():
    # há um nó executável (roteador) mas nenhum início escolhido → erro H1 claro
    cadeia = {
        "nos": [
            {"id": "gatilho", "tipo": "gatilho", "gatilho": "manual", "saidas": []},
            {"id": "rot", "tipo": "roteador", "nome": "T",
             "saidas": [{"rotulo": "a", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(ValueError, match="início que possa rodar"):
        validar_cadeia(cadeia, set())


def test_ref_para_agente_inexistente_erro_cita_o_no(sessao, dados):
    # nó cujo `ref` aponta para um agente que não existe mais → erro claro com o no_id
    fantasma = str(uuid.uuid4())
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": fantasma,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(ValueError) as exc:
        motor.executar_cadeia(sessao, cadeia, "vai")
    assert "n1" in str(exc.value)
    assert "não existe mais" in str(exc.value)


# ─────────── Onda 1: o grafo se comporta como grafo (2026-08-31) ───────────


def _cadeia_em_y(cacador_id, carrossel_id, story_id, refazer_id):
    """O caso do maestro: uma capa aprovada deve alimentar Carrossel E Story."""
    return {
        "inicial": "capa",
        "nos": [
            {"id": "capa", "tipo": "agente", "ref": cacador_id, "saidas": [
                {"rotulo": "aprovado1", "quando": "a capa foi aprovada",
                 "destino": "carrossel"},
                {"rotulo": "aprovado2", "quando": "a capa foi aprovada",
                 "destino": "story"},
                {"rotulo": "reprovado", "quando": "pediram ajuste",
                 "destino": "refazer"},
            ]},
            {"id": "carrossel", "tipo": "agente", "ref": carrossel_id,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "story", "tipo": "agente", "ref": story_id,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "refazer", "tipo": "agente", "ref": refazer_id, "saidas": []},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }


def test_fanout_segue_TODOS_os_ramos_atendidos(sessao, dados, ag, monkeypatch):
    """O bug que custou meses: com duas saídas atendidas, o motor seguia UMA e
    descartava a outra em silêncio. Agora as duas rodam."""
    capa, carr, story, refaz = ag("Capa"), ag("Carrossel"), ag("Story"), ag("Refazer")
    _mock_roteador_explode(monkeypatch)  # o agente declarou: roteador não entra
    _mock_agentes(
        monkeypatch,
        {"Capa": "capa pronta", "Carrossel": "carrossel publicado",
         "Story": "story publicado"},
        ramos_por_nome={"Capa": ["aprovado1", "aprovado2"]},
    )
    r = motor.executar_cadeia(
        sessao,
        _cadeia_em_y(str(capa.id), str(carr.id), str(story.id), str(refaz.id)),
        "vai",
    )
    assert r["estado"] == "concluida"
    assert [p["no_id"] for p in r["passos"]] == ["capa", "carrossel", "story"]
    assert r["passos"][0]["saidas_escolhidas"] == ["aprovado1", "aprovado2"]
    # o ramo reprovado NÃO rodou
    assert "refazer" not in [p["no_id"] for p in r["passos"]]


def test_juncao_implicita_roda_o_no_uma_vez(sessao, dados, ag, monkeypatch):
    """Dois ramos que reencontram o mesmo nó: ele roda UMA vez, com os dois textos
    juntos. Sem isso, um fluxo em Y publicaria em dobro."""
    inicio, final = ag("Inicio"), ag("Publicador")
    entradas: dict = {}
    _mock_roteador_explode(monkeypatch)
    _mock_agentes(
        monkeypatch,
        {"Inicio": "texto base", "Publicador": "publicado"},
        ramos_por_nome={"Inicio": ["a", "b"]},
        entradas=entradas,
    )
    cadeia = {
        "inicial": "ini",
        "nos": [
            {"id": "ini", "tipo": "agente", "ref": str(inicio.id), "saidas": [
                {"rotulo": "a", "quando": "sempre", "destino": "pub"},
                {"rotulo": "b", "quando": "sempre", "destino": "pub"},
            ]},
            {"id": "pub", "tipo": "agente", "ref": str(final.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    assert [p["no_id"] for p in r["passos"]].count("pub") == 1  # UMA vez só
    # e recebeu os dois textos juntos
    assert entradas["Publicador"].count("texto base") == 2


def test_saida_de_erro_segue_em_vez_de_matar_a_execucao(sessao, dados, ag, monkeypatch):
    """Nó que falha com saída de erro desenhada: o passo falho fica gravado e o fluxo
    segue pelo ramo de erro levando a mensagem."""
    quebra, avisador = ag("Quebra"), ag("Avisador")
    _mock_agentes(
        monkeypatch,
        {"Quebra": RuntimeError("o WordPress recusou"), "Avisador": "avisei o time"},
    )
    cadeia = {
        "inicial": "q",
        "nos": [
            {"id": "q", "tipo": "agente", "ref": str(quebra.id), "saidas": [
                {"rotulo": "ok", "quando": "publicou", "destino": "fim"},
                {"rotulo": "deu erro", "tipo": "erro", "destino": "aviso"},
            ]},
            {"id": "aviso", "tipo": "agente", "ref": str(avisador.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    assert r["passos"][0]["estado"] == "falhou"          # o passo falho fica gravado
    assert "o WordPress recusou" in r["passos"][0]["saida"]
    assert r["passos"][1]["no_id"] == "aviso"            # seguiu pelo ramo de erro
    assert "o WordPress recusou" in r["passos"][1]["entrada"]
    # o passo falho diz QUEM falhou (é o nome que a timeline e o aviso mostram)
    assert r["passos"][0]["agente_nome"] == "Quebra"
    assert r["passos"][0]["agente_id"] == str(quebra.id)


def test_sem_saida_de_erro_a_execucao_falha_mas_grava_o_passo(sessao, dados, ag, monkeypatch):
    quebra = ag("Quebra")
    registrados: list = []
    _mock_agentes(monkeypatch, {"Quebra": RuntimeError("estourou")})
    cadeia = {
        "inicial": "q",
        "nos": [
            {"id": "q", "tipo": "agente", "ref": str(quebra.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(RuntimeError, match="estourou"):
        motor.executar_cadeia(
            sessao, cadeia, "vai",
            registrar_passo=lambda p, o: registrados.append(p),
        )
    # a timeline não pula mais do último passo bom direto para "falhou"
    assert registrados and registrados[-1]["estado"] == "falhou"
    assert registrados[-1]["no_id"] == "q"


def test_saida_senao_quando_nada_casa(sessao, dados, ag, monkeypatch):
    triagem, padrao = ag("Triagem"), ag("Padrao")
    _mock_roteador(monkeypatch)  # nada casa: devolve []
    _mock_agentes(monkeypatch, {"Triagem": "nada disso", "Padrao": "tratei"})
    cadeia = {
        "inicial": "t",
        "nos": [
            {"id": "t", "tipo": "agente", "ref": str(triagem.id), "saidas": [
                {"rotulo": "urgente", "quando": "é urgente", "destino": "fim"},
                {"rotulo": "normal", "quando": "é rotina", "destino": "fim"},
                {"rotulo": "resto", "tipo": "senao", "destino": "padrao"},
            ]},
            {"id": "padrao", "tipo": "agente", "ref": str(padrao.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert [p["no_id"] for p in r["passos"]] == ["t", "padrao"]
    assert r["passos"][0]["saidas_escolhidas"] == ["resto"]


def test_nada_casa_e_sem_senao_encerra_com_motivo(sessao, dados, ag, monkeypatch):
    """Nunca mais escolha silenciosa: antes caía calado na PRIMEIRA saída."""
    triagem, urgente = ag("Triagem"), ag("Urgente")
    _mock_roteador(monkeypatch)
    _mock_agentes(monkeypatch, {"Triagem": "nada disso"})
    cadeia = {
        "inicial": "t",
        "nos": [
            {"id": "t", "tipo": "agente", "ref": str(triagem.id), "saidas": [
                {"rotulo": "urgente", "quando": "é urgente", "destino": "u"},
                {"rotulo": "normal", "quando": "é rotina", "destino": "fim"},
            ]},
            {"id": "u", "tipo": "agente", "ref": str(urgente.id), "saidas": []},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    assert [p["no_id"] for p in r["passos"]] == ["t"]  # NÃO caiu na primeira saída
    assert r["passos"][0]["saidas_escolhidas"] == []
    assert r["avisos"] and "nenhuma das condições" in r["avisos"][0]


def test_no_sem_saida_avisa_em_vez_de_verde_falso(sessao, dados, ag, monkeypatch):
    solo = ag("Solo")
    _mock_agentes(monkeypatch, {"Solo": "feito"})
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(solo.id), "saidas": []},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "concluida"
    assert r["resultado"] == "feito"
    assert r["avisos"] and "não tem saída ligada" in r["avisos"][0]


def test_condicao_obrigatoria_quando_o_no_bifurca(sessao, dados, ag):
    """A causa-raiz: o editor só tinha caixa para o rótulo, então toda condição ficava
    vazia e o agente escolhia no escuro. Agora não salva sem preencher."""
    a, b = ag("A"), ag("B")
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id), "nome": "Validador",
             "saidas": [
                 {"rotulo": "aprovado", "destino": "n2"},
                 {"rotulo": "reprovado", "quando": "pediram ajuste", "destino": "fim"},
             ]},
            {"id": "n2", "tipo": "agente", "ref": str(b.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(ValueError, match="Siga por aqui quando"):
        validar_cadeia(cadeia, {str(a.id), str(b.id)})


def test_copiar_cadeia_legada_nao_exige_condicao(sessao, dados, ag):
    """Duplicar time/automação NÃO pode ser bloqueado por dado legado: automações
    anteriores a 2026-08-31 têm todas as condições vazias."""
    a, b = ag("A"), ag("B")
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [
                 {"rotulo": "aprovado", "destino": "n2"},
                 {"rotulo": "reprovado", "destino": "fim"},
             ]},
            {"id": "n2", "tipo": "agente", "ref": str(b.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    validar_cadeia(cadeia, {str(a.id), str(b.id)}, exigir_condicao=False)  # não levanta


def test_uma_saida_so_nao_exige_condicao(sessao, dados, ag):
    a = ag("A")
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "segue", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    validar_cadeia(cadeia, {str(a.id)})  # não levanta


def test_saida_de_erro_e_senao_nao_exigem_condicao(sessao, dados, ag):
    a = ag("A")
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id), "saidas": [
                {"rotulo": "ok", "quando": "deu certo", "destino": "fim"},
                {"rotulo": "reprova", "quando": "deu ruim", "destino": "fim"},
                {"rotulo": "erro", "tipo": "erro", "destino": "fim"},
                {"rotulo": "resto", "tipo": "senao", "destino": "fim"},
            ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    validar_cadeia(cadeia, {str(a.id)})  # não levanta


def test_teto_de_passos_vale_por_execucao(sessao, dados, ag, monkeypatch):
    """Antes o teto zerava a cada retomada — um laço que atravessa portões corria
    para sempre. Agora `ordem_inicial` conta."""
    a = ag("Eterno")
    _mock_agentes(monkeypatch, {"Eterno": "de novo"})
    cadeia = {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "loop", "destino": "n1"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    with pytest.raises(RuntimeError, match="Máximo de passos"):
        motor.executar_cadeia(sessao, cadeia, "vai", max_passos=5, ordem_inicial=4)


def test_pausa_guarda_os_ramos_pendentes(sessao, dados, ag, monkeypatch):
    """Portão no meio de uma onda: os outros ramos não somem — voltam em
    `pendentes` para a retomada levá-los adiante."""
    inicio, portao, outro = ag("Inicio"), ag("Portao"), ag("Outro")
    _mock_roteador_explode(monkeypatch)
    _mock_agentes(
        monkeypatch,
        {"Inicio": "base", "Portao": "aprova?", "Outro": "fiz"},
        ramos_por_nome={"Inicio": ["a", "b"]},
    )
    cadeia = {
        "inicial": "ini",
        "nos": [
            {"id": "ini", "tipo": "agente", "ref": str(inicio.id), "saidas": [
                {"rotulo": "a", "quando": "sempre", "destino": "port"},
                {"rotulo": "b", "quando": "sempre", "destino": "outro"},
            ]},
            {"id": "port", "tipo": "agente", "ref": str(portao.id), "gate": True,
             "saidas": [{"rotulo": "ok", "quando": "aprovou", "destino": "fim"}]},
            {"id": "outro", "tipo": "agente", "ref": str(outro.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "aguardando_humano"
    assert r["no_pausado"] == "port"
    assert [p["no"] for p in r["pendentes"]] == ["outro"]


def test_frente_inicial_retoma_varios_ramos(sessao, dados, ag, monkeypatch):
    a, b = ag("A"), ag("B")
    _mock_agentes(monkeypatch, {"A": "fez a", "B": "fez b"})
    cadeia = {
        "inicial": "na",
        "nos": [
            {"id": "na", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "nb", "tipo": "agente", "ref": str(b.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(
        sessao, cadeia, "ignorado",
        frente_inicial=[
            {"no": "na", "entradas": ["entrada a"]},
            {"no": "nb", "entradas": ["entrada b"]},
        ],
    )
    assert [p["no_id"] for p in r["passos"]] == ["na", "nb"]
    assert "fez a" in r["resultado"] and "fez b" in r["resultado"]


def test_retomada_por_no_inicial(sessao, dados, ag, monkeypatch):
    """Retomada começa de um nó específico (como faz a `retoma`)."""
    pub = ag("Publi")
    _mock_agentes(monkeypatch, {"Publi": "publicado"})
    _mock_roteador(monkeypatch)
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(pub.id), "gate": True,
             "saidas": [{"rotulo": "ok", "destino": "pub"}]},
            {"id": "pub", "tipo": "agente", "ref": str(pub.id),
             "saidas": [{"rotulo": "fim", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "feedback", no_inicial="pub")
    assert r["estado"] == "concluida"
    assert [p["no_id"] for p in r["passos"]] == ["pub"]
