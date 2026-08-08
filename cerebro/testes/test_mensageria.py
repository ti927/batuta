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
    Execucao,
    Instrumento,
    MensagemConversa,
    PassoExecucao,
)


def _semear_sombra(sessao, conversa, *, custo_usd=0.0, turnos=1):
    """Semeia a timeline-sombra da conversa (Fatia 2: a fonte da medição do teto)
    com `turnos` passos PRODUTIVOS somando `custo_usd`. Substitui, nos testes,
    setar o contador `custo_acumulado_usd` na mão — que virou só cache."""
    sombra = Execucao(
        automacao_id=None, modo="conversa", conversa_id=conversa.id,
        estado="conversa", entrada={"texto": "sombra"},
    )
    sessao.add(sombra)
    sessao.flush()
    for i in range(turnos):
        sessao.add(
            PassoExecucao(
                execucao_id=sombra.id, ordem=i + 1,
                saida={"texto": "x", "uso": [{"custo_usd": custo_usd if i == 0 else 0}]},
                estado="concluido",
            )
        )
    sessao.flush()
    return sombra


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


def test_extrair_update_foto_pega_o_maior_tamanho():
    m = telegram.extrair_update(
        {"message": {"chat": {"id": 9}, "photo": [
            {"file_id": "pequeno"}, {"file_id": "grande"},
        ]}}
    )
    assert m and m.texto is None
    assert m.midia == {"tipo": "imagem", "file_id": "grande"}  # o último = o maior


def test_extrair_update_imagem_como_documento():
    m = telegram.extrair_update(
        {"message": {"chat": {"id": 9},
                     "document": {"file_id": "D", "mime_type": "image/png"}}}
    )
    assert m and m.midia == {"tipo": "imagem", "file_id": "D"}


def test_extrair_update_foto_com_legenda_guarda_o_caption():
    m = telegram.extrair_update(
        {"message": {"chat": {"id": 9}, "photo": [{"file_id": "G"}],
                     "caption": "segue o comprovante"}}
    )
    assert m.midia == {"tipo": "imagem", "file_id": "G", "legenda": "segue o comprovante"}


def test_extrair_update_documento_nao_imagem_vira_outro():
    m = telegram.extrair_update(
        {"message": {"chat": {"id": 9},
                     "document": {"file_id": "D", "mime_type": "application/pdf"}}}
    )
    assert m and m.midia == {"tipo": "outro"}


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


def test_memoria_semeia_historico_no_primeiro_turno(sessao, dados, monkeypatch):
    """P2a: com checkpointer disponível e SEM fio ainda, semeia com o histórico e passa
    checkpointer + thread_id + preâmbulo de sistema ao executar_agente."""
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("quanto custa?"))

    capt = {}
    sentinela = object()
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(servico.memoria_conversa, "obter", lambda: sentinela)
    monkeypatch.setattr(servico.memoria_conversa, "tem_estado", lambda tid: False)  # sem fio → semeia

    def fake(ag, cinto, entrada, **k):
        capt["entrada"] = entrada
        capt["kwargs"] = k
        return {"saida": "R$10", "uso": [{"tokens_entrada": 1, "tokens_saida": 1}]}

    monkeypatch.setattr(servico, "executar_agente", fake)
    monkeypatch.setattr(servico.telegram, "enviar", lambda *a: {"ok": True})

    servico.processar_turno(conversa.id)

    assert "quanto custa?" in capt["entrada"]  # SEMEOU com o histórico
    assert capt["kwargs"]["checkpointer"] is sentinela
    assert capt["kwargs"]["thread_id"] == str(conversa.id)
    assert "atendendo" in capt["kwargs"]["preambulo_sistema"].lower()


def test_conteudo_novo_pega_so_apos_o_ultimo_agente(sessao, dados):
    """P2a: a 'fala nova' do turno = mensagens do contato APÓS o último turno do agente
    (o resto o agente lembra do fio). Timestamps explícitos: numa só transação de teste,
    `now()` empataria."""
    inst = _bot(sessao, dados)
    ag = _agente_com(sessao, dados, inst)
    conv = Conversa(
        instrumento_id=inst.id, contato_chave="1", contato_nome="X",
        estado="aberta", destino_tipo="agente", destino_id=ag.id,
    )
    sessao.add(conv)
    sessao.flush()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for papel, texto, off in [
        ("contato", "pergunta antiga", 0),
        ("agente", "resposta antiga", 1),
        ("contato", "pergunta NOVA", 2),
    ]:
        sessao.add(MensagemConversa(
            conversa_id=conv.id, papel=papel, conteudo=texto,
            criado_em=base + timedelta(seconds=off),
        ))
    sessao.flush()

    novo = servico._conteudo_novo(sessao, conv)
    assert "pergunta NOVA" in novo
    assert "antiga" not in novo  # não reenvia o que veio antes do último turno do agente


