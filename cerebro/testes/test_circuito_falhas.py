"""Onda 4, fatia 3 — o disjuntor: automação que falha sozinha 3× seguidas se desliga.

Lacuna 27. Até aqui cada falha avisava, mas ninguém somava as falhas: uma automação
agendada podia falhar todo dia, para sempre. Foi o susto de 2026-09-02, com cinco
automações de blog que disparam sozinhas.

O que estes testes fixam, além do caminho feliz, são as três fronteiras que separam um
disjuntor útil de um que atrapalha: disparo MANUAL não conta (tem gente olhando),
falha causada pelo PRÓPRIO Batuta não conta (deploy/vigia), e um SUCESSO no meio zera
a sequência. Mais o religamento, que precisa devolver as três chances.
"""

from datetime import datetime, timedelta, timezone

from modelos import Agente, Automacao, Execucao
from orquestracao import circuito, disparo, grafo

NO_1 = "n1"


def _automacao(sessao, dados, *, gatilho="agendamento", ativa=True):
    ag = Agente(time_id=dados["timeA"].id, nome="Redator", papel="agente")
    sessao.add(ag)
    sessao.flush()
    cadeia = grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": str(ag.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Post do blog", tipo_gatilho=gatilho,
        configuracao_gatilho={}, cadeia=cadeia, ativa=ativa, configuracao={},
    )
    sessao.add(auto)
    sessao.commit()
    return auto


def _execucao(sessao, auto, *, estado, origem="agendamento", nossa_culpa=False, minutos=0):
    """Uma execução já encerrada. `minutos` recua o `criado_em` para dar ORDEM
    determinística (o banco de testes usa clock_timestamp, mas ser explícito aqui
    torna o teste independente do relógio)."""
    ex = disparo.criar_execucao(sessao, auto, "roda", origem=origem)
    ex.estado = estado
    ex.criado_em = datetime.now(timezone.utc) - timedelta(minutes=minutos)
    resultado = {"erro": "quebrou"} if estado == "falhou" else {"texto": "ok"}
    if nossa_culpa:
        resultado = circuito.marcar_interrompida_pelo_batuta(resultado)
    ex.resultado = resultado
    sessao.commit()
    return ex


# ───────────────────────── a contagem ─────────────────────────


def test_tres_falhas_automaticas_seguidas_desligam_a_automacao(sessao, dados, monkeypatch):
    avisos = []
    monkeypatch.setattr(
        "mensageria.aviso.avisar_falha", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "mensageria.aviso.avisar_desligada",
        lambda s, e, auto, n: avisos.append((auto.nome, n)),
    )
    auto = _automacao(sessao, dados)
    _execucao(sessao, auto, estado="falhou", minutos=30)
    _execucao(sessao, auto, estado="falhou", minutos=20)
    ultima = _execucao(sessao, auto, estado="falhou", minutos=10)

    desligou = circuito.apos_falha(sessao, ultima, "quebrou")

    assert desligou is True
    sessao.refresh(auto)
    assert auto.ativa is False
    assert auto.desligada_por_falhas_em is not None
    assert avisos == [("Post do blog", 3)]


def test_duas_falhas_nao_bastam(sessao, dados, monkeypatch):
    monkeypatch.setattr("mensageria.aviso.avisar_falha", lambda *a, **k: None)
    auto = _automacao(sessao, dados)
    _execucao(sessao, auto, estado="falhou", minutos=20)
    ultima = _execucao(sessao, auto, estado="falhou", minutos=10)

    assert circuito.apos_falha(sessao, ultima, "quebrou") is False
    sessao.refresh(auto)
    assert auto.ativa is True
    assert auto.desligada_por_falhas_em is None


def test_um_sucesso_no_meio_zera_a_sequencia(sessao, dados, monkeypatch):
    monkeypatch.setattr("mensageria.aviso.avisar_falha", lambda *a, **k: None)
    auto = _automacao(sessao, dados)
    _execucao(sessao, auto, estado="falhou", minutos=40)
    _execucao(sessao, auto, estado="falhou", minutos=30)
    _execucao(sessao, auto, estado="concluida", minutos=20)  # o sucesso zera
    ultima = _execucao(sessao, auto, estado="falhou", minutos=10)

    assert circuito.falhas_seguidas(sessao, auto) == 1
    assert circuito.apos_falha(sessao, ultima, "quebrou") is False
    sessao.refresh(auto)
    assert auto.ativa is True


