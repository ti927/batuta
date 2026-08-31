"""A borda depois da Onda 1: retomada com fan-out, pendências e aviso de falha.

Três coisas que o motor sozinho não garante:
- ao aprovar um portão, o fluxo anda por TODOS os caminhos que o agente liberou;
- os ramos que ficaram esperando (`execucoes.pendencias`) voltam a rodar na retomada;
- quando uma execução falha, alguém é AVISADO (§12-A / PRODUTO §16) — e, se não houver
  canal para avisar, isso vira evento no banco de logs, nunca silêncio.

`executar_agente`/`executar_cadeia` e o envio pelo Telegram são mockados — sem LLM, sem rede.
"""

from mensageria import aviso, retoma
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    Execucao,
    Instrumento,
    PassoExecucao,
    Time,
)
from orquestracao import grafo

NO_GATE = "rev"


def _cenario(sessao, dados):
    """Portão que bifurca em dois destinos com a MESMA condição (o caso do maestro)."""
    rev = Agente(time_id=dados["timeA"].id, nome="Revisor", papel="agente")
    carr = Agente(time_id=dados["timeA"].id, nome="Carrossel", papel="agente")
    story = Agente(time_id=dados["timeA"].id, nome="Story", papel="agente")
    sessao.add_all([rev, carr, story])
    sessao.flush()
    cadeia = {
        "inicial": NO_GATE,
        "nos": [
            {"id": NO_GATE, "tipo": "agente", "ref": str(rev.id), "gate": True,
             "saidas": [
                 {"rotulo": "aprovado1", "quando": "aprovou a capa", "destino": "carr"},
                 {"rotulo": "aprovado2", "quando": "aprovou a capa", "destino": "story"},
                 {"rotulo": "reprovado", "quando": "pediu ajuste", "destino": "fim"},
             ]},
            {"id": "carr", "tipo": "agente", "ref": str(carr.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "story", "tipo": "agente", "ref": str(story.id),
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
        automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"}
    )
    sessao.add(execucao)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=execucao.id, ordem=1, agente_id=rev.id, no_id=NO_GATE,
            entrada={"texto": "rascunho"},
            saida={"texto": "CAPA", "instrumentos_acionados": [],
                   "saida_escolhida": None, "uso": []},
            estado="concluido",
        )
    )
    sessao.flush()
    return auto, execucao, cadeia


def test_aprovar_alimenta_os_dois_ramos(sessao, dados, monkeypatch):
    """Aprovar UMA vez faz o Carrossel E o Story rodarem — o bug que custou meses."""
    auto, execucao, cadeia = _cenario(sessao, dados)

    def fake_agente(agente, cinto, entrada, **kwargs):
        return {
            "saida": "aprovado!", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {},
            "ramos_escolhidos": ["aprovado1", "aprovado2"],
        }

    rodados: list = []

    def fake_cadeia(sessao_, cadeia_, entrada, **kwargs):
        rodados.append(kwargs.get("frente_inicial"))
        return {"estado": "concluida", "resultado": "pronto", "ordem": 5,
                "passos": [], "avisos": []}

    monkeypatch.setattr(retoma, "executar_agente", fake_agente)
    monkeypatch.setattr(retoma, "executar_cadeia", fake_cadeia)
    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    assert rodados, "a cadeia pós-portão não rodou"
    assert [i["no"] for i in rodados[0]] == ["carr", "story"]


def test_pendencias_voltam_na_retomada(sessao, dados, monkeypatch):
    """Ramos que ficaram esperando quando o portão pausou não somem."""
    auto, execucao, cadeia = _cenario(sessao, dados)
    execucao.pendencias = [{"no": "story", "entradas": ["texto do outro ramo"]}]
    sessao.flush()

    rodados: list = []

    def fake_cadeia(sessao_, cadeia_, entrada, **kwargs):
        rodados.append(kwargs.get("frente_inicial"))
        return {"estado": "concluida", "resultado": "pronto", "ordem": 5,
                "passos": [], "avisos": []}

    monkeypatch.setattr(retoma, "executar_cadeia", fake_cadeia)
    idx = grafo.indexar(grafo.normalizar(cadeia))
    saida_carr = next(
        s for s in idx.no(NO_GATE)["saidas"] if s["rotulo"] == "aprovado1"
    )
    retoma.avancar_apos_gate(
        sessao, execucao, idx=idx, cadeia=grafo.normalizar(cadeia),
        escolhidas=[saida_carr], entrada_proxima="CAPA", ordem_inicial=1,
        chaves={}, origens={},
    )
    assert [i["no"] for i in rodados[0]] == ["carr", "story"]
    assert execucao.pendencias is None  # consumidas


# ── O aviso de falha (§12-A: nada morre em silêncio) ───────────────────────────


def _canal(sessao, dados, *, destinatario="123", no_cinto=True):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": destinatario},
    )
    sessao.add(inst)
    sessao.flush()
    if no_cinto:
        ag = Agente(time_id=dados["timeA"].id, nome="Atendente", papel="agente")
        sessao.add(ag)
        sessao.flush()
        sessao.add(AgenteInstrumento(agente_id=ag.id, instrumento_id=inst.id))
        sessao.flush()
    return inst


