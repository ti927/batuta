"""Configuração EFETIVA de uma conversa — a FONTE ÚNICA das regras de fluxo.

As regras de comportamento de uma conversa (espera, teto, turnos, saudação,
horário, portão, encerramento) NÃO são fixas no código: cascateiam, do mais geral
ao mais específico —

    padrão GLOBAL  <  canal (instrumento.configuracao)  <  PERFIL do fluxo  <
    ajustes do fluxo (automacao.configuracao.ajustes)  <  ajustes do NÓ (portão)

O mais específico vence. Atendimento puro (conversa sem automação) usa só
`global < canal` — idêntico ao de hoje (sem regressão). `resolver_config` é o
ÚNICO lugar que monta esse efetivo; a borda (servico/sweeper) e o portão leem dele,
NUNCA de `instrumento.configuracao` direto. Assim a regra é geral e por-fluxo ao
mesmo tempo, com uma fonte só (evita a divergência de fontes que gera bug
recorrente).

Este módulo é FOLHA (não importa servico/sweeper) — ele é a origem dos defaults e
das mensagens-padrão; a borda passa a importar daqui.
"""

from sqlalchemy.orm import Session

from modelos import Automacao, Execucao, Instrumento

# ── Mensagens-padrão (a borda importa daqui; antes viviam em servico/sweeper) ──
SAUDACAO_PADRAO = "Olá! Você está falando com um assistente virtual. Como posso ajudar?"
MSG_FORA_HORARIO_PADRAO = (
    "Olá! No momento estamos fora do horário de atendimento. "
    "Assim que possível retornaremos sua mensagem."
)
MSG_LIMITE = "Vou te encaminhar para um atendente humano. Um instante."
NUDGE_MSG = "Ainda está por aí? Se precisar de algo, é só me escrever."
DESPEDIDA_MSG = (
    "Vou encerrar por aqui por enquanto. Quando precisar, é só mandar uma mensagem."
)
# Despedida de um PORTÃO deixado pendente (estacionar): não sugere que o fluxo morreu —
# ele segue aguardando aprovação e é retomável por uma resposta tardia (ou pela tela).
DESPEDIDA_PORTAO_MSG = (
    "Vou pausar o lembrete por aqui, mas o fluxo segue aguardando a sua aprovação — "
    "responda quando puder para continuar, ou *cancelar* para encerrar."
)

# ── Padrão GLOBAL: o efetivo quando nada mais especifica. Os valores batem com o
# comportamento de HOJE (instrumento sem chave → estes defaults). As chaves dos
# botões de atendimento usam os MESMOS nomes que `instrumento.configuracao` já usa,
# para o canal sobrepor sem mapeamento. ──
GLOBAL: dict = {
    # A. Espera & encerramento
    "timeout_min": 60,            # min sem resposta até cutucar (sweeper)
    "nudge_timeout_min": 30,      # min após cutucar até encerrar
    "encerrar_por_inatividade": True,
    # B. Limites da conversa
    "max_turnos": 40,
    "teto_usd": 1.0,
    "acao_ao_estourar": "passar_humano",  # passar_humano | encerrar
    # C. Atendimento (cliente externo)
    "saudacao_abertura": SAUDACAO_PADRAO,  # "" = desligada
    "horario_comercial_ativo": False,
    "horario_inicio": "09:00",
    "horario_fim": "18:00",
    "dias_uteis_apenas": True,
    "mensagem_fora_horario": MSG_FORA_HORARIO_PADRAO,
    "mensagem_limite": MSG_LIMITE,
    "mensagem_nudge": NUDGE_MSG,
    "mensagem_despedida": DESPEDIDA_MSG,
    # D. Portão (aprovação)
    "portao_forma": "conversa",          # conversa | direto
    # Ao ABANDONAR o portão (silêncio no timeout OU estouro de turnos/teto): FONTE ÚNICA,
    # lida pelo sweeper E por `_turno_de_portao`. `estacionar` (padrão) = mantém a execução
    # `aguardando_humano` e RETOMÁVEL (uma resposta tardia pelo canal religa; a tela também
    # resolve); `cancelar` = encerra a execução. (Antes havia uma 2ª chave só no sweeper,
    # `acao_ao_encerrar`, que podia divergir desta — unificadas.)
    "portao_acao_abandono": "estacionar",
    "portao_max_rodadas": 8,
    # E. Motor (avançado/raro)
    "max_passos": 25,
    "modelo_roteador": None,             # None = MODELO_PADRAO
}

