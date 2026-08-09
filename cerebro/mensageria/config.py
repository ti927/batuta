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

from modelos import Automacao, Execucao, Instrumento, Organizacao, Time

# Endereço público do app (onde a aprovação de um portão também pode ser resolvida pela
# tela). Fonte única para as mensagens que orientam o humano.
URL_APP = "batuta.team"


def portao_nativo_ligado(sessao: Session, time_id) -> bool:
    """Se o PORTÃO NATIVO na conversa está ativo para este time (Fatia 4.3 / P3b+P3d).

    Governança DEFINITIVA: respeita a PAREDE DE APROVAÇÃO da organização
    (`Organizacao.parede_ativacao`, LIGADA por padrão) — a MESMA regra que barra ativar uma
    esteira com ação irreversível sem portão. Uma fonte de verdade só, controlada na tela da
    organização (sem env/Railway). Quando a trava está ligada, uma ação IRREVERSÍVEL do
    agente de conversa pausa e espera o 'sim' do contato (trava de SISTEMA, não do markdown);
    org que desligou a parede → sem trava na conversa também (escolha da org)."""
    if not time_id:
        return False
    time = sessao.get(Time, time_id)
    if time is None:
        return False
    org = sessao.get(Organizacao, time.organizacao_id)
    return bool(org and org.parede_ativacao)

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
    f"Estou encerrando a conversa por aqui, mas a aprovação ainda pode ser feita dentro "
    f"do {URL_APP}. (Ou responda aqui quando puder para retomar.)"
)
# Despedida de um PORTÃO quando o Tipo de fluxo manda CANCELAR ao abandonar: aí não há
# "continua no app" — o fluxo se encerra junto.
DESPEDIDA_PORTAO_CANCELA_MSG = (
    "Como não houve resposta, estou encerrando a conversa e cancelando o fluxo."
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
}
# (Fatia 3) As chaves MORTAS `max_passos`, `modelo_roteador` e `acao_ao_estourar`
# saíram: nunca eram lidas — o motor usa o fixo `MAX_PASSOS` (cadeia.py) e o roteador
# usa sempre `MODELO_PADRAO`; o teto SEMPRE passa para humano. O "teto de passos"
# configurável (unificando `max_passos`+`max_turnos`) entra na Fatia 4, junto com o
# descongelamento dirigido do núcleo (`docs/REMODELAGEM-MOTOR.md §7`).

# Só estas chaves podem vir do canal/ajustes (ignora token, destinatario_padrao, etc.).
CHAVES = frozenset(GLOBAL)

# ── PERFIS de fluxo: presets que sobrepõem o global. O usuário escolhe um "tipo de
# fluxo". FONTE ÚNICA — o frontend lê estes valores por endpoint, não os duplica.
# (Fatia 3) De 4 presets → 2 honestos: caíram "disparo" (é um GATILHO, não um tipo de
# fluxo — vira `origem` na Fatia 4) e "personalizado" (é apenas "sem tipo + ajustes",
# já é como a tela trata a ausência de perfil). Nenhuma automação de produção os usava. ──
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
    },
    "atendimento": {
        "saudacao_abertura": SAUDACAO_PADRAO,
        "timeout_min": 60,
        "nudge_timeout_min": 30,
        "max_turnos": 40,
        "teto_usd": 1.0,
        "portao_forma": "conversa",
        "portao_acao_abandono": "estacionar",
    },
}

# Perfil que uma automação recém-criada assume quando ninguém escolhe um tipo de
# fluxo. Antes nasciam sem perfil (`configuracao={}`) e caíam no GLOBAL (cutuca em
# 60 min) sem o usuário perceber — a maioria dos fluxos é interna, então este é o
# padrão sensato. Aplicado nos pontos de nascimento (IA criadora e create manual);
# o duplicar copia o perfil da original. Não retroage sobre automações legadas.
PERFIL_PADRAO = "interno"

# Rótulos amigáveis dos perfis (para a UI; fonte única).
PERFIS_ROTULOS = {
    "interno": "Processo interno",
    "atendimento": "Atendimento externo",
}