# ───────────────────── as fronteiras que protegem ─────────────────────


def test_disparo_manual_nao_conta_e_nunca_desliga(sessao, dados, monkeypatch):
    """Quem clicou está olhando a tela e vê a falha na hora. Desligar a automação por
    baixo dele, no meio de um teste, seria hostil."""
    monkeypatch.setattr("mensageria.aviso.avisar_falha", lambda *a, **k: None)
    auto = _automacao(sessao, dados)
    for m in (30, 20, 10):
        ultima = _execucao(sessao, auto, estado="falhou", origem="manual", minutos=m)

    assert circuito.falhas_seguidas(sessao, auto) == 0
    assert circuito.apos_falha(sessao, ultima, "quebrou") is False
    sessao.refresh(auto)
    assert auto.ativa is True


def test_falha_causada_pelo_proprio_batuta_nao_conta(sessao, dados, monkeypatch):
    """Reinício do servidor (deploy) e vigia de execuções presas. Sem esta exceção,
    três deploys em dias seguidos desligariam as automações do cliente."""
    monkeypatch.setattr("mensageria.aviso.avisar_falha", lambda *a, **k: None)
    auto = _automacao(sessao, dados)
    _execucao(sessao, auto, estado="falhou", nossa_culpa=True, minutos=30)
    _execucao(sessao, auto, estado="falhou", nossa_culpa=True, minutos=20)
    ultima = _execucao(sessao, auto, estado="falhou", minutos=10)

    assert circuito.falhas_seguidas(sessao, auto) == 1
    assert circuito.apos_falha(sessao, ultima, "quebrou") is False
    sessao.refresh(auto)
    assert auto.ativa is True


def test_falha_nossa_nao_interrompe_a_sequencia_das_falhas_de_verdade(sessao, dados):
    """Um deploy no meio de três falhas reais não pode "salvar" a automação: ele não
    conta, mas também não zera — senão bastaria um reinício para mascarar o defeito."""
    auto = _automacao(sessao, dados)
    _execucao(sessao, auto, estado="falhou", minutos=40)
    _execucao(sessao, auto, estado="falhou", minutos=30)
    _execucao(sessao, auto, estado="falhou", nossa_culpa=True, minutos=20)
    _execucao(sessao, auto, estado="falhou", minutos=10)

    assert circuito.falhas_seguidas(sessao, auto) == 3


def test_execucao_ainda_viva_nao_entra_na_conta(sessao, dados):
    """`aguardando_humano` ainda pode terminar bem — não é veredito."""
    auto = _automacao(sessao, dados)
    _execucao(sessao, auto, estado="falhou", minutos=30)
    _execucao(sessao, auto, estado="aguardando_humano", minutos=20)
    _execucao(sessao, auto, estado="falhou", minutos=10)

    assert circuito.falhas_seguidas(sessao, auto) == 2


# ───────────────────────── religar ─────────────────────────


def test_religar_pela_tela_zera_a_contagem(cliente, entrar, sessao, dados):
    """As DUAS portas que ligam uma automação têm de zerar: esta é a da interface
    (PUT /automacoes/{id}). Sem isso, religar a derrubaria na primeira falha."""
    entrar(dados["operador"])
    auto = _automacao(sessao, dados, ativa=False)
    auto.desligada_por_falhas_em = datetime.now(timezone.utc)
    sessao.commit()
    for m in (30, 20, 10):
        _execucao(sessao, auto, estado="falhou", minutos=m)
    assert circuito.falhas_seguidas(sessao, auto) == 3

    r = cliente.put(
        f"/automacoes/{auto.id}",
        json={
            "nome": auto.nome, "tipo_gatilho": "agendamento",
            "configuracao_gatilho": {}, "cadeia": auto.cadeia,
            "ativa": True, "configuracao": {},
        },
    )

    assert r.status_code == 200
    assert r.json()["desligada_por_falhas_em"] is None
    sessao.expire_all()
    auto_novo = sessao.get(Automacao, auto.id)
    assert auto_novo.ativa is True
    assert auto_novo.falhas_contam_desde is not None
    assert circuito.falhas_seguidas(sessao, auto_novo) == 0