# Só estas chaves podem vir do canal/ajustes (ignora token, destinatario_padrao, etc.).
CHAVES = frozenset(GLOBAL)

# ── PERFIS de fluxo: presets que sobrepõem o global. O usuário escolhe um "tipo de
# fluxo"; "personalizado" não tem defaults próprios (parte do global e os ajustes
# mandam). FONTE ÚNICA — o frontend lê estes valores por endpoint, não os duplica. ──
PERFIS: dict[str, dict] = {
    "interno": {
        "saudacao_abertura": "",
        "horario_comercial_ativo": False,
        "timeout_min": 30,
        "nudge_timeout_min": 15,
        "max_turnos": 20,
        "teto_usd": 0.5,
        "portao_forma": "conversa",
        "portao_acao_abandono": "estacionar",
        "acao_ao_estourar": "passar_humano",
    },
    "atendimento": {
        "saudacao_abertura": SAUDACAO_PADRAO,
        "timeout_min": 60,
        "nudge_timeout_min": 30,
        "max_turnos": 40,
        "teto_usd": 1.0,
        "portao_forma": "conversa",
        "portao_acao_abandono": "estacionar",
        "acao_ao_estourar": "passar_humano",
    },
    "disparo": {
        "saudacao_abertura": "",
        "horario_comercial_ativo": False,
        "timeout_min": 15,
        "nudge_timeout_min": 10,
        "max_turnos": 5,
        "teto_usd": 0.25,
        "portao_forma": "direto",
        "portao_acao_abandono": "cancelar",
        "acao_ao_estourar": "encerrar",
    },
    "personalizado": {},
}

# Rótulos amigáveis dos perfis (para a UI; fonte única).
PERFIS_ROTULOS = {
    "interno": "Processo interno",
    "atendimento": "Atendimento ao cliente",
    "disparo": "Disparo / notificação externa",
    "personalizado": "Personalizado",
}

# Opções dos botões de escolha (valor → rótulo amigável).
ESCOLHAS = {
    "acao_ao_estourar": [("passar_humano", "Passar para um humano"), ("encerrar", "Encerrar a conversa")],
    "portao_forma": [
        ("conversa", "O agente conversa (pode perguntar de volta)"),
        ("direto", "Decisão direta (aprovar/reprovar)"),
    ],
    "portao_acao_abandono": [("cancelar", "Cancelar o fluxo"), ("estacionar", "Deixar pendente na tela")],
}

# Botões EXPOSTOS na UI, agrupados (fonte única — o front renderiza a partir daqui,
# sem duplicar rótulos/opções). O que não está aqui fica interno (trilho de segurança
# ou avançado-raro como max_passos/modelo_roteador).
CAMPOS = [
    {"grupo": "Espera e encerramento", "campos": [
        {"chave": "timeout_min", "rotulo": "Tempo até cutucar quem some", "tipo": "int", "sufixo": "min"},
        {"chave": "nudge_timeout_min", "rotulo": "Tempo após cutucar até encerrar", "tipo": "int", "sufixo": "min"},
        {"chave": "encerrar_por_inatividade", "rotulo": "Encerrar conversas paradas", "tipo": "bool"},
    ]},
    {"grupo": "Limites da conversa", "campos": [
        {"chave": "max_turnos", "rotulo": "Máx. de mensagens por conversa", "tipo": "int"},
        {"chave": "teto_usd", "rotulo": "Teto de custo de IA por conversa", "tipo": "valor", "sufixo": "US$"},
        {"chave": "acao_ao_estourar", "rotulo": "Ao estourar o limite", "tipo": "escolha"},
    ]},
    {"grupo": "Atendimento ao cliente", "campos": [
        {"chave": "saudacao_abertura", "rotulo": "Saudação no 1º contato (vazio = desligada)", "tipo": "texto"},
        {"chave": "horario_comercial_ativo", "rotulo": "Atender só em horário comercial", "tipo": "bool"},
        {"chave": "horario_inicio", "rotulo": "Abre às", "tipo": "hora"},
        {"chave": "horario_fim", "rotulo": "Fecha às", "tipo": "hora"},
        {"chave": "dias_uteis_apenas", "rotulo": "Só em dias úteis", "tipo": "bool"},
        {"chave": "mensagem_fora_horario", "rotulo": "Mensagem fora do horário", "tipo": "texto"},
    ]},
    {"grupo": "Portão de aprovação", "campos": [
        {"chave": "portao_forma", "rotulo": "Como o agente conduz o portão", "tipo": "escolha"},
        {"chave": "portao_acao_abandono", "rotulo": "Se o aprovador abandona a conversa", "tipo": "escolha"},
    ]},
]