# Opções dos botões de escolha (valor → rótulo amigável).
ESCOLHAS = {
    "portao_forma": [
        ("conversa", "O agente conversa (pode perguntar de volta)"),
        ("direto", "Decisão direta (aprovar/reprovar)"),
    ],
    "portao_acao_abandono": [("cancelar", "Cancelar o fluxo"), ("estacionar", "Deixar pendente na tela")],
}

# Botões EXPOSTOS na UI, agrupados (fonte única — o front renderiza a partir daqui,
# sem duplicar rótulos/opções). O que não está aqui fica interno (trilho de segurança).
CAMPOS = [
    {"grupo": "Espera e encerramento", "campos": [
        {"chave": "timeout_min", "rotulo": "Tempo até cutucar quem some", "tipo": "int", "sufixo": "min"},
        {"chave": "nudge_timeout_min", "rotulo": "Tempo após cutucar até encerrar", "tipo": "int", "sufixo": "min"},
        {"chave": "encerrar_por_inatividade", "rotulo": "Encerrar conversas paradas", "tipo": "bool"},
    ]},
    {"grupo": "Limites da conversa", "campos": [
        {"chave": "max_turnos", "rotulo": "Máx. de mensagens por conversa", "tipo": "int"},
        {"chave": "teto_usd", "rotulo": "Teto de custo de IA por conversa", "tipo": "valor", "sufixo": "US$"},
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
        {"chave": "portao_max_rodadas", "rotulo": "Máx. de idas-e-vindas no portão (tela)", "tipo": "int"},
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
    """O efetivo no nível do FLUXO: global < perfil < ajustes (sem canal, aqui sem
    conversa). Usado quando só se tem a automação (ex.: o portão lendo `portao_max_rodadas`
    na tela, via `retoma`)."""
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


# ── Mensagens de portão DERIVADAS dos parâmetros do Tipo de fluxo ──────────────
# Em vez de o agente (markdown) fixar "X minutos" na mão — que desatualizaria ao
# trocar o Tipo de fluxo (múltiplas fontes de verdade) — a borda MONTA o texto a
# partir do `conf` resolvido. Assim o aviso é sempre coerente com o parâmetro real,
# uniforme em toda automação. `conf` é o efetivo de `resolver_config`.


def aviso_expectativa_portao(conf: dict) -> str | None:
    """Aviso enviado JUNTO do pedido de aprovação (borda), dizendo o que acontece se o
    humano não responder — derivado dos tempos e da ação de abandono do fluxo. Devolve
    `None` quando o fluxo não encerra por inatividade (não há timeout → nada a avisar)."""
    if not conf.get("encerrar_por_inatividade"):
        return None
    total = int(conf["timeout_min"]) + int(conf["nudge_timeout_min"])
    if conf.get("portao_acao_abandono") == "cancelar":
        return (
            f"⏳ Se você não responder, encerro esta conversa em cerca de {total} min e o "
            f"fluxo será cancelado. Dá para aprovar aqui ou em {URL_APP} até lá."
        )
    return (
        f"⏳ Se você não responder, encerro esta conversa em cerca de {total} min — mas "
        f"sem problema: a aprovação continua disponível dentro do {URL_APP} mesmo depois."
    )


def complemento_nudge_portao(conf: dict) -> str:
    """Cauda acrescentada ao 'cutucar' de um portão: lembra o prazo até encerrar, a
    opção de *cancelar* e (se estacionar) que a aprovação segue no app. Derivado do
    parâmetro do Tipo de fluxo."""
    y = int(conf["nudge_timeout_min"])
    if conf.get("portao_acao_abandono") == "cancelar":
        return (
            f"\n\n(Sem resposta, encerro em ~{y} min e cancelo o fluxo. "
            f"Ou responda *cancelar* para encerrar agora.)"
        )
    return (
        f"\n\n(Sem resposta, encerro em ~{y} min — a aprovação segue no {URL_APP}. "
        f"Ou responda *cancelar* para encerrar o fluxo.)"
    )
