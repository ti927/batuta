"""Diagnóstico de execução (`diagnostico_execucao.diagnosticar`) — leitura pura.

Um teste por cenário/aviso. Sem LLM: monta Execucao/PassoExecucao/Instrumento/
AgenteInstrumento/segredos direto na sessão e confere os `codigo` dos avisos. O caso
real (webhook blog→Instagram, portão que não avisou) é o `test_caso_real_completo`.
"""

import json
from datetime import datetime, timedelta, timezone

import diagnostico_execucao as diag
import segredos_instrumento as si
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    Conversa,
    Execucao,
    Instrumento,
    PassoExecucao,
    Time,
)

AGORA = datetime.now(timezone.utc)


# ───────────────────────────── construtores ─────────────────────────────

def _agente(sessao, dados, nome, time=None):
    ag = Agente(time_id=(time or dados["timeA"]).id, nome=nome, papel="agente")
    sessao.add(ag)
    sessao.flush()
    return ag


def _instr(sessao, dados, nome, tipo, *, time=None, cfg=None, token=None):
    inst = Instrumento(
        time_id=(time or dados["timeA"]).id, nome=nome, tipo=tipo, configuracao=cfg or {}
    )
    sessao.add(inst)
    sessao.flush()
    if token:
        si.salvar_segredos(sessao, inst.id, token)
    return inst


def _encaixar(sessao, agente, inst):
    sessao.add(AgenteInstrumento(agente_id=agente.id, instrumento_id=inst.id))
    sessao.flush()


def _auto(sessao, dados, *, nome="Fluxo", cadeia=None, gatilho="manual", time=None):
    auto = Automacao(
        time_id=(time or dados["timeA"]).id, nome=nome, tipo_gatilho=gatilho,
        configuracao_gatilho={}, cadeia=cadeia or {}, ativa=True,
    )
    sessao.add(auto)
    sessao.flush()
    return auto


def _exec(sessao, auto, estado, *, resultado=None, criado=None, iniciada=None):
    ex = Execucao(
        automacao_id=auto.id, estado=estado, entrada={"texto": "rode"},
        resultado=resultado, iniciada_em=iniciada,
    )
    sessao.add(ex)
    sessao.flush()
    if criado is not None:
        ex.criado_em = criado
        sessao.flush()
    return ex


def _passo(sessao, ex, *, ordem=1, agente=None, no_id=None, texto="ok", acionados=None,
           finalizado=None):
    p = PassoExecucao(
        execucao_id=ex.id, ordem=ordem, agente_id=(agente.id if agente else None),
        no_id=no_id, entrada={"texto": "x"},
        saida={"texto": texto, "instrumentos_acionados": acionados or []},
        estado="concluido", finalizado_em=finalizado,
    )
    sessao.add(p)
    sessao.flush()
    return p


def _cadeia_gate(ref, *, canal_id=None, dest="fim"):
    no = {"id": "n1", "tipo": "agente", "ref": str(ref), "gate": True,
          "saidas": [{"rotulo": "aprovado", "destino": dest},
                     {"rotulo": "reprovado", "destino": "n1"}]}
    if canal_id is not None:
        no["aprovacao"] = {"instrumento_id": str(canal_id), "destinatario": "555"}
    return {"inicial": "n1", "nos": [no, {"id": "fim", "tipo": "fim", "saidas": []}]}


def _codigos(d):
    return {a["codigo"] for a in d["avisos"]}


# ───────────────────────────── falhas ─────────────────────────────

def test_ia_sobrecarregada(sessao, dados):
    auto = _auto(sessao, dados)
    ex = _exec(sessao, auto, "falhou", resultado={
        "erro": "Error code: 529 - {'type':'error','error':{'type':'overloaded_error'}}"
    })
    _passo(sessao, ex)
    d = diag.diagnosticar(sessao, ex.id)
    assert "ia_sobrecarregada" in _codigos(d)
    assert d["avisos"][0]["severidade"] == "alerta"


def test_presa_orfa(sessao, dados):
    auto = _auto(sessao, dados)
    ex = _exec(sessao, auto, "falhou", resultado={
        "erro": "Execução travada (sem progresso além do tempo limite) — interrompida."
    })
    assert "presa_orfa" in _codigos(diag.diagnosticar(sessao, ex.id))