def test_religar_pela_ia_zera_a_contagem(sessao, dados):
    """A outra porta: `criacao.servicos.ativar`, usada pela IA criadora e pelo MCP."""
    from criacao import servicos

    auto = _automacao(sessao, dados, ativa=False)
    for m in (30, 20, 10):
        _execucao(sessao, auto, estado="falhou", minutos=m)
    assert circuito.falhas_seguidas(sessao, auto) == 3

    servicos.ativar(sessao, auto)
    sessao.commit()

    assert auto.falhas_contam_desde is not None
    assert auto.desligada_por_falhas_em is None
    assert circuito.falhas_seguidas(sessao, auto) == 0


def test_automacao_ja_desligada_nao_e_desligada_de_novo(sessao, dados, monkeypatch):
    """Sem esta guarda, cada falha de uma automação já fora do ar mandaria um recado
    novo — o barulho que o disjuntor existe para calar."""
    monkeypatch.setattr("mensageria.aviso.avisar_falha", lambda *a, **k: None)
    chamou = []
    monkeypatch.setattr(
        "mensageria.aviso.avisar_desligada", lambda *a, **k: chamou.append(1)
    )
    auto = _automacao(sessao, dados, ativa=False)
    for m in (30, 20, 10):
        ultima = _execucao(sessao, auto, estado="falhou", minutos=m)

    assert circuito.apos_falha(sessao, ultima, "quebrou") is False
    assert chamou == []


# ───────────────────── o funil e a origem gravada ─────────────────────


def test_criar_execucao_grava_a_origem(sessao, dados):
    """A origem já existia, mas ia só para o banco de logs. O disjuntor precisa dela
    na própria execução — e o funil é único para os quatro gatilhos."""
    auto = _automacao(sessao, dados)
    for origem in ("manual", "agendamento", "webhook", "comentario_instagram"):
        ex = disparo.criar_execucao(sessao, auto, "x", origem=origem)
        assert sessao.get(Execucao, ex.id).origem == origem


def test_disjuntor_nunca_derruba_o_caminho_de_erro(sessao, dados, monkeypatch):
    """Quem chama `apos_falha` já está tratando uma falha: se o disjuntor quebrar, ele
    engole e registra — nunca propaga (§12-A)."""
    monkeypatch.setattr("mensageria.aviso.avisar_falha", lambda *a, **k: None)
    auto = _automacao(sessao, dados)
    ultima = _execucao(sessao, auto, estado="falhou", minutos=10)

    def explode(*a, **k):
        raise RuntimeError("o banco caiu")

    monkeypatch.setattr(circuito, "falhas_seguidas", explode)

    assert circuito.apos_falha(sessao, ultima, "quebrou") is False


def test_rastro_de_conversa_fica_fora(sessao, dados, monkeypatch):
    """O modo `conversa` é o rastro-sombra de um atendimento, não uma automação."""
    monkeypatch.setattr("mensageria.aviso.avisar_falha", lambda *a, **k: None)
    auto = _automacao(sessao, dados)
    ex = _execucao(sessao, auto, estado="falhou", minutos=10)
    ex.modo = "conversa"
    sessao.commit()

    assert circuito.apos_falha(sessao, ex, "quebrou") is False
    sessao.refresh(auto)
    assert auto.ativa is True


def test_texto_do_recado_diz_o_que_houve_e_o_que_fazer(sessao):
    from mensageria.aviso import montar_texto_desligada

    texto = montar_texto_desligada("Post do blog", 3, "Revisor de SEO")

    assert "Post do blog" in texto
    assert "3 vezes seguidas" in texto
    assert "Revisor de SEO" in texto
    assert "religar" in texto  # o que fazer, nunca só o que houve
