"""Diagnóstico de execução — LEITURA pura, sem LLM, sem escrita.

Dado o id de uma execução, reúne os fatos relevantes (estado, passos enxutos, nó
pausado, cinto dos agentes, canais de aprovação, conversas vinculadas, webhook
disparado) e roda VERIFICAÇÕES DETERMINÍSTICAS, devolvendo `avisos` priorizados —
o porquê de a execução ter falhado ou ficado parada, em linguagem de máquina. Quem
traduz para o consultor é a IA companheira (guiada pelo prompt).

É a FONTE ÚNICA de "como ler/diagnosticar uma execução": usada pela IA companheira
(`criacao.ferramentas`), pelo script `scripts/inspecionar_exec.py` e por futuros
endpoints. NÃO controla acesso (recebe `execucao_id` já validado pelo chamador) e
NUNCA vaza segredo — só informa se um canal "tem token", nunca o valor.

Verificações (cada uma vira um aviso): `ia_sobrecarregada`, `falha_instrumento`,
`falha_generica`, `presa_orfa`, `em_andamento_sem_progresso`, `preso_aguardando`,
`aprovacao_pendente_normal`, `portao_sem_entrega`, `canal_sem_token`,
`portao_so_tela`, `cancelada`, `webhook_disparou_alvo` (segue 1 hop, só na mesma
organização — o motor do webhook cria uma execução-alvo noutra automação).
"""

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import segredos_instrumento
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
from orquestracao import grafo

# Truncagem dos textos longos (artigos): o diagnóstico é lido por uma IA paga, então
# resumimos antes — o porquê está nos `avisos`, não no corpo dos passos.
MAX_TRECHO = 280
MAX_PASSOS = 12
# (Fatia 3) Limiar de "travada" (sem progresso além disto) — FONTE ÚNICA com o sweeper:
# importado de `fila`, não redefinido, para as duas pontas nunca divergirem.
from fila import TETO_INATIVIDADE_EXEC_MIN as LIMIAR_PRESO_MIN  # noqa: E402
# Acima disto na FILA (sem começar) já é suspeito (pool parado / fila cheia).
LIMIAR_FILA_MIN = 5

CANAIS_TIPOS = {"enviar_telegram", "enviar_whatsapp"}
# Campos de segredo que contam como "token de autenticação" de um canal/instrumento.
CAMPOS_TOKEN = ("token_bot", "token_bearer", "token", "api_key")
_PADRAO_WEBHOOK = re.compile(r"/webhooks/automacoes/([0-9a-fA-F-]{36})")
_ORDEM_SEVERIDADE = {"erro": 0, "alerta": 1, "info": 2}


# ───────────────────────────── utilidades ─────────────────────────────

def _coagir_uuid(valor) -> uuid.UUID | None:
    if isinstance(valor, uuid.UUID):
        return valor
    try:
        return uuid.UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        return None


def _trunc(valor, n: int = MAX_TRECHO) -> str | None:
    if valor is None:
        return None
    s = str(valor)
    return s if len(s) <= n else s[:n] + f"… (+{len(s) - n} chars)"