def test_falha_instrumento(sessao, dados):
    auto = _auto(sessao, dados)
    pub = _agente(sessao, dados, "Publicador")
    inst = _instr(sessao, dados, "Publicar", "publicar_wordpress")
    _encaixar(sessao, pub, inst)
    ex = _exec(sessao, auto, "falhou", resultado={
        "erro": "O instrumento 'Publicar' falhou: acesso negado por X (HTTP 403)."
    })
    _passo(sessao, ex, agente=pub, acionados=[f"Publicar_{inst.id.hex[:8]}"])
    d = diag.diagnosticar(sessao, ex.id)
    assert "falha_instrumento" in _codigos(d)
    a = next(a for a in d["avisos"] if a["codigo"] == "falha_instrumento")
    assert a["referencias"]["instrumento_id"] == str(inst.id)
    assert a["acao_sugerida"]["tipo"] == "editar_instrumento"


def test_falha_generica(sessao, dados):
    auto = _auto(sessao, dados)
    ex = _exec(sessao, auto, "falhou", resultado={"erro": "Cadeia inválida: nó X ausente."})
    assert "falha_generica" in _codigos(diag.diagnosticar(sessao, ex.id))


# ───────────────────────────── presas ─────────────────────────────

def test_em_andamento_sem_progresso(sessao, dados):
    auto = _auto(sessao, dados)
    ex = _exec(sessao, auto, "em_andamento", iniciada=AGORA - timedelta(minutes=25))
    assert "em_andamento_sem_progresso" in _codigos(diag.diagnosticar(sessao, ex.id))


def test_preso_aguardando(sessao, dados):
    auto = _auto(sessao, dados)
    ex = _exec(sessao, auto, "aguardando", criado=AGORA - timedelta(minutes=12))
    assert "preso_aguardando" in _codigos(diag.diagnosticar(sessao, ex.id))


# ───────────────────────────── portão ─────────────────────────────

def test_portao_sem_entrega_e_canal_sem_token(sessao, dados):
    """Caso real (a)+(b): o agente do portão NÃO tem canal no cinto e o canal de
    aprovação está sem token. Dois avisos de erro; o token nunca aparece no dict."""
    gate = _agente(sessao, dados, "Gerador de Imagem e Legenda")
    foto = _instr(sessao, dados, "FotoMontagem", "montar_imagem")
    _encaixar(sessao, gate, foto)  # só ferramenta de imagem, nenhum canal
    canal = _instr(sessao, dados, "Telegram_InstaBot", "enviar_telegram")  # SEM token
    auto = _auto(sessao, dados, cadeia=_cadeia_gate(gate.id, canal_id=canal.id))
    ex = _exec(sessao, auto, "aguardando_humano")
    _passo(sessao, ex, agente=gate, no_id="n1", texto="Aprova? ✅/❌", acionados=[])

    d = diag.diagnosticar(sessao, ex.id)
    cods = _codigos(d)
    assert "portao_sem_entrega" in cods and "canal_sem_token" in cods
    assert "aprovacao_pendente_normal" not in cods
    a = next(a for a in d["avisos"] if a["codigo"] == "portao_sem_entrega")
    assert a["acao_sugerida"]["tipo"] == "encaixar_instrumento"
    assert a["acao_sugerida"]["agente_id"] == str(gate.id)


def test_canal_sem_token_nao_vaza_o_segredo(sessao, dados):
    gate = _agente(sessao, dados, "G")
    canal = _instr(sessao, dados, "Bot", "enviar_telegram", token={"token_bot": "SEGREDO-123"})
    _encaixar(sessao, gate, canal)
    auto = _auto(sessao, dados, cadeia=_cadeia_gate(gate.id, canal_id=canal.id))
    ex = _exec(sessao, auto, "aguardando_humano")
    _passo(sessao, ex, agente=gate, no_id="n1", acionados=[])  # não enviou nesta rodada
    d = diag.diagnosticar(sessao, ex.id)
    # canal TEM token → não dispara canal_sem_token; e o valor nunca aparece.
    assert "canal_sem_token" not in _codigos(d)
    assert "SEGREDO-123" not in json.dumps(d, ensure_ascii=False)


def test_aprovacao_pendente_normal(sessao, dados):
    gate = _agente(sessao, dados, "Revisor")
    canal = _instr(sessao, dados, "Bot", "enviar_telegram", token={"token_bot": "tok"})
    _encaixar(sessao, gate, canal)
    auto = _auto(sessao, dados, cadeia=_cadeia_gate(gate.id, canal_id=canal.id))
    ex = _exec(sessao, auto, "aguardando_humano")
    # o agente ACIONOU o canal nesta rodada (entregou o pedido).
    _passo(sessao, ex, agente=gate, no_id="n1", acionados=[f"Bot_{canal.id.hex[:8]}"])
    sessao.add(Conversa(
        instrumento_id=canal.id, contato_chave="555", estado="aguardando_resposta",
        execucao_id=ex.id,
    ))
    sessao.flush()
    cods = _codigos(diag.diagnosticar(sessao, ex.id))
    assert "aprovacao_pendente_normal" in cods
    assert "portao_sem_entrega" not in cods and "canal_sem_token" not in cods