def test_resgatar_imagens_recentes_rebaixa_pelo_file_id(sessao, dados, monkeypatch):
    """Fallback do arquivar entre turnos: resgata a imagem MAIS RECENTE re-baixando pelo
    file_id salvo — o que deixa o agente guardar o comprovante num turno posterior ao envio."""
    inst = _bot(sessao, dados)
    ag = _agente_com(sessao, dados, inst)
    conv = Conversa(
        instrumento_id=inst.id, contato_chave="1", contato_nome="X",
        estado="aberta", destino_tipo="agente", destino_id=ag.id,
    )
    sessao.add(conv)
    sessao.flush()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    sessao.add(MensagemConversa(
        conversa_id=conv.id, papel="contato", conteudo="[imagem recebida] recibo",
        midia={"tipo": "imagem", "file_id": "FID123", "legenda": "recibo"},
        criado_em=base,
    ))
    sessao.add(MensagemConversa(  # mensagem de texto MAIS NOVA (não é imagem)
        conversa_id=conv.id, papel="contato", conteudo="cof piso",
        criado_em=base + timedelta(seconds=5),
    ))
    sessao.flush()

    monkeypatch.setattr(
        servico.telegram, "baixar_arquivo",
        lambda tok, fid: b"\xff\xd8\xffJPG" if fid == "FID123" else None,
    )
    imgs = servico._resgatar_imagens_recentes(sessao, conv, token="T")
    assert len(imgs) == 1
    assert imgs[0]["bytes"] == b"\xff\xd8\xffJPG"
    assert imgs[0]["legenda"] == "recibo"


def test_resgatar_sem_token_ou_sem_imagem_volta_vazio(sessao, dados):
    """Sem token, ou sem nenhuma imagem na conversa → []; o instrumento então avisa claro."""
    inst = _bot(sessao, dados)
    ag = _agente_com(sessao, dados, inst)
    conv = Conversa(
        instrumento_id=inst.id, contato_chave="1", contato_nome="X",
        estado="aberta", destino_tipo="agente", destino_id=ag.id,
    )
    sessao.add(conv)
    sessao.flush()
    sessao.add(MensagemConversa(conversa_id=conv.id, papel="contato", conteudo="só texto"))
    sessao.flush()
    assert servico._resgatar_imagens_recentes(sessao, conv, token=None) == []  # sem token
    assert servico._resgatar_imagens_recentes(sessao, conv, token="T") == []   # sem imagem


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
    # Fatia 2: o teto lê da TIMELINE-sombra, não do contador. Semeia um turno caro.
    _semear_sombra(sessao, conversa, custo_usd=999)
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


# ───────────────────────── imagem → texto (visão) ────────────────────────────


def test_imagem_fica_sem_texto_ate_o_turno(sessao, dados):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    img = telegram.MensagemEntrante("555", "João", None, {"tipo": "imagem", "file_id": "F"})
    conversa, _ = servico.registrar_entrada(sessao, inst, img)
    m = sessao.scalars(
        select(MensagemConversa).where(MensagemConversa.conversa_id == conversa.id)
    ).first()
    # imagem entra SEM texto (a visão preenche no turno) — não vira o aviso genérico.
    assert m.conteudo is None and (m.midia or {}).get("tipo") == "imagem"


