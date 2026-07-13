"""Portão de aprovação carrega adiante o que foi APRESENTADO ao humano.

Conserto 2026-06-18 (execução `7f020c5a`): ao pausar num portão, o conteúdo que
segue — e o que é persistido no passo — deixa de ser o status que o agente narra
("Enviei para aprovação, aguardando…") e passa a ser a mensagem que o agente
enviou pelo canal de aprovação, ou seja, o que a pessoa de fato viu. Sem isto o
conteúdo aprovado se perdia (o artigo ficava só no Telegram) e o próximo agente
recebia só "aviso + aprovado".

Cobre os três níveis:
- agente: a captura por canal (`_ferramenta_unica` registra a mensagem enviada);
- cadeia: o portão usa a mensagem apresentada (com canal configurado, com
  fallback sem config, e portão só de tela mantém o texto do agente);
- retomada: o conteúdo apresentado + a resposta seguem para o próximo nó.
"""

import uuid

import instrumentos as encaixe
import orquestracao.agente as agente_mod
import orquestracao.cadeia as motor
from mensageria import retoma
from modelos import Agente, Automacao, Execucao, Instrumento, PassoExecucao


# ───────────────────── nível do agente: a captura por canal ─────────────────────

def test_envio_por_canal_registra_a_mensagem_apresentada(monkeypatch):
    tg = encaixe.obter_tipo("enviar_telegram")
    inst = Instrumento(
        time_id=uuid.uuid4(), nome="Canal", tipo="enviar_telegram",
        configuracao={"token_bot": "x"},
    )
    inst.id = uuid.uuid4()
    # Não falamos com o Telegram de verdade: o acionar devolve sucesso.
    monkeypatch.setattr(
        agente_mod, "acionar_com_retentativa", lambda t, c, a: {"ok": True, "status": 200}
    )
    enviadas: dict[str, list[str]] = {}
    tool = agente_mod._ferramenta_unica(
        inst, tg, tg.Config.model_validate({"token_bot": "x"}), [], enviadas, []
    )
    tool.func(destinatario="123", mensagem="ARTIGO COMPLETO REVISADO")
    assert enviadas == {str(inst.id): ["ARTIGO COMPLETO REVISADO"]}


def test_instrumento_sem_campo_mensagem_nao_registra(monkeypatch):
    # busca_web não apresenta mensagem a humano (campo_mensagem None) → nada a carregar.
    busca = encaixe.obter_tipo("busca_web")
    inst = Instrumento(
        time_id=uuid.uuid4(), nome="Busca", tipo="busca_web", configuracao={}
    )
    inst.id = uuid.uuid4()
    monkeypatch.setattr(
        agente_mod, "acionar_com_retentativa", lambda t, c, a: {"resultados": []}
    )
    enviadas: dict[str, list[str]] = {}
    tool = agente_mod._ferramenta_unica(inst, busca, busca.Config(), [], enviadas, [])
    tool.func(consulta="reforma tributária")
    assert enviadas == {}


# ───────────────────── nível da cadeia: o portão usa o apresentado ─────────────────────

def _ag(sessao, dados, nome):
    a = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
    sessao.add(a)
    sessao.flush()
    return a


def _mock_executar(monkeypatch, *, saida, mensagens_enviadas):
    def fake(agente, cinto, entrada, **kwargs):
        return {
            "saida": saida,
            "instrumentos_acionados": [],
            "uso": [],
            "mensagens_enviadas": mensagens_enviadas,
            "ramo_escolhido": None,
        }
    monkeypatch.setattr(motor, "executar_agente", fake)


def test_portao_carrega_a_mensagem_do_canal_de_aprovacao(sessao, dados, monkeypatch):
    rev = _ag(sessao, dados, "Revisor")
    canal_id = str(uuid.uuid4())
    _mock_executar(
        monkeypatch,
        saida="Enviei para aprovação. Aguardando retorno.",  # o status (ruído)
        mensagens_enviadas={canal_id: ["ARTIGO COMPLETO REVISADO"]},
    )
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(rev.id), "gate": True,
             "aprovacao": {"instrumento_id": canal_id, "destinatario": "999"},
             "saidas": [
                 {"rotulo": "aprovado", "destino": "fim"},
                 {"rotulo": "reprovado", "destino": "rev"},
             ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["estado"] == "aguardando_humano"
    # o que segue (pergunta) E o que é persistido no passo = o ARTIGO, não o status.
    assert r["pergunta"] == "ARTIGO COMPLETO REVISADO"
    assert r["passos"][-1]["saida"] == "ARTIGO COMPLETO REVISADO"


def test_portao_fallback_qualquer_canal_quando_sem_config(sessao, dados, monkeypatch):
    # Portão sem `aprovacao` no nó, mas o agente enviou por um canal → usa o enviado.
    rev = _ag(sessao, dados, "RevisorSemConfig")
    outro_canal = str(uuid.uuid4())
    _mock_executar(
        monkeypatch,
        saida="status irrelevante",
        mensagens_enviadas={outro_canal: ["O QUE A PESSOA VIU"]},
    )
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(rev.id), "gate": True,
             "saidas": [{"rotulo": "aprovado", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["pergunta"] == "O QUE A PESSOA VIU"


def test_portao_de_tela_mantem_o_texto_do_agente(sessao, dados, monkeypatch):
    # Sem envio por canal (aprovação só na tela): o que vale é o texto do agente.
    rev = _ag(sessao, dados, "RevisorTela")
    _mock_executar(monkeypatch, saida="Proposta exibida na tela", mensagens_enviadas={})
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(rev.id), "gate": True,
             "saidas": [{"rotulo": "aprovado", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    r = motor.executar_cadeia(sessao, cadeia, "vai")
    assert r["pergunta"] == "Proposta exibida na tela"


# ───────────────────── retomada ponta-a-ponta ─────────────────────

def test_retomada_entrega_o_conteudo_apresentado_mais_a_resposta(sessao, dados):
    """Com o passo do portão guardando o conteúdo apresentado (como a cadeia agora
    produz), retomar com 'aprovado' faz esse conteúdo + a resposta seguirem adiante."""
    ag = _ag(sessao, dados, "RevisorRetoma")
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(ag.id), "gate": True,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},  # destino fim → conclui
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=cadeia, ativa=False,
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
            execucao_id=execucao.id, ordem=1, agente_id=ag.id, no_id="rev",
            entrada={"texto": "x"},
            saida={
                "texto": "ARTIGO COMPLETO REVISADO",  # o que a cadeia agora carrega
                "instrumentos_acionados": [], "saida_escolhida": None, "uso": [],
            },
            estado="concluido",
        )
    )
    sessao.flush()

    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"
    texto = execucao.resultado["texto"]
    assert "ARTIGO COMPLETO REVISADO" in texto  # o conteúdo aprovado seguiu
    assert "aprovado" in texto  # com a resposta do humano anexada
