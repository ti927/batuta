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

# Endereço público do app (onde a aprovação de um portão também pode ser resolvida pela
# tela). Fonte única para as mensagens que orientam o humano.
URL_APP = "batuta.team"


# ── Mensagens-padrão (a borda importa daqui; antes viviam em servico/sweeper) ──
SAUDACAO_PADRAO = "Olá! Você está falando com um assistente virtual. Como posso ajudar?"
MSG_FORA_HORARIO_PADRAO = (
    "Olá! No momento estamos fora do horário de atendimento. "
    "Assim que possível retornaremos sua mensagem."
)
# O bot atingiu um limite da conversa e passa a bola para uma pessoa. O texto diz o
# que houve e o que acontece agora — o antigo "Vou te encaminhar para um atendente
# humano. Um instante." escondia o motivo e prometia um "instante" que ninguém cumpria.
MSG_LIMITE = (
    "Esta conversa atingiu o limite configurado de atendimento automático, então vou "
    "passá-la para uma pessoa da equipe. Nada do que você escreveu se perdeu — está "
    "tudo registrado aqui e alguém retoma a partir do ponto em que paramos."
)
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

# ── Turno PRESO (§12-A: nada que o usuário dispara pode ficar sem sinal de vida) ──
# Um turno roda em segundo plano; enquanto ele corre, a conversa fica `bot_respondendo`.
# Se a tarefa morrer ou pendurar (reinício do servidor, chamada externa sem retorno), a
# conversa ficava nesse estado PARA SEMPRE: nenhum vigia olhava para ela e o contato não
# recebia nada — foi o que aconteceu em 2026-08-26 (aprovação de portão parada ~1h em
# silêncio). DOIS tetos, porque os piores casos legítimos são diferentes:
# - Atendimento (chat): a IA roda com limites curtos (60 s × 2 tentativas) + instrumentos;
#   um turno legítimo não passa de ~5 min. Teto de 8 min — no incidente de 2026-08-27 o
#   contato ficou 16 min no vácuo esperando os 30.
# - Portão: a resposta religa o FLUXO, que roda com os limites da orquestração
#   (300 s × 6 retentativas de IA) — 30 min não interrompe retomada lenta de verdade.
TETO_TURNO_PRESO_MIN = 8
TETO_TURNO_PRESO_PORTAO_MIN = 30
# Aviso honesto ao contato quando o turno dele não voltou (o que houve + o que fazer).
TURNO_PRESO_PORTAO_MSG = (
    "⚠️ Tive uma falha interna e não consegui concluir o processamento da sua resposta. "
    "Ela NÃO foi perdida e a aprovação continua pendente: reenvie sua resposta aqui, ou "
    f"aprove direto no {URL_APP}."
)
TURNO_PRESO_MSG = (
    "⚠️ Tive uma falha interna e não consegui concluir a resposta à sua última mensagem. "
    "Pode reenviá-la, por favor?"
)
# A conversa tinha sido passada para uma pessoa e ninguém assumiu: o vigia
# (`sweeper.varrer_transferidas`) devolve ao bot. Honesto nas duas pontas — diz que
# ninguém veio e que o atendimento continua, em vez de deixar o contato no vácuo.
DEVOLVIDA_AO_BOT_MSG = (
    "Desculpe a demora — ninguém da equipe conseguiu assumir esta conversa a tempo, "
    "então volto a te atender por aqui. Pode seguir de onde paramos."
)
DEVOLVIDA_AO_BOT_PORTAO_MSG = (
    "Desculpe a demora — ninguém da equipe assumiu esta conversa, então volto a te "
    f"atender por aqui. A aprovação continua pendente: responda por aqui ou no {URL_APP}."
)
# O turno FALHOU (a IA não respondeu a tempo, um instrumento estourou). Diferente do turno
# preso: aqui o Batuta sabe na hora que deu errado, então avisa na hora — em vez de deixar
# o contato no vácuo esperando uma resposta que não vem.
FALHA_TURNO_MSG = (
    "⚠️ Não consegui responder agora — tive um problema para processar sua mensagem. "
    "Pode reenviar, por favor? Se continuar, avise o responsável pelo atendimento."
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
    # Teto de custo da CONVERSA: conta a IA que CONVERSA (o turno do agente e a
    # transcrição de áudio), NÃO o trabalho que ele manda fazer (gerar imagem, vídeo,
    # PDF). O trabalho é do FLUXO e tem o teto dele (`teto_usd_execucao`) — contar as
    # duas coisas aqui fazia um único carrossel (3 imagens = US$ 0,50) estourar o teto
    # de uma conversa inteira na PRIMEIRA reprovação, emudecendo o canal (incidente de
    # 2026-09-14, execução 3a1edfd6). Uma régua por propósito, sem dupla contagem.
    "teto_usd": 1.0,
    # Guarda contra laço infinito no motor: nº máximo de passos por EXECUÇÃO (a conta
    # soma as retomadas). Era o fixo `cadeia.MAX_PASSOS` — um teto que ninguém via nem
    # podia mudar. Todo limite do Batuta é configurável e aparece no resumo do fluxo.
    "max_passos": 25,
    # B2. Limite da EXECUÇÃO (Onda 4, fatia 4). Irmão do `teto_usd`, que vale por
    # CONVERSA: este vale por execução de automação, somando as retomadas. Zero =
    # DESLIGADO, e é o padrão de propósito — a fatia é opcional, e um teto ligado sem
    # o consultor pedir interromperia fluxos legitimamente caros (gerar vídeo, um
    # for-each de 20 itens) como se fosse defeito.
    "teto_usd_execucao": 0.0,
    # Tempo (Onda 3, fatia 2). Ambos ZERO = desligados, pelo mesmo motivo do teto de
    # custo: um teto que o consultor não pediu interromperia trabalho legítimo e lento
    # (gerar vídeo leva ~25 min) como se fosse defeito. O do PASSO barra o agente
    # ENTRE ações; o da EXECUÇÃO é conferido entre passos.
    "teto_min_passo": 0,
    "teto_min_execucao": 0,
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
    # Idas-e-vindas de UM portão (apresentar + cada volta com feedback). Vale nas DUAS
    # superfícies — tela e canal. Antes o canal usava outra régua (`max_turnos`/`teto_usd`
    # da conversa inteira): duas fontes de verdade para a mesma regra, que é a receita
    # de bug recorrente — e foi o que estourou em 2026-09-14.
    "portao_max_rodadas": 8,
    # Quanto tempo uma espera por aprovação pode ficar parada antes de virar ALARME.
    # NÃO encerra nada: esperar dias por uma aprovação é legítimo (quem aprova viaja,
    # dorme, tem segunda-feira). O que não é legítimo é o SILÊNCIO — e até 2026-09-21
    # uma aprovação pedida só pela tela, sem canal amarrado, não era varrida por vigia
    # nenhum: ficava parada para sempre sem ninguém saber. 24 h por padrão.
    "teto_espera_humano_min": 1440,
    # E. Vigia de turno preso (§12-A). Eram fixos no `sweeper`: quanto tempo um turno
    # pode ficar "rodando" antes de o vigia declarar que morreu, avisar a pessoa e
    # destravar a conversa. Dois valores porque os casos legítimos são diferentes —
    # atendimento responde rápido; retomada de fluxo pode demorar.
    "teto_turno_preso_min": 8,
    "teto_turno_preso_portao_min": 30,
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
        {"chave": "teto_usd",
         "rotulo": "Teto de custo da conversa — só a IA que conversa",
         "tipo": "valor", "sufixo": "US$"},
        {"chave": "teto_turno_preso_min",
         "rotulo": "Tempo até declarar um turno travado (atendimento)",
         "tipo": "int", "sufixo": "min"},
        {"chave": "teto_turno_preso_portao_min",
         "rotulo": "Tempo até declarar um turno travado (aprovação)",
         "tipo": "int", "sufixo": "min"},
    ]},
    {"grupo": "Limites da execução", "campos": [
        {"chave": "max_passos",
         "rotulo": "Máx. de passos de uma execução",
         "tipo": "int"},
        {"chave": "teto_usd_execucao",
         "rotulo": "Teto de custo por execução — inclui imagem/vídeo (0 = sem teto)",
         "tipo": "valor", "sufixo": "US$"},
        {"chave": "teto_min_passo",
         "rotulo": "Tempo máximo de um passo (0 = sem teto)",
         "tipo": "int", "sufixo": "min"},
        {"chave": "teto_min_execucao",
         "rotulo": "Tempo máximo da execução inteira (0 = sem teto)",
         "tipo": "int", "sufixo": "min"},
    ]},
    {"grupo": "Atendimento ao cliente", "campos": [
        {"chave": "saudacao_abertura", "rotulo": "Saudação no 1º contato (vazio = desligada)", "tipo": "texto"},
        {"chave": "horario_comercial_ativo", "rotulo": "Atender só em horário comercial", "tipo": "bool"},
        {"chave": "horario_inicio", "rotulo": "Abre às", "tipo": "hora"},
        {"chave": "horario_fim", "rotulo": "Fecha às", "tipo": "hora"},
        {"chave": "dias_uteis_apenas", "rotulo": "Só em dias úteis", "tipo": "bool"},
        {"chave": "mensagem_fora_horario", "rotulo": "Mensagem fora do horário", "tipo": "texto"},
    ]},
    {"grupo": "Aprovação humana", "campos": [
        {"chave": "portao_forma", "rotulo": "Como o agente conduz a aprovação", "tipo": "escolha"},
        {"chave": "portao_acao_abandono", "rotulo": "Se o aprovador abandona a conversa", "tipo": "escolha"},
        {"chave": "portao_max_rodadas", "rotulo": "Máx. de idas-e-vindas na aprovação", "tipo": "int"},
        {"chave": "teto_espera_humano_min",
         "rotulo": "Tempo parada até avisar que ninguém aprovou (0 = nunca avisar)",
         "tipo": "int", "sufixo": "min"},
    ]},
]