def _aware(dt: datetime | None) -> datetime | None:
    """Garante datetime com fuso (o banco grava aware; defensivo p/ naive=UTC)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _idade_min(dt: datetime | None) -> float | None:
    dt = _aware(dt)
    if dt is None:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0


def _aviso(
    codigo: str, severidade: str, titulo: str, detalhe: str, *,
    acao: dict | None = None, agente_id=None, instrumento_id=None,
) -> dict:
    return {
        "codigo": codigo,
        "severidade": severidade,  # erro | alerta | info
        "titulo": titulo,
        "detalhe": detalhe,
        "referencias": {
            "agente_id": str(agente_id) if agente_id else None,
            "instrumento_id": str(instrumento_id) if instrumento_id else None,
        },
        # acao_sugerida.tipo ∈ {encaixar_instrumento, editar_agente, editar_instrumento
        # (a IA aplica) | conectar_bot, cadastrar_token (exige o maestro) |
        # aprovar_pela_tela, aguardar (orientação)}.
        "acao_sugerida": acao,
    }


def resumo_estado(estado: str, resultado: dict | None) -> str:
    """Frase curta sobre o estado de uma execução (usada na listagem e no resumo)."""
    if estado == "concluida":
        return "Concluída com sucesso."
    if estado == "falhou":
        return "Falhou: " + (_trunc((resultado or {}).get("erro"), 120) or "erro não registrado")
    if estado == "aguardando_humano":
        return "Parada esperando uma aprovação humana."
    if estado == "em_andamento":
        return "Ainda em andamento."
    if estado == "aguardando":
        return "Na fila, ainda não começou."
    if estado == "cancelada":
        return "Cancelada."
    return estado


def _instrumento_resumo(sessao: Session, inst: Instrumento) -> dict:
    """Resumo seguro de um instrumento do cinto: nunca o valor do segredo, só QUAIS
    campos secretos estão preenchidos (nome do campo não é segredo)."""
    campos = segredos_instrumento.resumo(sessao, inst.id)  # {campo: ultimos4}
    return {
        "id": str(inst.id),
        "nome": inst.nome,
        "tipo": inst.tipo,
        "segredos_presentes": sorted(campos.keys()),
        "tem_token": any(c in campos for c in CAMPOS_TOKEN),
    }


def _cinto(sessao: Session, agente_id) -> list[dict]:
    if agente_id is None:
        return []
    insts = sessao.scalars(
        select(Instrumento)
        .join(AgenteInstrumento, AgenteInstrumento.instrumento_id == Instrumento.id)
        .where(AgenteInstrumento.agente_id == agente_id)
    ).all()
    return [_instrumento_resumo(sessao, i) for i in insts]


def _acionou(inst: Instrumento, acionados: list) -> bool:
    """Se o instrumento aparece em `instrumentos_acionados` do passo. O nome da
    ferramenta termina em `_<id.hex[:8]>` (ver agente._nome_de_ferramenta) — casar
    pelo sufixo é robusto à sanitização do nome."""
    sufixo = "_" + inst.id.hex[:8]
    return any(str(n).endswith(sufixo) for n in (acionados or []))


# ───────────────────────────── coleta de fatos ─────────────────────────────

def _no_pausado(auto: Automacao | None, passos: list[PassoExecucao]) -> tuple[str | None, dict]:
    """(no_id, nó do grafo) onde a execução pausou — pelo último passo, igual a
    `aprovacao._config_aprovacao_do_no`."""
    if auto is None or not passos:
        return (None, {})
    ultimo = passos[-1]
    no_id = ultimo.no_id or (str(ultimo.agente_id) if ultimo.agente_id else None)
    if not no_id:
        return (None, {})
    idx = grafo.indexar(grafo.normalizar(auto.cadeia or {}))
    return (no_id, idx.no(no_id) or {})


def _detectar_webhook(sessao: Session, passos: list[PassoExecucao]):
    """Acha o disparo de webhook mais recente entre os passos. Devolve
    (instrumento, url, automacao_id_alvo|None) — automacao_id_alvo só quando a URL
    aponta para um webhook de automação do próprio Batuta."""
    for p in reversed(passos):
        acionados = (p.saida or {}).get("instrumentos_acionados") or []
        if not acionados or p.agente_id is None:
            continue
        insts = sessao.scalars(
            select(Instrumento)
            .join(AgenteInstrumento, AgenteInstrumento.instrumento_id == Instrumento.id)
            .where(AgenteInstrumento.agente_id == p.agente_id)
            .where(Instrumento.tipo == "disparar_webhook")
        ).all()
        for inst in insts:
            if not _acionou(inst, acionados):
                continue
            url = (inst.configuracao or {}).get("url") or ""
            m = _PADRAO_WEBHOOK.search(url)
            alvo = _coagir_uuid(m.group(1)) if m else None
            return inst, url, alvo
    return None, None, None


def _org_do_time(sessao: Session, time_id) -> uuid.UUID | None:
    t = sessao.get(Time, time_id) if time_id else None
    return t.organizacao_id if t else None


# ───────────────────────────── diagnóstico ─────────────────────────────

def diagnosticar(sessao: Session, execucao_id, *, seguir_webhook: bool = True) -> dict:
    """Diagnóstico de leitura de UMA execução. `seguir_webhook=False` corta a
    recursão (1 hop) ao inspecionar a execução-alvo de um webhook."""
    eid = _coagir_uuid(execucao_id)
    ex = sessao.get(Execucao, eid) if eid else None
    if ex is None:
        return {"encontrada": False, "execucao_id": str(execucao_id)}

    auto = sessao.get(Automacao, ex.automacao_id)
    passos = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == ex.id)
        .order_by(PassoExecucao.ordem)
    ).all()
    # Nomes só dos agentes que apareceram nos passos (o do nó pausado é o último
    # passo) — evita varrer a tabela inteira de agentes.
    ids_agentes = {p.agente_id for p in passos if p.agente_id}
    nomes = (
        {a.id: a.nome for a in sessao.scalars(
            select(Agente).where(Agente.id.in_(ids_agentes))
        ).all()}
        if ids_agentes else {}
    )

    resultado = ex.resultado or {}
    no_id, no = _no_pausado(auto, passos)

    d: dict = {
        "encontrada": True,
        "execucao_id": str(ex.id),
        "estado": ex.estado,
        "resumo": resumo_estado(ex.estado, resultado),
        "automacao": {
            "id": str(auto.id) if auto else None,
            "nome": auto.nome if auto else None,
            "time_id": str(auto.time_id) if auto else None,
            "tipo_gatilho": auto.tipo_gatilho if auto else None,
        },
        "criada_em": (_aware(ex.criado_em).isoformat() if ex.criado_em else None),
        "iniciada_em": (_aware(ex.iniciada_em).isoformat() if ex.iniciada_em else None),
        "finalizada_em": (_aware(ex.finalizada_em).isoformat() if ex.finalizada_em else None),
        "entrada_resumo": _trunc((ex.entrada or {}).get("texto")),
        "erro": _trunc(resultado.get("erro")) if ex.estado == "falhou" else None,
        "total_passos": len(passos),
        "passos": [
            {
                "ordem": p.ordem,
                "no_id": p.no_id,
                "agente_nome": nomes.get(p.agente_id),
                "estado": p.estado,
                "saida_resumo": _trunc((p.saida or {}).get("texto")),
                "instrumentos_acionados": (p.saida or {}).get("instrumentos_acionados") or [],
            }
            for p in passos[-MAX_PASSOS:]
        ],
        "no_pausado": None,
        "cinto_dos_agentes": {},
        "canais_de_aprovacao": [],
        "conversas_vinculadas": [],
        "webhook_alvo": None,
        "avisos": [],
    }

    avisos: list[dict] = []

    # ── Falhou: ler o erro e classificá-lo ──
    if ex.estado == "falhou":
        _verificar_falha(sessao, d, ex, passos, avisos, nomes)

    # ── Parada num portão: confirmar se o aviso de aprovação chegou ──
    elif ex.estado == "aguardando_humano":
        _verificar_portao(sessao, d, ex, no_id, no, passos, avisos, nomes)

    # ── Presa rodando sem progresso ──
    elif ex.estado == "em_andamento":
        heartbeat = _aware(ex.iniciada_em)
        for p in passos:
            if p.finalizado_em and (heartbeat is None or _aware(p.finalizado_em) > heartbeat):
                heartbeat = _aware(p.finalizado_em)
        idade = _idade_min(heartbeat)
        if idade is not None and idade > LIMIAR_PRESO_MIN:
            avisos.append(_aviso(
                "em_andamento_sem_progresso", "alerta",
                "Travada sem avançar",
                f"Está 'em andamento' há ~{int(idade)} min sem concluir um passo. O Batuta "
                "marca como falha sozinho quando passa do tempo limite; aí dá para rodar de novo.",
                acao={"tipo": "aguardar"},
            ))

    # ── Presa na fila, sem começar ──
    elif ex.estado == "aguardando":
        idade = _idade_min(ex.iniciada_em or ex.criado_em)
        if idade is not None and idade > LIMIAR_FILA_MIN:
            avisos.append(_aviso(
                "preso_aguardando", "alerta",
                "Parada na fila",
                f"Está na fila há ~{int(idade)} min sem começar. Pode ser fila cheia ou o "
                "processador de execuções parado.",
                acao={"tipo": "aguardar"},
            ))

    elif ex.estado == "cancelada":
        avisos.append(_aviso(
            "cancelada", "info", "Cancelada",
            _trunc(resultado.get("texto")) or "A execução foi cancelada.",
            acao={"tipo": "aguardar"},
        ))

    # ── Instrumento que falhou mas o fluxo SEGUIU (leitura/geração) ──
    # Não fica visível no estado (a execução "concluiu"); o erro cru mora no passo.
    _verificar_erros_instrumentos(d, passos, avisos)

    # ── Conversa rodando SEM memória entre turnos (modo degradado) ──
    _verificar_memoria_legado(ex, passos, avisos)

    # ── Seguir o webhook (1 hop, mesma organização) ──
    if seguir_webhook:
        _verificar_webhook(sessao, d, auto, passos, avisos)

    avisos.sort(key=lambda a: _ORDEM_SEVERIDADE.get(a["severidade"], 9))
    d["avisos"] = avisos
    return d


def _verificar_falha(sessao, d, ex, passos, avisos, nomes) -> None:
    erro = (ex.resultado or {}).get("erro") or ""
    low = erro.lower()
    if "529" in erro or "overloaded" in low or "sobrecarregad" in low:
        avisos.append(_aviso(
            "ia_sobrecarregada", "alerta",
            "A IA estava sobrecarregada",
            "A falha foi uma sobrecarga temporária do provedor de IA (não é erro de "
            "configuração do time). Rodar de novo costuma resolver.",
            acao={"tipo": "aguardar"},
        ))
        return
    if any(t in low for t in ("travada", "reinício", "reinicio", "interrompida por reinício")):
        avisos.append(_aviso(
            "presa_orfa", "alerta",
            "Interrompida por instabilidade",
            "A execução foi interrompida (travamento ou reinício do serviço), não por um "
            "erro de configuração. Rodar de novo costuma resolver.",
            acao={"tipo": "aguardar"},
        ))
        return
    if any(t in low for t in (
        "o instrumento", "acesso negado", "http 401", "http 403",
        "não configurado", "nao configurado", "verifique a autenticação",
    )):
        # Tenta apontar o instrumento envolvido (último passo com instrumentos).
        inst = _instrumento_da_falha(sessao, passos)
        ref = {"instrumento_id": inst.id, "agente_id": None} if inst else {}
        avisos.append(_aviso(
            "falha_instrumento", "erro",
            "Um instrumento falhou",
            f"A execução parou por causa de um instrumento: «{_trunc(erro, 180)}». Confira a "
            "configuração/credencial dele.",
            acao={"tipo": "editar_instrumento", "instrumento_id": str(inst.id)} if inst else
                 {"tipo": "cadastrar_token"},
            **ref,
        ))
        return
    avisos.append(_aviso(
        "falha_generica", "erro",
        "A execução falhou",
        _trunc(erro, 220) or "Falhou sem erro registrado.",
        acao={"tipo": "aguardar"},
    ))


def _verificar_erros_instrumentos(d, passos, avisos) -> None:
    """Aviso para cada instrumento de LEITURA/GERAÇÃO que falhou sem derrubar a
    execução (ex.: `gerar_video` recusado por dimensão/moderação). Esse erro é
    "engolido" — o agente narra à sua maneira e o estado fica "concluída" —, então
    aqui trazemos o TEXTO CRU que o instrumento devolveu. Falhas de ação IRREVERSÍVEL
    por exceção já aparecem via `_verificar_falha` (a execução fica 'falhou') — não
    repetimos. EXCEÇÃO da exceção: `origem="resposta"` (a falha voltou como DADO,
    ex.: HTTP 4xx do REST/conector) nunca muda o estado da execução — mesmo numa
    ação irreversível o agente segue e pode narrar sucesso; o aviso é o único lugar
    onde essa falha aparece, então ele SEMPRE sai."""
    for p in passos:
        for e in (p.saida or {}).get("erros_instrumentos") or []:
            de_resposta = e.get("origem") == "resposta"
            if e.get("irreversivel") and not de_resposta:
                continue
            if de_resposta:
                detalhe = (
                    f"No passo {p.ordem}, «{e.get('ferramenta')}» respondeu com falha: "
                    f"{_trunc(e.get('erro'), 240)}. O agente recebeu essa falha como "
                    "resposta e decidiu sozinho como seguir — confira se a ação foi "
                    "de fato concluída antes de confiar no que ele narrou."
                )
            else:
                detalhe = (
                    f"No passo {p.ordem}, «{e.get('ferramenta')}» não concluiu: "
                    f"{_trunc(e.get('erro'), 240)}. O fluxo seguiu (não é ação "
                    "irreversível), mas o resultado desse passo pode estar incompleto."
                )
            avisos.append(_aviso(
                "instrumento_falhou_seguiu", "alerta",
                f"O instrumento «{e.get('ferramenta')}» falhou",
                detalhe,
                acao=(
                    {"tipo": "editar_instrumento", "instrumento_id": e.get("instrumento_id")}
                    if e.get("instrumento_id") else {"tipo": "aguardar"}
                ),
                instrumento_id=_coagir_uuid(e.get("instrumento_id")),
            ))


def _verificar_memoria_legado(ex, passos, avisos) -> None:
    """Aviso quando uma CONVERSA rodou turno(s) no modo LEGADO (sem memória entre
    turnos): o agente re-deriva do texto — re-busca dados, perde resultados de
    ferramenta e a trava nativa de aprovação fica inativa. É modo degradado (o
    checkpointer caiu); o carimbo `saida.memoria` de cada turno é quem denuncia.
    Passos antigos (sem o carimbo) não geram aviso."""
    if getattr(ex, "modo", None) != "conversa":
        return
    legados = [p.ordem for p in passos if (p.saida or {}).get("memoria") == "legado"]
    if not legados:
        return
    avisos.append(_aviso(
        "conversa_sem_memoria", "alerta",
        "Conversa rodou sem memória entre turnos",
        f"{len(legados)} turno(s) desta conversa rodaram no modo degradado (sem o fio "
        "salvo): o agente recomeça do texto a cada turno e a trava nativa de aprovação "
        "fica inativa. Verifique os logs do sistema (memoria.checkpointer_indisponivel) "
        "e o serviço do cérebro.",
        acao={"tipo": "aguardar"},
    ))


def _instrumento_da_falha(sessao, passos) -> Instrumento | None:
    """O instrumento provável da falha: do último passo que acionou algo, o primeiro
    de ação irreversível (publicar/enviar) que aparece. Best-effort."""
    for p in reversed(passos):
        acionados = (p.saida or {}).get("instrumentos_acionados") or []
        if not acionados or p.agente_id is None:
            continue
        insts = sessao.scalars(
            select(Instrumento)
            .join(AgenteInstrumento, AgenteInstrumento.instrumento_id == Instrumento.id)
            .where(AgenteInstrumento.agente_id == p.agente_id)
        ).all()
        acionou = [i for i in insts if _acionou(i, acionados)]
        if acionou:
            return acionou[-1]
    return None


def _verificar_portao(sessao, d, ex, no_id, no, passos, avisos, nomes) -> None:
    gate_agente_id = _coagir_uuid(no.get("ref"))
    aprovacao = no.get("aprovacao") or {}
    inst_id = _coagir_uuid(aprovacao.get("instrumento_id"))
    cinto = _cinto(sessao, gate_agente_id)

    d["no_pausado"] = {
        "no_id": no_id,
        "gate": bool(no.get("gate")),
        "agente_id": str(gate_agente_id) if gate_agente_id else None,
        "agente_nome": nomes.get(gate_agente_id),
        "aprovacao": {
            "tem_instrumento_id": inst_id is not None,
            "destinatario": aprovacao.get("destinatario"),
        },
    }
    if gate_agente_id:
        d["cinto_dos_agentes"][str(gate_agente_id)] = cinto

    # Conversas vinculadas a esta execução (correlação do portão por canal).
    convs = sessao.scalars(select(Conversa).where(Conversa.execucao_id == ex.id)).all()
    d["conversas_vinculadas"] = [
        {"id": str(c.id), "estado": c.estado, "contato_chave": c.contato_chave}
        for c in convs
    ]

    canais_no_cinto = [i for i in cinto if i["tipo"] in CANAIS_TIPOS]
    # O agente ENTREGOU o pedido? (acionou um canal no passo pausado)
    ultimo = passos[-1] if passos else None
    acionados_ultimo = (ultimo.saida or {}).get("instrumentos_acionados") if ultimo else []
    entregou = any(
        str(n).endswith("_" + i["id"].replace("-", "")[:8]) for i in canais_no_cinto
        for n in (acionados_ultimo or [])
    )

    # Portão sem canal de aprovação configurado no nó → só resolve pela tela.
    if inst_id is None:
        avisos.append(_aviso(
            "portao_so_tela", "info",
            "Aprovação só pela tela",
            "Esta etapa pede aprovação humana, mas não tem um canal (Telegram) configurado "
            "para avisar. Aprove pela tela da execução para destravar.",
            acao={"tipo": "aprovar_pela_tela"},
        ))
        return

    canal = sessao.get(Instrumento, inst_id)
    canal_resumo = _instrumento_resumo(sessao, canal) if canal else None
    if canal_resumo:
        d["canais_de_aprovacao"] = [canal_resumo]
    canal_tem_token = bool(canal_resumo and "token_bot" in canal_resumo["segredos_presentes"])

    # (a) O aviso não foi entregue: o agente do portão não acionou nenhum canal.
    if not entregou:
        if canais_no_cinto:
            detalhe = (
                "O agente desta etapa tem um canal no cinto, mas não enviou o pedido de "
                "aprovação nesta rodada — provavelmente a documentação dele não manda enviar."
            )
            acao = {"tipo": "editar_agente", "agente_id": str(gate_agente_id)}
        else:
            detalhe = (
                "O agente desta etapa NÃO tem um canal de mensagem no cinto, então não teve "
                "como te enviar o pedido de aprovação. Encaixe o canal no cinto dele."
            )
            acao = {
                "tipo": "encaixar_instrumento",
                "agente_id": str(gate_agente_id),
                "instrumento_id": str(inst_id),
            }
        avisos.append(_aviso(
            "portao_sem_entrega", "erro",
            "O pedido de aprovação não foi entregue",
            detalhe, acao=acao, agente_id=gate_agente_id, instrumento_id=inst_id,
        ))

    # (b) O canal de aprovação não está conectado (sem token).
    if canal and not canal_tem_token:
        avisos.append(_aviso(
            "canal_sem_token", "erro",
            "O canal de aprovação não está conectado",
            f"O canal «{canal.nome}» configurado para avisar não tem um bot conectado (falta o "
            "token). Conecte o bot para os pedidos de aprovação chegarem.",
            acao={"tipo": "conectar_bot", "instrumento_id": str(inst_id)},
            instrumento_id=inst_id,
        ))

    # (c) Tudo certo: entregou e o canal está conectado — só falta o humano aprovar.
    if entregou and canal_tem_token:
        avisos.append(_aviso(
            "aprovacao_pendente_normal", "info",
            "Esperando sua aprovação",
            "A etapa enviou o pedido e está apenas aguardando você aprovar (pela tela ou pelo "
            "canal). Nenhum problema de configuração.",
            acao={"tipo": "aprovar_pela_tela"},
        ))


def _verificar_webhook(sessao, d, auto, passos, avisos) -> None:
    inst, url, alvo_id = _detectar_webhook(sessao, passos)
    if inst is None:
        return

    # Webhook externo (URL não é de uma automação do Batuta): só registra.
    if alvo_id is None:
        d["webhook_alvo"] = {"url_origem": _trunc(url, 120), "fora_de_alcance": True}
        avisos.append(_aviso(
            "webhook_disparou_externo", "info",
            "Disparou um webhook externo",
            f"Esta execução chamou um sistema externo em {_trunc(url, 100)}.",
            acao={"tipo": "aguardar"},
        ))
        return

    alvo_auto = sessao.get(Automacao, alvo_id)
    org_origem = _org_do_time(sessao, auto.time_id) if auto else None
    org_alvo = _org_do_time(sessao, alvo_auto.time_id) if alvo_auto else None

    # Automação-alvo de outra organização (ou inexistente): fora de alcance.
    if alvo_auto is None or org_alvo is None or org_alvo != org_origem:
        d["webhook_alvo"] = {
            "automacao_id": str(alvo_id),
            "automacao_nome": alvo_auto.nome if alvo_auto else None,
            "url_origem": _trunc(url, 120),
            "fora_de_alcance": True,
            "execucao_alvo": None,
        }
        avisos.append(_aviso(
            "webhook_disparou_alvo", "info",
            "Disparou outra automação",
            "O webhook disparou uma automação de outra organização — não consigo inspecionar "
            "o que aconteceu lá.",
            acao={"tipo": "aguardar"},
        ))
        return

    # Execução-alvo mais recente da automação-alvo (a que este disparo iniciou).
    alvo_exec = sessao.scalars(
        select(Execucao)
        .where(Execucao.automacao_id == alvo_auto.id)
        .order_by(Execucao.criado_em.desc())
    ).first()

    if alvo_exec is None:
        d["webhook_alvo"] = {
            "automacao_id": str(alvo_id),
            "automacao_nome": alvo_auto.nome,
            "url_origem": _trunc(url, 120),
            "fora_de_alcance": False,
            "execucao_alvo": None,
        }
        avisos.append(_aviso(
            "webhook_disparou_alvo", "alerta",
            "O webhook não iniciou nada",
            f"O webhook aponta para a automação «{alvo_auto.nome}», mas não há execução dela — "
            "confira se essa automação está ATIVA e é do tipo webhook.",
            acao={"tipo": "aguardar"},
        ))
        return

    # 1 hop: diagnostica a execução-alvo (sem seguir webhooks de novo).
    alvo_diag = diagnosticar(sessao, alvo_exec.id, seguir_webhook=False)
    alvo_avisos = alvo_diag.get("avisos") or []
    d["webhook_alvo"] = {
        "automacao_id": str(alvo_auto.id),
        "automacao_nome": alvo_auto.nome,
        "time_id": str(alvo_auto.time_id),
        "mesmo_time": bool(auto and alvo_auto.time_id == auto.time_id),
        "url_origem": _trunc(url, 120),
        "fora_de_alcance": False,
        "execucao_alvo": {
            "id": str(alvo_exec.id),
            "estado": alvo_exec.estado,
            "resumo": alvo_diag.get("resumo"),
            "avisos": alvo_avisos,
            "no_pausado": alvo_diag.get("no_pausado"),
            "cinto_dos_agentes": alvo_diag.get("cinto_dos_agentes"),
            "canais_de_aprovacao": alvo_diag.get("canais_de_aprovacao"),
        },
    }
    # A severidade do disparo herda o pior aviso da execução-alvo.
    pior = min((_ORDEM_SEVERIDADE.get(a["severidade"], 9) for a in alvo_avisos), default=2)
    severidade = {0: "erro", 1: "alerta", 2: "info"}.get(pior, "info")
    titulos_alvo = "; ".join(a["titulo"] for a in alvo_avisos[:3]) or "sem problemas detectados"
    avisos.append(_aviso(
        "webhook_disparou_alvo", "info" if severidade == "info" else "alerta",
        "Disparou outra automação",
        f"O webhook INICIOU a execução {str(alvo_exec.id)[:8]} da automação «{alvo_auto.nome}» — "
        f"ela está '{alvo_exec.estado}' ({titulos_alvo}). Veja `webhook_alvo` para os detalhes.",
        acao={"tipo": "aguardar"},
    ))