def painel_config() -> dict:
    """Metadados para a UI montar 'Configurações do fluxo' a partir do backend (fonte
    única): os perfis (com os defaults que cada um aplica), os grupos de botões e o
    padrão global. O front não duplica rótulos/valores."""
    perfis = [
        {"id": pid, "rotulo": PERFIS_ROTULOS.get(pid, pid), "defaults": _mesclar(GLOBAL, PERFIS.get(pid))}
        for pid in PERFIS
    ]
    grupos = []
    for g in CAMPOS:
        campos = []
        for c in g["campos"]:
            c = dict(c)
            if c["tipo"] == "escolha":
                c["opcoes"] = [{"valor": v, "rotulo": r} for v, r in ESCOLHAS[c["chave"]]]
            c["padrao"] = GLOBAL.get(c["chave"])
            campos.append(c)
        grupos.append({"grupo": g["grupo"], "campos": campos})
    return {"perfis": perfis, "grupos": grupos, "padrao_global": dict(GLOBAL)}


def _mesclar(base: dict, extra: dict | None) -> dict:
    """Sobrepõe `base` com as chaves conhecidas de `extra` (ignora nulos e chaves
    estranhas). Não muta `base`."""
    out = dict(base)
    for k, v in (extra or {}).items():
        if k in CHAVES and v is not None:
            out[k] = v
    return out


def config_da_automacao(auto: Automacao | None) -> dict:
    """O efetivo no nível do FLUXO: global < canal-NÃO (aqui sem conversa) < perfil <
    ajustes. Usado quando só se tem a automação (ex.: motor lendo max_passos)."""
    cfg = dict(GLOBAL)
    bruto = (auto.configuracao or {}) if auto else {}
    perfil = bruto.get("perfil")
    if perfil in PERFIS:
        cfg = _mesclar(cfg, PERFIS[perfil])
    return _mesclar(cfg, bruto.get("ajustes"))


def resolver_config(sessao: Session, conversa) -> dict:
    """Monta a config EFETIVA de uma conversa, na cascata
    global < canal < perfil do fluxo < ajustes do fluxo.

    (Ajustes por NÓ do portão entram no consumidor que conhece o nó pausado.)
    Atendimento puro (sem `execucao_id`) para em `global < canal` — igual a hoje."""
    cfg = dict(GLOBAL)
    inst = sessao.get(Instrumento, conversa.instrumento_id) if conversa.instrumento_id else None
    if inst is not None:
        cfg = _mesclar(cfg, inst.configuracao)

    execucao = (
        sessao.get(Execucao, conversa.execucao_id) if conversa.execucao_id else None
    )
    auto = (
        sessao.get(Automacao, execucao.automacao_id)
        if execucao is not None
        else None
    )
    if auto is not None:
        bruto = auto.configuracao or {}
        perfil = bruto.get("perfil")
        if perfil in PERFIS:
            cfg = _mesclar(cfg, PERFIS[perfil])
        cfg = _mesclar(cfg, bruto.get("ajustes"))
    return cfg


def com_ajuste_do_no(cfg: dict, no: dict | None) -> dict:
    """Sobrepõe a config efetiva com ajustes específicos do NÓ do portão
    (`no.config`), o nível mais específico da cascata."""
    return _mesclar(cfg, (no or {}).get("config"))