def _execucao_falha(sessao, dados):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Publicador", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=True, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(
        automacao_id=auto.id, estado="falhou",
        entrada={"texto": "x"}, resultado={"erro": "o WordPress recusou"},
    )
    sessao.add(ex)
    sessao.flush()
    return ex


def test_falha_avisa_pelo_canal_do_time(sessao, dados, monkeypatch):
    _canal(sessao, dados)
    ex = _execucao_falha(sessao, dados)
    enviados: list = []
    monkeypatch.setattr(
        aviso.segredos_instrumento, "decifrar", lambda s, i: {"token_bot": "T"}
    )
    monkeypatch.setattr(
        aviso.telegram, "enviar",
        lambda token, chat, texto: enviados.append((chat, texto)) or {"ok": True},
    )
    aviso.avisar_falha(sessao, ex, "o WordPress recusou")
    assert enviados, "ninguém foi avisado da falha"
    chat, texto = enviados[0]
    assert chat == "123"
    assert "Publicador" in texto and "o WordPress recusou" in texto
    assert "falhou" in texto.lower()


def test_falha_sem_canal_vira_evento(sessao, dados, monkeypatch):
    """Sem canal para avisar, o fail-safe não pode ser MUDO."""
    ex = _execucao_falha(sessao, dados)
    eventos: list = []
    monkeypatch.setattr(
        aviso, "registrar_evento", lambda **kw: eventos.append(kw)
    )
    aviso.avisar_falha(sessao, ex, "erro qualquer")
    assert [e["acao"] for e in eventos] == ["falha.sem_canal"]
    assert eventos[0]["nivel"] == "warning"


def test_aviso_nunca_derruba_o_caminho_de_erro(sessao, dados, monkeypatch):
    _canal(sessao, dados)
    ex = _execucao_falha(sessao, dados)
    eventos: list = []
    monkeypatch.setattr(
        aviso.segredos_instrumento, "decifrar",
        lambda s, i: (_ for _ in ()).throw(RuntimeError("cofre fora do ar")),
    )
    monkeypatch.setattr(aviso, "registrar_evento", lambda **kw: eventos.append(kw))
    aviso.avisar_falha(sessao, ex, "erro")  # não levanta
    assert [e["acao"] for e in eventos] == ["falha.aviso_quebrou"]


def test_conversa_nao_gera_aviso(sessao, dados, monkeypatch):
    """O rastro-sombra de um atendimento não é uma automação que quebrou."""
    ex = Execucao(
        automacao_id=None, modo="conversa", estado="falhou", entrada={"texto": "x"}
    )
    sessao.add(ex)
    sessao.flush()
    eventos: list = []
    monkeypatch.setattr(aviso, "registrar_evento", lambda **kw: eventos.append(kw))
    aviso.avisar_falha(sessao, ex, "erro")
    assert eventos == []


def test_texto_do_aviso_diz_o_que_fazer(sessao, dados):
    txt = aviso.montar_texto("Gerar Posts", "Publicador", "HTTP 413 do WordPress")
    assert "Gerar Posts" in txt
    assert "Publicador" in txt
    assert "HTTP 413" in txt
    assert "dispare de novo" in txt  # o que fazer, não só o que houve


def test_canal_sem_destinatario_nao_serve(sessao, dados, monkeypatch):
    _canal(sessao, dados, destinatario="", no_cinto=False)
    ex = _execucao_falha(sessao, dados)
    eventos: list = []
    monkeypatch.setattr(aviso, "registrar_evento", lambda **kw: eventos.append(kw))
    aviso.avisar_falha(sessao, ex, "erro")
    assert [e["acao"] for e in eventos] == ["falha.sem_canal"]


def test_canal_de_outro_time_nao_e_usado(sessao, dados, monkeypatch):
    """O canal de OUTRO time não avisa esta falha (não vaza entre clientes)."""
    outro_time = Time(organizacao_id=dados["orgB"].id, nome="Time B")
    sessao.add(outro_time)
    sessao.flush()
    sessao.add(
        Instrumento(
            time_id=outro_time.id, nome="Bot B", tipo="enviar_telegram",
            configuracao={"destinatario_padrao": "999"},
        )
    )
    sessao.flush()
    ex = _execucao_falha(sessao, dados)
    eventos: list = []
    monkeypatch.setattr(aviso, "registrar_evento", lambda **kw: eventos.append(kw))
    aviso.avisar_falha(sessao, ex, "erro")
    assert [e["acao"] for e in eventos] == ["falha.sem_canal"]
