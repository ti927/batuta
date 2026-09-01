"""A ficha da execução (Onda 2) — o dado deixa de morrer no primeiro nó.

Três coisas provadas aqui:

1. **A entrada do gatilho chega a TODOS os nós.** Era a lacuna-raiz: entre os nós
   trafegava só texto, e o que o gatilho trouxe só sobrevivia se o agente lembrasse de
   repetir. Foi assim que o Gerador Carrossel recebeu "Aprovado. Seguindo para
   publicação" no lugar do título e da URL do artigo (execução `f1e23565`, 2026-09-01).
2. **`anotar` é a variável de fluxo**: o agente guarda um valor e ele viaja pela ficha,
   não pela prosa.
3. **A regra exata é do MOTOR**, não da IA — inclusive na borda 10×11, onde a IA erra.

`executar_agente` e `_rotear_por_llm` são mockados: nenhum teste aqui chama LLM.
"""

import pytest
from langchain_core.messages import AIMessage

from mensageria import retoma
from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao import agente as agente_mod
from orquestracao import cadeia as motor
from orquestracao import ficha as ficha_mod


@pytest.fixture
def ag(sessao, dados):
    def criar(nome):
        a = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
        sessao.add(a)
        sessao.flush()
        return a
    return criar


def _mock(monkeypatch, *, saidas=None, ramos=None, anota=None, fichas_vistas=None):
    """Mocka `executar_agente` por nome de agente. `anota` diz o que cada um guarda na
    ficha; `fichas_vistas` coleta a ficha que cada um recebeu (a prova do item 1)."""
    saidas, ramos, anota = saidas or {}, ramos or {}, anota or {}

    def fake(agente, cinto, entrada, **kwargs):
        if fichas_vistas is not None:
            fichas_vistas[agente.nome] = dict(kwargs.get("ficha") or {})
        r = ramos.get(agente.nome)
        return {
            "saida": saidas.get(agente.nome, "ok"),
            "instrumentos_acionados": [],
            "uso": [],
            "ramos_escolhidos": [r] if isinstance(r, str) else list(r or []),
            "anotacoes": dict(anota.get(agente.nome) or {}),
        }

    monkeypatch.setattr(motor, "executar_agente", fake)