def test_imagem_descrita_entra_no_turno(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    img = telegram.MensagemEntrante("555", "João", None, {"tipo": "imagem", "file_id": "F"})
    conversa, _ = servico.registrar_entrada(sessao, inst, img)

    entradas = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico, "resolver_chaves_por_time", lambda s, t: ({"anthropic": "K"}, {})
    )
    monkeypatch.setattr("mensageria.telegram.baixar_arquivo", lambda token, fid: b"\xff\xd8\xffimg")
    monkeypatch.setattr(
        "mensageria.visao.descrever", lambda dados, modelo, **k: ("Nota fiscal de R$ 250,00", {})
    )
    monkeypatch.setattr(
        servico, "executar_agente",
        lambda ag, cinto, entrada, **k: entradas.append(entrada) or {"saida": "Recebi a nota."},
    )
    monkeypatch.setattr(servico.telegram, "enviar", lambda *a: {"ok": True})

    servico.processar_turno(conversa.id)

    # a imagem virou descrição e entrou no enquadramento do turno
    assert entradas and "Nota fiscal de R$ 250,00" in entradas[0]
    m = sessao.scalars(
        select(MensagemConversa).where(
            MensagemConversa.conversa_id == conversa.id,
            MensagemConversa.papel == "contato",
        )
    ).first()
    assert "Nota fiscal de R$ 250,00" in (m.conteudo or "")
    assert (m.midia or {}).get("descrito") is True


def test_imagem_com_legenda_preserva_o_texto_do_cliente(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    img = telegram.MensagemEntrante(
        "555", "João", None,
        {"tipo": "imagem", "file_id": "F", "legenda": "esse foi o pix de hoje"},
    )
    conversa, _ = servico.registrar_entrada(sessao, inst, img)

    entradas = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico, "resolver_chaves_por_time", lambda s, t: ({"anthropic": "K"}, {})
    )
    monkeypatch.setattr("mensageria.telegram.baixar_arquivo", lambda token, fid: b"\xff\xd8\xffimg")
    monkeypatch.setattr(
        "mensageria.visao.descrever", lambda dados, modelo, **k: ("comprovante de R$ 90", {})
    )
    monkeypatch.setattr(
        servico, "executar_agente",
        lambda ag, cinto, entrada, **k: entradas.append(entrada) or {"saida": "ok"},
    )
    monkeypatch.setattr(servico.telegram, "enviar", lambda *a: {"ok": True})

    servico.processar_turno(conversa.id)

    # a descrição E a legenda do cliente entram no turno (a legenda nunca se perde)
    assert entradas and "comprovante de R$ 90" in entradas[0]
    assert "esse foi o pix de hoje" in entradas[0]


def test_imagem_recebida_disponivel_para_arquivar_no_turno(sessao, dados, monkeypatch):
    """A imagem baixada fica disponível no contexto do turno (`midia_recebida`), para o
    instrumento `arquivar_imagem` GUARDAR sob demanda — o agente decide pelo markdown."""
    import midia_recebida

    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    img = telegram.MensagemEntrante("555", "João", None, {"tipo": "imagem", "file_id": "F"})
    conversa, _ = servico.registrar_entrada(sessao, inst, img)

    visto = {}
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico, "resolver_chaves_por_time", lambda s, t: ({"anthropic": "K"}, {})
    )
    monkeypatch.setattr("mensageria.telegram.baixar_arquivo", lambda token, fid: b"\xff\xd8\xffimg")
    monkeypatch.setattr("mensageria.visao.descrever", lambda dados, modelo, **k: ("desc", {}))

    def fake_agente(ag, cinto, entrada, **k):
        visto["imagens"] = list(midia_recebida.imagens_recebidas_atuais())
        return {"saida": "ok"}

    monkeypatch.setattr(servico, "executar_agente", fake_agente)
    monkeypatch.setattr(servico.telegram, "enviar", lambda *a: {"ok": True})

    servico.processar_turno(conversa.id)

    # durante o turno do agente, a imagem recebida esteve disponível para guardar
    assert visto.get("imagens") and visto["imagens"][0]["mime"] == "image/jpeg"
    # e fora do turno o contexto volta a ficar vazio (não vaza)
    assert midia_recebida.imagens_recebidas_atuais() == []


