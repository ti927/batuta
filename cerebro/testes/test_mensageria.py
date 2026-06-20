"""Testes da camada de mensageria (Fase 1, modo conversacional).

Cobrem o roteamento (achar/criar a Conversa, gravar a thread, achar o agente
atendente pelo cinto), o filtro dos instrumentos de canal das ferramentas do
agente, e um turno completo com `executar_agente` e o envio mockados (sem bot
real). NÃO tocam o núcleo de orquestração.
"""

from datetime import datetime, timedelta, timezone

import segredos_instrumento as si
from sqlalchemy import select

from mensageria import servico, telegram
from modelos import (
    Agente,
    AgenteInstrumento,
    Conversa,
    Instrumento,
    MensagemConversa,
)


class _SessaoFake:
    """Proxy que reusa a sessão do teste (transação revertida ao fim) mas ignora
    o `close()` — assim o `processar_turno` (que abre a própria sessão) opera
    sobre os mesmos dados e o teste pode conferir o resultado depois."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def _bot(sessao, dados, nome="bot", configuracao=None):
    # Saudação de abertura DESLIGADA por padrão nos testes de turno (foco na
    # resposta da IA, sem a mensagem de boas-vindas no meio); os testes da Fase K
    # passam a config explícita para exercitar saudação/horário.
    inst = Instrumento(
        time_id=dados["timeA"].id,
        nome=nome,
        tipo="enviar_telegram",
        configuracao={"saudacao_abertura": ""} if configuracao is None else configuracao,
    )
    sessao.add(inst)
    sessao.flush()
    return inst


def _agente_com(sessao, dados, *instrumentos, nome="Atendente"):
    ag = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
    sessao.add(ag)
    sessao.flush()
    for inst in instrumentos:
        sessao.add(AgenteInstrumento(agente_id=ag.id, instrumento_id=inst.id))
    sessao.flush()
    return ag


def _msg(texto="oi", chave="555", nome="João"):
    return telegram.MensagemEntrante(
        contato_chave=chave, contato_nome=nome, texto=texto, midia=None
    )


# ───────────────────────── extrair_update (adaptador) ────────────────────────


def test_extrair_update_texto():
    m = telegram.extrair_update(
        {"message": {"chat": {"id": 555}, "from": {"first_name": "Ana"}, "text": "olá"}}
    )
    assert m and m.contato_chave == "555" and m.contato_nome == "Ana" and m.texto == "olá"


def test_extrair_update_voz_marca_midia():
    m = telegram.extrair_update(
        {"message": {"chat": {"id": 9}, "voice": {"file_id": "abc"}}}
    )
    assert m and m.texto is None
    assert m.midia == {"tipo": "voz", "file_id": "abc", "duracao_s": 0}


def test_extrair_update_ignora_nao_mensagem():
    assert telegram.extrair_update({"my_chat_member": {}}) is None
    assert telegram.extrair_update({}) is None


# ───────────────────────────── roteamento ────────────────────────────────────


def test_registrar_entrada_cria_conversa_e_roteia(sessao, dados):
    inst = _bot(sessao, dados)
    ag = _agente_com(sessao, dados, inst)

    conversa, deve = servico.registrar_entrada(sessao, inst, _msg("oi"))

    assert deve is True
    assert conversa.destino_tipo == "agente" and conversa.destino_id == ag.id
    assert conversa.estado == "bot_respondendo"
    assert conversa.contato_nome == "João"
    msgs = sessao.scalars(
        select(MensagemConversa).where(MensagemConversa.conversa_id == conversa.id)
    ).all()
    assert [(m.papel, m.conteudo) for m in msgs] == [("contato", "oi")]


def test_segunda_mensagem_reusa_a_mesma_conversa(sessao, dados):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    c1, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    c2, _ = servico.registrar_entrada(sessao, inst, _msg("tudo bem?"))
    assert c1.id == c2.id
    msgs = sessao.scalars(
        select(MensagemConversa)
        .where(MensagemConversa.conversa_id == c1.id)
        .order_by(MensagemConversa.criado_em)
    ).all()
    assert [m.conteudo for m in msgs] == ["oi", "tudo bem?"]


def test_sem_agente_atendente_nao_processa(sessao, dados):
    inst = _bot(sessao, dados)  # nenhum agente tem este instrumento no cinto
    conversa, deve = servico.registrar_entrada(sessao, inst, _msg("oi"))
    assert deve is False
    assert conversa.destino_id is None
    assert conversa.estado == "aberta"


def test_humano_assumiu_nao_processa(sessao, dados):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    conversa.estado = "humano_assumiu"
    sessao.commit()
    conversa2, deve = servico.registrar_entrada(sessao, inst, _msg("alguém aí?"))
    assert conversa2.id == conversa.id
    assert deve is False
    assert conversa2.estado == "humano_assumiu"


def test_cinto_sem_canais_filtra_o_instrumento_de_canal(sessao, dados):
    inst_canal = _bot(sessao, dados)
    inst_busca = Instrumento(
        time_id=dados["timeA"].id, nome="busca", tipo="busca_web", configuracao={}
    )
    sessao.add(inst_busca)
    sessao.flush()
    ag = _agente_com(sessao, dados, inst_canal, inst_busca)

    cinto = servico._cinto_sem_canais(sessao, ag.id)
    tipos = {i.tipo for i in cinto}
    assert tipos == {"busca_web"}  # o canal foi filtrado


# ─────────────────────────── turno completo (mock) ───────────────────────────


def test_processar_turno_envia_resposta_e_grava(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TOKEN"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("quanto custa?"))

    enviados = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico,
        "executar_agente",
        lambda ag, cinto, entrada, **k: {
            "saida": "Custa R$10.",
            "uso": [{"modelo": "haiku", "tokens_entrada": 1000, "tokens_saida": 500}],
        },
    )
    monkeypatch.setattr(
        servico.telegram,
        "enviar",
        lambda token, chat_id, texto: enviados.append((token, chat_id, texto)) or {"ok": True},
    )

    servico.processar_turno(conversa.id)

    assert enviados == [("TOKEN", "555", "Custa R$10.")]
    sessao.refresh(conversa)
    assert conversa.estado == "aguardando_resposta"
    assert conversa.turnos == 1
    assert float(conversa.custo_acumulado_usd) > 0  # custo do turno acumulado
    assert conversa.aguardando_ate is not None  # relógio da inatividade armado
    # (não ordeno por criado_em: no teste tudo roda numa transação, então now() é
    # constante e os timestamps empatam; em produção cada commit tem o seu.)
    do_agente = sessao.scalars(
        select(MensagemConversa).where(
            MensagemConversa.conversa_id == conversa.id,
            MensagemConversa.papel == "agente",
        )
    ).all()
    assert len(do_agente) == 1
    assert do_agente[0].conteudo == "Custa R$10." and do_agente[0].entregue


def test_debounce_aborta_quando_chega_msg_mais_nova(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))

    rodou = {"agente": False}
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico,
        "executar_agente",
        lambda *a, **k: rodou.__setitem__("agente", True) or {"saida": "x"},
    )
    monkeypatch.setattr(servico.telegram, "enviar", lambda *a: {"ok": True})

    # Durante a "espera" do debounce, simula a chegada de uma mensagem mais nova.
    def sleep_simula_msg_nova(_):
        c = sessao.get(Conversa, conversa.id)
        c.ultima_entrada_em = datetime.now(timezone.utc) + timedelta(seconds=30)
        sessao.commit()

    monkeypatch.setattr(servico.time, "sleep", sleep_simula_msg_nova)

    servico.processar_turno(conversa.id)

    assert rodou["agente"] is False  # abortou: não rodou o agente
    do_agente = sessao.scalars(
        select(MensagemConversa).where(
            MensagemConversa.conversa_id == conversa.id,
            MensagemConversa.papel == "agente",
        )
    ).all()
    assert do_agente == []


def test_teto_estourado_passa_para_humano(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    conversa.custo_acumulado_usd = 999  # já estourou o teto
    sessao.commit()

    rodou = {"agente": False}
    enviados = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico, "executar_agente", lambda *a: rodou.__setitem__("agente", True) or {"saida": "x"}
    )
    monkeypatch.setattr(
        servico.telegram, "enviar", lambda token, chat_id, texto: enviados.append(texto) or {"ok": True}
    )

    servico.processar_turno(conversa.id)

    assert rodou["agente"] is False  # não rodou a IA
    sessao.refresh(conversa)
    assert conversa.estado == "humano_assumiu"
    assert enviados == [servico.MSG_LIMITE]  # cortesia enviada ao contato


# ───────────────────────── áudio → texto (Fase H) ────────────────────────────


def test_voz_fica_sem_texto_ate_o_turno(sessao, dados):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    voz = telegram.MensagemEntrante("555", "João", None, {"tipo": "voz", "file_id": "F"})
    conversa, _ = servico.registrar_entrada(sessao, inst, voz)
    m = sessao.scalars(
        select(MensagemConversa).where(MensagemConversa.conversa_id == conversa.id)
    ).first()
    assert m.conteudo is None and (m.midia or {}).get("tipo") == "voz"


def test_audio_transcrito_entra_no_turno(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    voz = telegram.MensagemEntrante("555", "João", None, {"tipo": "voz", "file_id": "F"})
    conversa, _ = servico.registrar_entrada(sessao, inst, voz)

    entradas = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico, "resolver_chaves_por_time", lambda s, t: ({"openai": "K"}, {})
    )
    monkeypatch.setattr("mensageria.telegram.baixar_arquivo", lambda token, fid: b"audio")
    monkeypatch.setattr(
        "mensageria.transcricao.transcrever", lambda audio, chave, **kw: "Quero saber o preço"
    )
    monkeypatch.setattr(
        servico,
        "executar_agente",
        lambda ag, cinto, entrada, **k: entradas.append(entrada) or {"saida": "São R$10."},
    )
    monkeypatch.setattr(servico.telegram, "enviar", lambda *a: {"ok": True})

    servico.processar_turno(conversa.id)

    # a voz virou texto e entrou no enquadramento do turno
    assert entradas and "Quero saber o preço" in entradas[0]
    m = sessao.scalars(
        select(MensagemConversa).where(
            MensagemConversa.conversa_id == conversa.id,
            MensagemConversa.papel == "contato",
        )
    ).first()
    assert m.conteudo == "Quero saber o preço" and (m.midia or {}).get("transcrito") is True


# ───────────── contabilização: uso do turno carimbado por categoria ──────────


def test_processar_turno_grava_uso_com_origem_e_categoria(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TOKEN"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("quanto custa?"))

    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    # origens determinístico: a chamada do agente saiu da chave-mãe (consultoria).
    monkeypatch.setattr(
        servico,
        "resolver_chaves_por_time",
        lambda s, t: ({"anthropic": "K"}, {"anthropic": "consultoria"}),
    )
    monkeypatch.setattr(
        servico,
        "executar_agente",
        lambda ag, cinto, entrada, **k: {
            "saida": "Custa R$10.",
            "uso": [{"modelo": "claude-haiku-4-5", "tokens_entrada": 1000, "tokens_saida": 500}],
        },
    )
    monkeypatch.setattr(servico.telegram, "enviar", lambda *a: {"ok": True})

    servico.processar_turno(conversa.id)

    sessao.refresh(conversa)
    do_agente = sessao.scalars(
        select(MensagemConversa).where(
            MensagemConversa.conversa_id == conversa.id,
            MensagemConversa.papel == "agente",
        )
    ).all()
    assert len(do_agente) == 1
    uso = do_agente[0].uso
    assert uso and uso[0]["categoria"] == "mensageria"
    assert uso[0]["origem"] == "consultoria"  # carimbo da chave-mãe
    assert float(conversa.custo_acumulado_usd) > 0


def test_processar_turno_contabiliza_transcricao(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    voz = telegram.MensagemEntrante(
        "555", "João", None, {"tipo": "voz", "file_id": "F", "duracao_s": 120}
    )
    conversa, _ = servico.registrar_entrada(sessao, inst, voz)

    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico,
        "resolver_chaves_por_time",
        lambda s, t: ({"openai": "K"}, {"openai": "consultoria"}),
    )
    monkeypatch.setattr("mensageria.telegram.baixar_arquivo", lambda token, fid: b"audio")
    monkeypatch.setattr(
        "mensageria.transcricao.transcrever", lambda audio, chave, **kw: "Quero o preço"
    )
    monkeypatch.setattr(servico, "executar_agente", lambda *a, **k: {"saida": "R$10.", "uso": []})
    monkeypatch.setattr(servico.telegram, "enviar", lambda *a: {"ok": True})

    servico.processar_turno(conversa.id)

    do_agente = sessao.scalars(
        select(MensagemConversa).where(
            MensagemConversa.conversa_id == conversa.id,
            MensagemConversa.papel == "agente",
        )
    ).first()
    # 2 min de áudio → uma entrada de transcrição (categoria 'transcricao'), com
    # custo por minuto pré-calculado e origem da chave-mãe.
    transc = [e for e in (do_agente.uso or []) if e.get("categoria") == "transcricao"]
    assert len(transc) == 1
    assert transc[0]["origem"] == "consultoria"
    assert transc[0]["custo_usd"] == round(servico.precos.custo_whisper(120), 6)


# ───────────────────── inatividade: cutucar e encerrar (Fase J) ──────────────


def test_sweeper_cutuca_e_depois_encerra(sessao, dados, monkeypatch):
    from mensageria import sweeper

    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    # Simula: o bot já respondeu e o prazo de resposta venceu.
    conversa.estado = "aguardando_resposta"
    conversa.nudge_enviado = False
    conversa.aguardando_ate = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.commit()

    enviados = []
    monkeypatch.setattr(
        "mensageria.telegram.enviar",
        lambda t, c, x: enviados.append(x) or {"ok": True},
    )

    # 1ª varredura → cutuca (e rearma o prazo), sem encerrar.
    assert sweeper.varrer(sessao) == 1
    sessao.refresh(conversa)
    assert conversa.nudge_enviado is True
    assert conversa.estado == "aguardando_resposta"
    assert enviados[-1] == sweeper.NUDGE_MSG

    # Vence o prazo do nudge → 2ª varredura encerra.
    conversa.aguardando_ate = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.commit()
    assert sweeper.varrer(sessao) == 1
    sessao.refresh(conversa)
    assert conversa.estado == "fechada"
    assert enviados[-1] == sweeper.DESPEDIDA_MSG


# ─────────────────────── endpoint de entrada (HTTP) ──────────────────────────


def test_endpoint_entrada_agenda_turno(cliente, dados, sessao, monkeypatch):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    agendados = []
    monkeypatch.setattr(servico, "processar_turno", lambda cid: agendados.append(cid))

    r = cliente.post(
        f"/mensageria/{inst.id}/entrada",
        json={"message": {"chat": {"id": 777}, "from": {"first_name": "Zé"}, "text": "oi"}},
    )
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert len(agendados) == 1
    conv = sessao.scalars(
        select(Conversa).where(Conversa.instrumento_id == inst.id)
    ).first()
    assert conv is not None and conv.contato_chave == "777"


def test_endpoint_entrada_404_para_instrumento_que_nao_e_canal(cliente, dados, sessao):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="busca", tipo="busca_web", configuracao={}
    )
    sessao.add(inst)
    sessao.flush()
    r = cliente.post(f"/mensageria/{inst.id}/entrada", json={"message": {}})
    assert r.status_code == 404


# ────────────────────────── conectar canal (Fase E) ──────────────────────────


def test_ativar_canal_seta_webhook_e_guarda_secret(cliente, entrar, dados, sessao, monkeypatch):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TOK"})
    chamada = {}
    monkeypatch.setattr(
        "mensageria.telegram.configurar_webhook",
        lambda token, url, secret: chamada.update(token=token, url=url, secret=secret)
        or {"ok": True},
    )
    r = cliente.post(f"/mensageria/{inst.id}/ativar-canal")
    assert r.status_code == 200
    assert chamada["token"] == "TOK"
    assert chamada["url"].endswith(f"/mensageria/{inst.id}/entrada")
    sessao.refresh(inst)
    assert inst.configuracao["webhook_secret"] == chamada["secret"]


def test_ativar_canal_sem_token_recusa(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)  # sem token_bot
    r = cliente.post(f"/mensageria/{inst.id}/ativar-canal")
    assert r.status_code == 422


def test_ativar_canal_recusa_bot_ja_usado_por_outro_canal(
    cliente, entrar, dados, sessao, monkeypatch
):
    """Dois canais com o MESMO bot brigam pelo webhook (as respostas — inclusive
    aprovações de portão — caem no canal errado). Conectar o segundo é recusado com
    recado claro, ANTES de tocar o Telegram. (Cobre o time duplicado que reusa o bot
    do original.)"""
    entrar(dados["admin"])
    inst1 = _bot(sessao, dados, nome="Canal A")
    si.salvar_segredos(sessao, inst1.id, {"token_bot": "MESMO-TOKEN"})
    inst2 = _bot(sessao, dados, nome="Canal B")
    si.salvar_segredos(sessao, inst2.id, {"token_bot": "MESMO-TOKEN"})
    chamou = {"n": 0}
    monkeypatch.setattr(
        "mensageria.telegram.configurar_webhook",
        lambda *a, **k: chamou.update(n=chamou["n"] + 1) or {"ok": True},
    )
    r = cliente.post(f"/mensageria/{inst2.id}/ativar-canal")
    assert r.status_code == 409
    assert "Canal A" in r.json()["detail"]
    assert chamou["n"] == 0  # nem chega a chamar o Telegram


def test_ativar_canal_tokens_distintos_conectam(
    cliente, entrar, dados, sessao, monkeypatch
):
    """A trava não atrapalha o caso bom: bots distintos conectam normalmente."""
    entrar(dados["admin"])
    inst1 = _bot(sessao, dados, nome="Canal A")
    si.salvar_segredos(sessao, inst1.id, {"token_bot": "TOKEN-A"})
    inst2 = _bot(sessao, dados, nome="Canal B")
    si.salvar_segredos(sessao, inst2.id, {"token_bot": "TOKEN-B"})
    monkeypatch.setattr(
        "mensageria.telegram.configurar_webhook", lambda *a, **k: {"ok": True}
    )
    assert cliente.post(f"/mensageria/{inst1.id}/ativar-canal").status_code == 200
    assert cliente.post(f"/mensageria/{inst2.id}/ativar-canal").status_code == 200


def test_entrada_valida_secret_token(cliente, dados, sessao, monkeypatch):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    inst.configuracao = {"webhook_secret": "s3cr3t"}
    sessao.commit()
    monkeypatch.setattr(servico, "processar_turno", lambda cid: None)
    corpo = {"message": {"chat": {"id": 1}, "text": "oi"}}
    # sem o cabeçalho correto → 403
    assert cliente.post(f"/mensageria/{inst.id}/entrada", json=corpo).status_code == 403
    # com o cabeçalho correto → 200
    r = cliente.post(
        f"/mensageria/{inst.id}/entrada",
        json=corpo,
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"},
    )
    assert r.status_code == 200


# ─────────────────────── inbox e takeover (Fase F) ───────────────────────────


def test_listar_conversas_da_inbox(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    servico.registrar_entrada(sessao, inst, _msg("oi"))
    r = cliente.get(f"/times/{dados['timeA'].id}/conversas")
    assert r.status_code == 200
    corpo = r.json()
    assert len(corpo) == 1 and corpo[0]["contato_chave"] == "555"


def test_obter_conversa_traz_a_thread(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    r = cliente.get(f"/conversas/{conversa.id}")
    assert r.status_code == 200
    assert [m["papel"] for m in r.json()["mensagens"]] == ["contato"]


def test_assumir_silencia_o_bot(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    r = cliente.post(f"/conversas/{conversa.id}/assumir")
    assert r.status_code == 200 and r.json()["estado"] == "humano_assumiu"
    # uma nova mensagem do contato NÃO dispara o bot
    _, deve = servico.registrar_entrada(sessao, inst, _msg("ainda aí?"))
    assert deve is False


def test_responder_operador_envia_e_grava(cliente, entrar, dados, sessao, monkeypatch):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TK"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    enviados = []
    monkeypatch.setattr(
        "mensageria.telegram.enviar",
        lambda t, c, x: enviados.append((t, c, x)) or {"ok": True},
    )
    r = cliente.post(
        f"/conversas/{conversa.id}/responder-operador",
        json={"texto": "Aqui é o operador."},
    )
    assert r.status_code == 200 and r.json()["papel"] == "operador"
    assert enviados == [("TK", "555", "Aqui é o operador.")]


def test_devolver_e_fechar(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    cliente.post(f"/conversas/{conversa.id}/assumir")
    assert cliente.post(f"/conversas/{conversa.id}/devolver").json()["estado"] == "aberta"
    assert cliente.post(f"/conversas/{conversa.id}/fechar").json()["estado"] == "fechada"


# ───────────────────── horário comercial + saudação (Fase K) ─────────────────


def _quarta(hora_sp: int):
    """Um datetime UTC que, no fuso de SP (UTC−3), cai na quarta 2026-06-17 às
    `hora_sp` horas. (2026-06-17 é quarta-feira; 2026-06-20, sábado.)"""
    return datetime(2026, 6, 17, hora_sp + 3, 0, tzinfo=timezone.utc)


def test_fora_do_horario_desligado_e_sempre_dentro():
    assert servico._fora_do_horario({}) is False
    assert servico._fora_do_horario({"horario_comercial_ativo": False}) is False


def test_fora_do_horario_dia_util_dentro_e_fora():
    cfg = {"horario_comercial_ativo": True, "horario_inicio": "09:00", "horario_fim": "18:00"}
    assert servico._fora_do_horario(cfg, _quarta(12)) is False  # meio do expediente
    assert servico._fora_do_horario(cfg, _quarta(20)) is True   # depois de fechar
    assert servico._fora_do_horario(cfg, _quarta(7)) is True    # antes de abrir


def test_fora_do_horario_fim_de_semana():
    sabado = datetime(2026, 6, 20, 15, 0, tzinfo=timezone.utc)  # SP sáb 12h
    assert servico._fora_do_horario({"horario_comercial_ativo": True}, sabado) is True
    # Atendendo todo dia, sábado ao meio-dia está dentro.
    cfg = {
        "horario_comercial_ativo": True,
        "dias_uteis_apenas": False,
        "horario_inicio": "09:00",
        "horario_fim": "18:00",
    }
    assert servico._fora_do_horario(cfg, sabado) is False


def test_fora_do_horario_config_invalida_fail_open():
    cfg = {"horario_comercial_ativo": True, "horario_inicio": "xx", "horario_fim": "18:00"}
    assert servico._fora_do_horario(cfg, _quarta(12)) is False  # HH:MM inválido → dentro


def test_fora_do_horario_responde_sem_acionar_ia(sessao, dados, monkeypatch):
    inst = _bot(
        sessao, dados,
        configuracao={"saudacao_abertura": "", "mensagem_fora_horario": "Estamos fechados."},
    )
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TOKEN"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))

    rodou = {"ia": False}
    enviados = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(servico, "_fora_do_horario", lambda cfg: True)
    monkeypatch.setattr(
        servico, "executar_agente", lambda *a, **k: rodou.__setitem__("ia", True) or {"saida": "x"}
    )
    monkeypatch.setattr(
        servico.telegram, "enviar", lambda t, c, x: enviados.append(x) or {"ok": True}
    )

    servico.processar_turno(conversa.id)

    assert rodou["ia"] is False               # não acionou a IA
    assert enviados == ["Estamos fechados."]  # auto-resposta de fora-de-horário
    sessao.refresh(conversa)
    assert conversa.estado == "aberta" and conversa.turnos == 0  # não contou turno


def test_saudacao_no_primeiro_contato_uma_unica_vez(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados, configuracao={"saudacao_abertura": "Oi! Sou virtual."})
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TOKEN"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("quanto custa?"))

    enviados = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(servico, "executar_agente", lambda *a, **k: {"saida": "Custa R$10.", "uso": []})
    monkeypatch.setattr(
        servico.telegram, "enviar", lambda t, c, x: enviados.append(x) or {"ok": True}
    )

    servico.processar_turno(conversa.id)
    # 1º turno: saudação ANTES da resposta da IA.
    assert enviados == ["Oi! Sou virtual.", "Custa R$10."]

    # 2ª mensagem do contato (mesma conversa viva) → a saudação NÃO se repete.
    enviados.clear()
    conversa2, _ = servico.registrar_entrada(sessao, inst, _msg("e o prazo?"))
    servico.processar_turno(conversa2.id)
    assert enviados == ["Custa R$10."]


# ─────────────────────────── métricas (Fase K) ───────────────────────────────


def test_metricas_de_atendimento(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    # Conversa 1: o bot respondeu (1 turno, custo) e foi transferida p/ humano.
    c1, _ = servico.registrar_entrada(sessao, inst, _msg("oi", chave="111"))
    sessao.add(MensagemConversa(conversa_id=c1.id, papel="agente", conteudo="resp"))
    c1.turnos = 1
    c1.custo_acumulado_usd = 0.05
    c1.estado = "humano_assumiu"
    # Conversa 2: aberta, ainda sem resposta.
    servico.registrar_entrada(sessao, inst, _msg("ola", chave="222"))
    sessao.commit()

    r = cliente.get(f"/times/{dados['timeA'].id}/conversas/metricas")
    assert r.status_code == 200
    m = r.json()
    assert m["total"] == 2
    assert m["com_humano"] == 1 and m["percent_humano"] == 50.0
    assert m["fechadas"] == 0 and m["abertas"] == 2
    assert m["turnos_total"] == 1
    assert round(m["custo_total_usd"], 2) == 0.05
    assert m["por_estado"]["humano_assumiu"] == 1
    assert m["tempo_resposta_medio_s"] is not None  # c1 teve resposta do bot