def painel_config() -> dict:
    """Metadados para a UI montar 'Configurações do fluxo' a partir do backend (fonte
    única): os perfis (com os defaults que cada um aplica), os grupos de botões e o
    padrão global. O front não duplica rótulos/valores."""
    perfis = [
        {
            "id": pid,
            "rotulo": PERFIS_ROTULOS.get(pid, pid),
            "defaults": _mesclar(GLOBAL, PERFIS.get(pid)),
            # Os limites deste perfil em português, para a tela mostrar SEM o usuário
            # ter de abrir o "Avançado" e interpretar números soltos. Lei do maestro:
            # nenhum teto pode existir sem a pessoa saber que existe e onde fica.
            "limites": resumo_dos_limites(_mesclar(GLOBAL, PERFIS.get(pid))),
        }
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
    return {
        "perfis": perfis,
        "grupos": grupos,
        "padrao_global": dict(GLOBAL),
        "limites_padrao": resumo_dos_limites(GLOBAL),
        "onde_mudar": ONDE_MUDAR,
    }


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


# ── Limites: nenhum teto secreto ───────────────────────────────────────────────
# Lei do maestro (2026-09-14): "todo tipo de limitação tem que ser CONFIGURÁVEL, não
# dá pra ter um teto e a gente nem sabe onde isso fica". Então TODO limite (a) mora na
# cascata acima, (b) aparece na tela em português, e (c) quando dispara, se explica —
# dizendo qual foi, quanto valia e onde se muda. Estas três funções são a fonte única
# desses textos: a tela, o recado ao humano e o rastro leem daqui.

# Onde o consultor muda qualquer um destes números (uma frase só, reusada).
ONDE_MUDAR = (
    "Construtor da automação → Configurações do fluxo → Avançado"
)


def resumo_dos_limites(conf: dict) -> list[str]:
    """Os limites EFETIVOS deste fluxo, em português claro — um item por limite.

    Serve ao painel (o consultor lê sem abrir o 'Avançado') e ao recado honesto. Zero
    em teto de custo/tempo significa DESLIGADO, e isso é dito com todas as letras em
    vez de mostrar um "0" que ninguém interpreta."""

    def _n(chave: str, padrao=0):
        try:
            return type(padrao)(conf.get(chave, padrao) or padrao)
        except (TypeError, ValueError):
            return padrao

    def _teto(valor, texto: str) -> str:
        return texto if valor else "sem teto"

    usd_conversa = float(_n("teto_usd", 0.0))
    usd_exec = float(_n("teto_usd_execucao", 0.0))
    min_passo = int(_n("teto_min_passo", 0))
    min_exec = int(_n("teto_min_execucao", 0))
    execucao = [f"até {int(_n('max_passos', 25))} passos"]
    if usd_exec:
        execucao.append(f"US$ {usd_exec:.2f} de custo (inclui imagem e vídeo)")
    if min_exec:
        execucao.append(f"{min_exec} min de duração")
    if min_passo:
        execucao.append(f"{min_passo} min por passo")
    if not (usd_exec or min_exec or min_passo):
        execucao.append("sem teto de custo nem de tempo")
    return [
        f"Aprovação: até {int(_n('portao_max_rodadas', 8))} idas-e-vindas por portão; "
        "passado isso, a resposta segue direto pelo caminho que ela indicar.",
        f"Conversa: até {int(_n('max_turnos', 40))} mensagens e "
        f"{_teto(usd_conversa, f'US$ {usd_conversa:.2f}')} de IA de conversa "
        "(gerar imagem/vídeo não conta aqui — conta no teto da execução).",
        "Execução: " + ", ".join(execucao) + ".",
        f"Turno travado: o vigia destrava e avisa em {int(_n('teto_turno_preso_min', 8))} min "
        f"(atendimento) ou {int(_n('teto_turno_preso_portao_min', 30))} min (aprovação).",
    ]


# Os limites que podem interromper uma aprovação em andamento, com o nome que a
# pessoa entende e a chave que ela procura na tela. Fonte única do recado e do rastro.
LIMITES_DO_PORTAO = {
    "rodadas": ("idas-e-vindas desta aprovação", "portao_max_rodadas"),
    "custo": ("custo de IA desta conversa", "teto_usd"),
    "mensagens": ("mensagens desta conversa", "max_turnos"),
}


def explicacao_limite_portao(qual: str, conf: dict, *, valor_atual: str) -> str:
    """O recado HONESTO quando um limite interrompe a condução de uma aprovação.

    Substitui o antigo "Vou te encaminhar para um atendente humano. Um instante." —
    que não dizia o que tinha acontecido, não dizia o que fazer, e (pior) vinha junto
    com o canal ficando surdo. Diz as quatro coisas que importam: o QUE acabou, QUANTO
    valia, que o trabalho NÃO se perdeu, e ONDE se muda o número."""
    rotulo, chave = LIMITES_DO_PORTAO.get(qual, (qual, qual))
    return (
        f"Atingi o limite de {rotulo} ({valor_atual}), então não vou continuar "
        f"refazendo o material nesta conversa.\n\n"
        f"Nada se perdeu: sua última resposta vale e o fluxo segue por ela. Se quiser "
        f"rever o material inteiro ou responder com calma, ele está em {URL_APP}.\n\n"
        f"Para mudar esse limite: {ONDE_MUDAR} → “{_rotulo_do_campo(chave)}”."
    )


def _rotulo_do_campo(chave: str) -> str:
    """O rótulo que a tela mostra para esta chave (para o recado apontar o botão pelo
    nome que a pessoa vê, não pelo nome técnico)."""
    for grupo in CAMPOS:
        for campo in grupo["campos"]:
            if campo["chave"] == chave:
                return campo["rotulo"]
    return chave