def test_processar_turno_contabiliza_visao(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "T"})
    _agente_com(sessao, dados, inst)
    img = telegram.MensagemEntrante("555", "João", None, {"tipo": "imagem", "file_id": "F"})
    conversa, _ = servico.registrar_entrada(sessao, inst, img)

    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico, "resolver_chaves_por_time",
        lambda s, t: ({"anthropic": "K"}, {"anthropic": "consultoria"}),
    )
    monkeypatch.setattr(
        "mensageria.telegram.baixar_arquivo", lambda token, fid: b"\x89PNG\r\n\x1a\nimg"
    )
    monkeypatch.setattr("mensageria.visao.descrever", lambda dados, modelo, **k: ("um recibo", {}))
    monkeypatch.setattr(servico, "executar_agente", lambda *a, **k: {"saida": "ok", "uso": []})
    monkeypatch.setattr(servico.telegram, "enviar", lambda *a: {"ok": True})

    servico.processar_turno(conversa.id)

    do_agente = sessao.scalars(
        select(MensagemConversa).where(
            MensagemConversa.conversa_id == conversa.id,
            MensagemConversa.papel == "agente",
        )
    ).first()
    # uma entrada de leitura por visão (categoria 'visao'), custo por descrição pré-calc
    # e origem carimbada.
    vis = [e for e in (do_agente.uso or []) if e.get("categoria") == "visao"]
    assert len(vis) == 1
    assert vis[0]["origem"] == "consultoria"
    assert vis[0]["custo_usd"] == round(servico.precos.custo_por_descricao(vis[0]["modelo"]), 6)


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
    assert inst.webhook_secret == chamada["secret"]  # crachá na coluna própria


def test_editar_instrumento_preserva_webhook_secret(cliente, entrar, dados, sessao):
    """Editar a config do canal (trocar destinatário, saudação…) NÃO pode apagar o
    crachá do webhook — senão o canal "desconecta" sozinho e o usuário tem de
    reconectar a cada ajuste (bug recorrente). O crachá vive em coluna própria,
    imune à reconstrução da config. Vale para o formulário E para a IA de conversa."""
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TOK"})
    inst.webhook_secret = "cracha-123"
    sessao.commit()
    r = cliente.put(
        f"/instrumentos/{inst.id}",
        json={
            "nome": inst.nome,
            "configuracao": {"destinatario_padrao": "999"},
            "icone": None,
            "credencial_id": None,
        },
    )
    assert r.status_code == 200, r.text
    sessao.refresh(inst)
    assert inst.webhook_secret == "cracha-123"  # crachá preservado
    assert (inst.configuracao or {}).get("destinatario_padrao") == "999"  # edição aplicou


# ─────────────────── checagem de alcance do destinatário ───────────────────


def _mock_telegram_alcance(monkeypatch, *, chat_status, chat_corpo):
    """Intercepta o httpx de `mensageria.telegram`: getMe fixo + getChat controlado."""

    class _Resp:
        def __init__(self, status, corpo):
            self.status_code = status
            self.is_success = 200 <= status < 300
            self.content = b"x"
            self._c = corpo

        def json(self):
            return self._c

    class _Cli:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None):
            if url.endswith("/getMe"):
                return _Resp(200, {"ok": True, "result": {"username": "MeuBot"}})
            if url.endswith("/getChat"):
                return _Resp(chat_status, chat_corpo)
            return _Resp(200, {"ok": True})

    monkeypatch.setattr("mensageria.telegram.httpx.Client", _Cli)


def test_checar_alcance_destino_alcancavel(monkeypatch):
    _mock_telegram_alcance(monkeypatch, chat_status=200, chat_corpo={"ok": True, "result": {"id": 999}})
    r = telegram.checar_alcance("TOK", "999")
    assert r["alcancavel"] is True
    assert r["bot_username"] == "MeuBot"


def test_checar_alcance_destino_inalcancavel(monkeypatch):
    _mock_telegram_alcance(
        monkeypatch, chat_status=400, chat_corpo={"ok": False, "description": "chat not found"}
    )
    r = telegram.checar_alcance("TOK", "999")
    assert r["alcancavel"] is False
    assert r["bot_username"] == "MeuBot"
    assert "chat not found" in r["motivo"]


def test_alcance_sem_token_ou_destino_nao_aplicavel(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)  # sem token e sem destinatário
    r = cliente.get(f"/mensageria/{inst.id}/alcance")
    assert r.status_code == 200
    assert r.json()["aplicavel"] is False


def test_alcance_route_reporta_inalcancavel(cliente, entrar, dados, sessao, monkeypatch):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TOK"})
    inst.configuracao = {"destinatario_padrao": "999"}
    sessao.commit()
    monkeypatch.setattr(
        "mensageria.telegram.checar_alcance",
        lambda token, chat: {"alcancavel": False, "bot_username": "MeuBot", "motivo": "chat not found"},
    )
    r = cliente.get(f"/mensageria/{inst.id}/alcance")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["aplicavel"] is True and b["alcancavel"] is False
    assert b["bot_username"] == "MeuBot" and b["destino"] == "999"


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
    inst.webhook_secret = "s3cr3t"
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