def _dois_nos(a, b):
    return {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "segue", "destino": "n2"}]},
            {"id": "n2", "tipo": "agente", "ref": str(b.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }


# --- 1. A entrada do gatilho não morre mais no primeiro nó -----------------------


def test_entrada_do_gatilho_chega_ao_segundo_no(sessao, dados, ag, monkeypatch):
    """O caso exato que quebrou em produção: o nó 1 responde uma frase seca e o nó 2
    PRECISA continuar tendo os dados do gatilho."""
    vistas: dict = {}
    a, b = ag("Primeiro"), ag("Segundo")
    _mock(monkeypatch, saidas={"Primeiro": "Aprovado. Seguindo."}, fichas_vistas=vistas)

    motor.executar_cadeia(
        sessao, _dois_nos(a, b), '"titulo": "Simples Nacional"\n"url": "https://x"'
    )

    assert '"titulo": "Simples Nacional"' in vistas["Segundo"]["entrada"]
    assert vistas["Segundo"]["entrada"] == vistas["Primeiro"]["entrada"]


def test_ficha_volta_no_resultado(sessao, dados, ag, monkeypatch):
    a, b = ag("Primeiro"), ag("Segundo")
    _mock(monkeypatch)
    r = motor.executar_cadeia(sessao, _dois_nos(a, b), "pedido 42")
    assert r["ficha"]["entrada"] == "pedido 42"


# --- 2. `anotar` — a variável de fluxo -------------------------------------------


def test_anotacao_de_um_no_chega_ao_seguinte(sessao, dados, ag, monkeypatch):
    vistas: dict = {}
    a, b = ag("Primeiro"), ag("Segundo")
    _mock(
        monkeypatch,
        anota={"Primeiro": {"url_da_capa": "https://img/1.png"}},
        fichas_vistas=vistas,
    )
    r = motor.executar_cadeia(sessao, _dois_nos(a, b), "vai")

    assert "url_da_capa" not in vistas["Primeiro"]      # ele ainda não tinha anotado
    assert vistas["Segundo"]["url_da_capa"] == "https://img/1.png"
    assert r["ficha"]["url_da_capa"] == "https://img/1.png"


def test_anotacao_aparece_no_rastro_do_passo(sessao, dados, ag, monkeypatch):
    a, b = ag("Primeiro"), ag("Segundo")
    _mock(monkeypatch, anota={"Primeiro": {"Total do Pedido": "1240"}})
    r = motor.executar_cadeia(sessao, _dois_nos(a, b), "vai")
    # O nome é NORMALIZADO: `Total do Pedido` e `total_do_pedido` são o mesmo campo.
    assert r["passos"][0]["anotou"] == ["total_do_pedido"]
    assert r["ficha"]["total_do_pedido"] == "1240"


def test_ultimo_a_escrever_vence(sessao, dados, ag, monkeypatch):
    a, b = ag("Primeiro"), ag("Segundo")
    _mock(monkeypatch, anota={"Primeiro": {"x": "1"}, "Segundo": {"x": "2"}})
    r = motor.executar_cadeia(sessao, _dois_nos(a, b), "vai")
    assert r["ficha"]["x"] == "2"


# --- 3. A regra exata é do motor -------------------------------------------------


def _com_regra(a, b, c, regra_b, regra_c):
    return {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id), "saidas": [
                {"rotulo": "pequeno", "quando": "for pequeno", "destino": "nb",
                 "regra": regra_b},
                {"rotulo": "grande", "quando": "for grande", "destino": "nc",
                 "regra": regra_c},
            ]},
            {"id": "nb", "tipo": "agente", "ref": str(b.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "nc", "tipo": "agente", "ref": str(c.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }


def test_regra_exata_decide_sem_a_ia(sessao, dados, ag, monkeypatch):
    """O motor compara; o agente NÃO declara ramo nenhum e mesmo assim o fluxo anda
    pelo caminho certo."""
    vistas: dict = {}
    a, b, c = ag("Apurador"), ag("Pequeno"), ag("Grande")
    _mock(monkeypatch, anota={"Apurador": {"total": "10"}}, fichas_vistas=vistas)
    # Se a LLM roteadora for chamada, o teste falha — a decisão tem de ser do código.
    monkeypatch.setattr(
        motor, "_rotear_por_llm",
        lambda *a, **k: pytest.fail("a regra exata não pode chamar a LLM roteadora"),
    )
    cadeia = _com_regra(
        a, b, c,
        {"campo": "total", "operador": "entre", "valor": "1", "valor2": "10"},
        {"campo": "total", "operador": "maior", "valor": "10"},
    )
    r = motor.executar_cadeia(sessao, cadeia, "vai")

    assert r["passos"][0]["saidas_escolhidas"] == ["pequeno"]
    assert "Pequeno" in vistas and "Grande" not in vistas


def test_a_borda_10_versus_11(sessao, dados, ag, monkeypatch):
    """`entre 1 e 10` é INCLUSIVO; 11 cai no outro lado. É a borda que a IA erra."""
    a, b, c = ag("Apurador"), ag("Pequeno"), ag("Grande")
    _mock(monkeypatch, anota={"Apurador": {"total": "11"}})
    cadeia = _com_regra(
        a, b, c,
        {"campo": "total", "operador": "entre", "valor": "1", "valor2": "10"},
        {"campo": "total", "operador": "maior", "valor": "10"},
    )
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["passos"][0]["saidas_escolhidas"] == ["grande"]


def test_regra_indecidivel_nao_vira_nao_em_silencio(sessao, dados, ag, monkeypatch):
    """Campo que não é número numa comparação numérica = 'não sei'. O motor NÃO o
    trata como 'não': devolve ao agente e, se ninguém escolher, o aviso diz o porquê."""
    a, b, c = ag("Apurador"), ag("Pequeno"), ag("Grande")
    _mock(monkeypatch, anota={"Apurador": {"total": "muito"}})
    monkeypatch.setattr(motor, "_rotear_por_llm", lambda t, s: ([], {"modelo": "x"}))
    cadeia = _com_regra(
        a, b, c,
        {"campo": "total", "operador": "maior", "valor": "10"},
        {"campo": "total", "operador": "menor", "valor": "10"},
    )
    r = motor.executar_cadeia(sessao, cadeia, "vai")

    assert r["passos"][0]["saidas_escolhidas"] == []
    aviso = r["avisos"][0]
    assert "não foi possível conferir a regra exata" in aviso
    assert "anotar" in aviso  # diz o que fazer
    resultados = {x["rotulo"]: x["resultado"] for x in r["passos"][0]["regras"]}
    assert resultados == {"pequeno": None, "grande": None}


def test_regra_que_nao_bate_avisa_com_o_motivo(sessao, dados, ag, monkeypatch):
    a, b, c = ag("Apurador"), ag("Pequeno"), ag("Grande")
    _mock(monkeypatch, anota={"Apurador": {"total": "500"}})
    cadeia = _com_regra(
        a, b, c,
        {"campo": "total", "operador": "menor", "valor": "10"},
        {"campo": "total", "operador": "entre", "valor": "20", "valor2": "30"},
    )
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["passos"][0]["saidas_escolhidas"] == []
    assert "não bateu com a ficha" in r["avisos"][0]


def test_saida_com_regra_e_saida_sem_regra_convivem(sessao, dados, ag, monkeypatch):
    """Com regra em uma saída, a outra NÃO é seguida automaticamente por ser única —
    ela passa pelo julgamento normal."""
    a, b, c = ag("Apurador"), ag("Pequeno"), ag("Grande")
    _mock(monkeypatch, anota={"Apurador": {"total": "5"}}, ramos={"Apurador": "grande"})
    cadeia = _com_regra(
        a, b, c,
        {"campo": "total", "operador": "menor", "valor": "10"},
        None,
    )
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    # a regra liberou "pequeno"; o agente declarou "grande" — os dois rodam.
    assert sorted(r["passos"][0]["saidas_escolhidas"]) == ["grande", "pequeno"]


# --- 4. "Para cada item" ----------------------------------------------------------


def _com_cada(a, b, *, lista="pedidos", acumular_em="", item_em=""):
    """Apurador anota uma lista → nó "cada" → Tratador roda uma vez por item."""
    no_cada = {"id": "loop", "tipo": "cada", "lista": lista, "nome": "Para cada pedido",
               "saidas": [{"rotulo": "item", "destino": "trat"}]}
    if acumular_em:
        no_cada["acumular_em"] = acumular_em
    if item_em:
        no_cada["item_em"] = item_em
    return {
        "inicial": "n1",
        "nos": [
            {"id": "n1", "tipo": "agente", "ref": str(a.id),
             "saidas": [{"rotulo": "segue", "destino": "loop"}]},
            no_cada,
            {"id": "trat", "tipo": "agente", "ref": str(b.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }


def test_cada_roda_uma_vez_por_item(sessao, dados, ag, monkeypatch):
    vistas: list = []
    a, b = ag("Apurador"), ag("Tratador")

    def fake(agente, cinto, entrada, **kwargs):
        f = dict(kwargs.get("ficha") or {})
        if agente.nome == "Tratador":
            vistas.append((f.get("item"), f.get("item_numero"), f.get("item_total")))
            return {"saida": f"tratei {f.get('item')}", "instrumentos_acionados": [],
                    "uso": [], "ramos_escolhidos": [], "anotacoes": {}}
        return {"saida": "ok", "instrumentos_acionados": [], "uso": [],
                "ramos_escolhidos": [],
                "anotacoes": {"pedidos": "- pedido A\n- pedido B\n- pedido C"}}

    monkeypatch.setattr(motor, "executar_agente", fake)
    r = motor.executar_cadeia(sessao, _com_cada(a, b), "vai")

    assert vistas == [("pedido A", "1", "3"), ("pedido B", "2", "3"), ("pedido C", "3", "3")]
    # A agregação natural: os três resultados no texto final, sem se fundirem em um passo.
    assert r["resultado"].count("tratei") == 3
    assert [p["no_id"] for p in r["passos"]] == ["n1", "trat", "trat", "trat"]


def test_cada_aceita_json(sessao, dados, ag, monkeypatch):
    vistas: list = []
    a, b = ag("Apurador"), ag("Tratador")

    def fake(agente, cinto, entrada, **kwargs):
        f = dict(kwargs.get("ficha") or {})
        if agente.nome == "Tratador":
            vistas.append(f.get("linha"))
            return {"saida": "ok", "instrumentos_acionados": [], "uso": [],
                    "ramos_escolhidos": [], "anotacoes": {}}
        return {"saida": "ok", "instrumentos_acionados": [], "uso": [],
                "ramos_escolhidos": [], "anotacoes": {"pedidos": '["x", "y"]'}}

    monkeypatch.setattr(motor, "executar_agente", fake)
    motor.executar_cadeia(sessao, _com_cada(a, b, item_em="linha"), "vai")
    assert vistas == ["x", "y"]


def test_cada_acumula_na_ficha(sessao, dados, ag, monkeypatch):
    a, b = ag("Apurador"), ag("Tratador")

    def fake(agente, cinto, entrada, **kwargs):
        f = dict(kwargs.get("ficha") or {})
        if agente.nome == "Tratador":
            return {"saida": f"feito:{f.get('item')}", "instrumentos_acionados": [],
                    "uso": [], "ramos_escolhidos": [], "anotacoes": {}}
        return {"saida": "ok", "instrumentos_acionados": [], "uso": [],
                "ramos_escolhidos": [], "anotacoes": {"pedidos": "A\nB"}}

    monkeypatch.setattr(motor, "executar_agente", fake)
    r = motor.executar_cadeia(
        sessao, _com_cada(a, b, acumular_em="relatorio"), "vai"
    )
    assert "feito:A" in r["ficha"]["relatorio"]
    assert "feito:B" in r["ficha"]["relatorio"]


def test_repeticoes_nao_se_fundem_na_juncao(sessao, dados, ag, monkeypatch):
    """A junção implícita (Onda 1) vale DENTRO de um ramo. Duas repetições que caem no
    mesmo nó são trabalhos distintos e NÃO podem virar um passo só — senão o for-each
    processaria os itens todos de uma vez, que é o oposto do que ele existe para fazer."""
    a, b = ag("Apurador"), ag("Tratador")

    def fake(agente, cinto, entrada, **kwargs):
        if agente.nome == "Tratador":
            return {"saida": "t", "instrumentos_acionados": [], "uso": [],
                    "ramos_escolhidos": [], "anotacoes": {}}
        return {"saida": "ok", "instrumentos_acionados": [], "uso": [],
                "ramos_escolhidos": [], "anotacoes": {"pedidos": "A\nB\nC\nD"}}

    monkeypatch.setattr(motor, "executar_agente", fake)
    r = motor.executar_cadeia(sessao, _com_cada(a, b), "vai")
    assert sum(1 for p in r["passos"] if p["no_id"] == "trat") == 4


def test_cada_com_lista_ausente_avisa(sessao, dados, ag, monkeypatch):
    a, b = ag("Apurador"), ag("Tratador")
    _mock(monkeypatch)  # ninguém anota "pedidos"
    r = motor.executar_cadeia(sessao, _com_cada(a, b), "vai")
    assert "não está na ficha" in r["avisos"][0]
    assert all(p["no_id"] != "trat" for p in r["passos"])


def test_cada_corta_acima_do_teto_e_diz(sessao, dados, ag, monkeypatch):
    """Corte silencioso é proibido: o rastro diz quantos ficaram de fora (§12-A)."""
    a, b = ag("Apurador"), ag("Tratador")
    n = motor.MAX_ITENS_CADA + 3

    def fake(agente, cinto, entrada, **kwargs):
        if agente.nome == "Tratador":
            return {"saida": "t", "instrumentos_acionados": [], "uso": [],
                    "ramos_escolhidos": [], "anotacoes": {}}
        return {"saida": "ok", "instrumentos_acionados": [], "uso": [],
                "ramos_escolhidos": [],
                "anotacoes": {"pedidos": "\n".join(f"i{k}" for k in range(n))}}

    monkeypatch.setattr(motor, "executar_agente", fake)
    r = motor.executar_cadeia(sessao, _com_cada(a, b), "vai")
    assert "3 últimos NÃO foram processados" in r["avisos"][0]
    assert sum(1 for p in r["passos"] if p["no_id"] == "trat") == motor.MAX_ITENS_CADA


def test_cada_sem_lista_nao_salva(sessao, dados, ag):
    a, b = ag("Apurador"), ag("Tratador")
    cadeia = _com_cada(a, b, lista="")
    with pytest.raises(ValueError, match="repete uma lista, mas não diz QUAL"):
        motor.validar_cadeia(cadeia, {str(a.id), str(b.id)})


# --- A ficha atravessa a espera por uma pessoa -----------------------------------


def _cenario_pausado(sessao, dados, ag):
    """Uma execução parada num pedido de aprovação, com ficha já preenchida."""
    rev, carr = ag("Revisor"), ag("Carrossel")
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(rev.id), "saidas": [
                {"rotulo": "aprovado", "quando": "aprovou", "destino": "carr"},
                {"rotulo": "reprovado", "quando": "pediu ajuste", "destino": "fim"},
            ]},
            {"id": "carr", "tipo": "agente", "ref": str(carr.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Posts", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=cadeia, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    execucao = Execucao(
        automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"},
        dados={"entrada": '"titulo": "Simples Nacional"', "capa": "https://img/1.png"},
    )
    sessao.add(execucao)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=execucao.id, ordem=1, agente_id=rev.id, no_id="rev",
            entrada={"texto": "rascunho"},
            saida={"texto": "CAPA", "instrumentos_acionados": [],
                   "saida_escolhida": None, "uso": []},
            estado="concluido",
        )
    )
    sessao.flush()
    return auto, execucao, cadeia


def test_ficha_sobrevive_a_aprovacao(sessao, dados, ag, monkeypatch):
    """A cena exata de 2026-09-01: a pessoa aprova, o agente responde só "Aprovado" — e
    o nó seguinte PRECISA continuar com o título e a capa. Antes chegava lá só o
    transcript da conversa."""
    auto, execucao, cadeia = _cenario_pausado(sessao, dados, ag)
    recebido: dict = {}

    def fake_agente(agente, cinto, entrada, **kwargs):
        recebido["ficha_do_portao"] = dict(kwargs.get("ficha") or {})
        return {
            "saida": "Aprovado. Seguindo.", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramos_escolhidos": ["aprovado"],
            "anotacoes": {"decisao": "aprovado"},
        }

    def fake_cadeia(sessao_, cadeia_, entrada, **kwargs):
        recebido["ficha_pos_portao"] = dict(kwargs.get("ficha") or {})
        return {"estado": "concluida", "resultado": "pronto", "ordem": 5,
                "passos": [], "avisos": [], "ficha": kwargs.get("ficha") or {}}

    monkeypatch.setattr(retoma, "executar_agente", fake_agente)
    monkeypatch.setattr(retoma, "executar_cadeia", fake_cadeia)
    retoma.retomar_execucao(sessao, execucao, "Aprovado", chaves={}, origens={})

    # O agente do portão viu a ficha…
    assert recebido["ficha_do_portao"]["capa"] == "https://img/1.png"
    # …e o trecho PÓS-aprovação também, já com o que ele anotou na retomada.
    pos = recebido["ficha_pos_portao"]
    assert '"titulo": "Simples Nacional"' in pos["entrada"]
    assert pos["capa"] == "https://img/1.png"
    assert pos["decisao"] == "aprovado"
    assert execucao.dados["decisao"] == "aprovado"


# --- A ferramenta `anotar` só existe onde há ficha --------------------------------


def _fake_app(monkeypatch, tools: list, conteudos: list, anotar_com: dict | None = None):
    """Mocka o `create_agent`, capturando as ferramentas e a mensagem do turno. Se
    `anotar_com` vier, o agente falso CHAMA a ferramenta `anotar` durante o turno."""
    class App:
        def invoke(self, estado, config=None):
            conteudos.append(estado["messages"][0]["content"])
            if anotar_com:
                f = next(t for t in tools if t.name == "anotar")
                for campo, valor in anotar_com.items():
                    f.func(campo=campo, valor=valor)
            return {"messages": [AIMessage(content="ok")]}

    def fake_create(modelo, ferramentas, system_prompt=None, **kw):
        tools.extend(ferramentas)
        return App()

    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m, **k: object())
    monkeypatch.setattr(agente_mod, "create_agent", fake_create)


def test_conversa_nao_ganha_anotar(sessao, dados, ag, monkeypatch):
    """No atendimento por mensageria não há execução nem ficha — e o agente não pode
    ganhar uma ferramenta que não teria onde escrever."""
    tools: list = []
    conteudos: list = []
    _fake_app(monkeypatch, tools, conteudos)
    agente_mod.executar_agente(ag("Atendente"), [], "oi")
    assert all(f.name != "anotar" for f in tools)
    assert conteudos == ["oi"]  # entrada intacta, sem bloco de ficha


def test_orquestracao_ganha_anotar_e_ve_a_ficha(sessao, dados, ag, monkeypatch):
    tools: list = []
    conteudos: list = []
    _fake_app(monkeypatch, tools, conteudos, anotar_com={"Total do Pedido": "1240"})
    r = agente_mod.executar_agente(
        ag("Passo"), [], "faça isso", ficha={"entrada": "pedido 42"}
    )
    assert "pedido 42" in conteudos[0]
    assert conteudos[0].endswith("faça isso")   # a ficha vem ANTES da entrada
    assert r["anotacoes"] == {"total_do_pedido": "1240"}  # nome já canônico


# --- O módulo puro ---------------------------------------------------------------


@pytest.mark.parametrize(
    "atual,op,valor,valor2,esperado",
    [
        ("10", "entre", "1", "10", True),      # inclusivo na ponta de cima
        ("1", "entre", "1", "10", True),       # e na de baixo
        ("11", "entre", "1", "10", False),
        ("1.234,56", "maior", "1000", None, True),   # número em pt-BR
        ("R$ 1.234,56", "menor", "2000", None, True),
        ("SIM", "igual", "sim", None, True),          # sem caixa
        ("São Paulo", "igual", "sao paulo", None, True),  # sem acento
        ("10,00", "igual", "10", None, True),          # mesmo número, outra grafia
        ("abc", "contem", "B", None, True),
        ("", "preenchido", None, None, False),
        ("x", "preenchido", None, None, True),
        ("texto", "maior", "10", None, None),          # indecidível
    ],
)
def test_operadores(atual, op, valor, valor2, esperado):
    regra = {"campo": "c", "operador": op}
    if valor is not None:
        regra["valor"] = valor
    if valor2 is not None:
        regra["valor2"] = valor2
    assert ficha_mod.avaliar_regra(regra, {"c": atual}) is esperado


def test_campo_ausente_e_decidivelmente_falso():
    regra = {"campo": "total", "operador": "maior", "valor": "10"}
    assert ficha_mod.avaliar_regra(regra, {}) is False


def test_regra_mal_formada_e_indecidivel():
    assert ficha_mod.avaliar_regra({"campo": "x"}, {"x": "1"}) is None
    assert ficha_mod.avaliar_regra({"operador": "igual", "valor": "1"}, {}) is None
    assert ficha_mod.avaliar_regra(None, {}) is None


def test_nome_de_campo_e_canonico():
    assert ficha_mod.normalizar_nome("Total do Pedido") == "total_do_pedido"
    assert ficha_mod.normalizar_nome("  Ação/Nº 3 ") == "acao_no_3"
    assert ficha_mod.normalizar_nome("!!") == ""


def test_teto_de_campos_nao_derruba_nada():
    f = {f"c{i}": "v" for i in range(ficha_mod.MAX_CAMPOS)}
    nome, _ = ficha_mod.anotar(f, "estoura", "x")
    assert nome == ""                       # recusado…
    assert len(f) == ficha_mod.MAX_CAMPOS   # …sem quebrar nem crescer
    # …mas ATUALIZAR um campo que já existe continua valendo.
    nome, substituiu = ficha_mod.anotar(f, "c0", "novo")
    assert (nome, substituiu) == ("c0", True)


def test_bloco_do_prompt_diz_que_o_dado_atravessa():
    texto = ficha_mod.para_o_prompt({"entrada": "pedido 42"})
    assert "atravessam a automação INTEIRA" in texto
    assert "pedido 42" in texto
    assert "anotar" in texto


def test_descricao_da_regra_em_portugues():
    assert ficha_mod.descrever_regra(
        {"campo": "Total", "operador": "entre", "valor": "1", "valor2": "10"}
    ) == "total está entre 1 e 10"