def test_portao_so_tela(sessao, dados):
    gate = _agente(sessao, dados, "Revisor")
    auto = _auto(sessao, dados, cadeia=_cadeia_gate(gate.id, canal_id=None))  # sem canal
    ex = _exec(sessao, auto, "aguardando_humano")
    _passo(sessao, ex, agente=gate, no_id="n1", acionados=[])
    assert "portao_so_tela" in _codigos(diag.diagnosticar(sessao, ex.id))


# ───────────────────────────── webhook hop ─────────────────────────────

def _montar_hop(sessao, dados, *, time_alvo=None):
    """Source (blog) dispara webhook p/ a automação-alvo (Instagram), cuja execução
    parou num portão que não avisou. Devolve (exec_origem, auto_alvo)."""
    time_alvo = time_alvo or dados["timeA"]
    # alvo: automação webhook com portão sem entrega + canal sem token
    gate = _agente(sessao, dados, "Gerador Insta", time=time_alvo)
    _encaixar(sessao, gate, _instr(sessao, dados, "Foto", "montar_imagem", time=time_alvo))
    canal = _instr(sessao, dados, "InstaBot", "enviar_telegram", time=time_alvo)
    auto_alvo = _auto(sessao, dados, nome="Webhook Insta", gatilho="webhook",
                      cadeia=_cadeia_gate(gate.id, canal_id=canal.id), time=time_alvo)
    ex_alvo = _exec(sessao, auto_alvo, "aguardando_humano")
    _passo(sessao, ex_alvo, agente=gate, no_id="n1", acionados=[])
    # origem: blog, Publicador dispara o webhook para a URL da auto_alvo
    pub = _agente(sessao, dados, "Publicador")
    url = f"https://api.batuta.team/webhooks/automacoes/{auto_alvo.id}"
    wh = _instr(sessao, dados, "Disparar Insta", "disparar_webhook", cfg={"url": url})
    _encaixar(sessao, pub, wh)
    auto_origem = _auto(sessao, dados, nome="Blog")
    ex_origem = _exec(sessao, auto_origem, "concluida", resultado={"texto": "Publicado."})
    _passo(sessao, ex_origem, agente=pub, texto="Webhook disparado",
           acionados=[f"Disparar_Insta_{wh.id.hex[:8]}"])
    return ex_origem, auto_alvo


def test_caso_real_completo(sessao, dados):
    """O webhook iniciou a execução-alvo, que parou num portão que não avisou —
    a origem concluiu, mas o diagnóstico segue até a causa real lá no alvo."""
    ex_origem, _ = _montar_hop(sessao, dados)
    d = diag.diagnosticar(sessao, ex_origem.id)
    assert "webhook_disparou_alvo" in _codigos(d)
    alvo = d["webhook_alvo"]
    assert alvo and not alvo["fora_de_alcance"]
    assert alvo["mesmo_time"] is True
    cods_alvo = {a["codigo"] for a in alvo["execucao_alvo"]["avisos"]}
    assert "portao_sem_entrega" in cods_alvo and "canal_sem_token" in cods_alvo
    # o aviso de origem herda gravidade do alvo (erro lá → alerta aqui).
    a = next(a for a in d["avisos"] if a["codigo"] == "webhook_disparou_alvo")
    assert a["severidade"] == "alerta"


def test_webhook_outra_org_fora_de_alcance(sessao, dados):
    # automação-alvo num time de OUTRA organização (orgB)
    time_b = Time(organizacao_id=dados["orgB"].id, nome="Time B")
    sessao.add(time_b)
    sessao.flush()
    ex_origem, _ = _montar_hop(sessao, dados, time_alvo=time_b)
    d = diag.diagnosticar(sessao, ex_origem.id)
    alvo = d["webhook_alvo"]
    assert alvo["fora_de_alcance"] is True
    assert alvo["execucao_alvo"] is None
    # nunca expõe avisos/segredos da outra organização
    assert "portao_sem_entrega" not in json.dumps(d, ensure_ascii=False)


# ───────────────────────────── truncagem ─────────────────────────────

def test_textos_longos_truncados(sessao, dados):
    auto = _auto(sessao, dados)
    ex = _exec(sessao, auto, "concluida", resultado={"texto": "ok"})
    _passo(sessao, ex, texto="x" * 5000)
    d = diag.diagnosticar(sessao, ex.id)
    resumo = d["passos"][-1]["saida_resumo"]
    assert len(resumo) <= diag.MAX_TRECHO + 30 and "…" in resumo
