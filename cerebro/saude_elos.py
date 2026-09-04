"""Vigia dos ELOS — sonda ativa de cada ligação da corrente do Batuta (§12-A).

Nasceu do incidente de 2026-08-27: a rede até o pooler do Supabase congelou por ~30
minutos e NINGUÉM ficou sabendo — o app respondia HTTP, o `/saude` dizia "tudo de pé"
(ele só lê estado em memória) e o usuário via um bot mudo. A lição: "no ar" não é a
mesma coisa que "cada ligação funcionando". Este módulo sonda ATIVAMENTE cada elo —
banco, memória, provedores de IA, canais, borda pública, MCP, threads internas — em
períodos curtos, guarda o resultado em memória e:

- expõe a foto em `GET /saude/elos` (a página de status da interface lê daqui);
- registra EVENTO no banco de logs em toda transição (`elo.caiu` / `elo.voltou` /
  `elo.reconectado`) — histórico consultável em `/logs`;
- AUTO-CURA os elos de banco (2 falhas seguidas → derruba o pool e reconecta), e
  oferece reconexão por botão (`POST /saude/elos/{id}/reconectar`) para os demais
  elos que têm cura possível.

Toda sonda tem timeout curto e não gasta token de IA nem toca API de cliente (os
instrumentos do cliente são testados SOB DEMANDA pelo Construtor, não aqui).
"""

import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx
from sqlalchemy import select, text

import arquivos
import db
import segredos_instrumento
from chaves import resolver_chaves_por_organizacao
from modelos import Instrumento
from observabilidade.escritor import registrar_evento
from orquestracao import memoria_conversa
from orquestracao.modelos_ia import (
    PROVEDOR_ANTHROPIC,
    PROVEDOR_GOOGLE,
    PROVEDOR_OPENAI,
)
from sessao import CriadorDeSessao

logger = logging.getLogger(__name__)

TIMEOUT_SONDA_S = 5.0
# Auto-cura: quantas falhas SEGUIDAS antes de reconectar sozinho (1 falha isolada
# pode ser um soluço; 2 seguidas com período de 30 s já é indisponibilidade real).
FALHAS_PARA_AUTOCURA = 2

# Períodos por grupo (segundos). Internos/banco são baratos e críticos → 30 s.
# Externos respeitam os limites dos serviços → 60 s (Meta: 300 s).
PERIODO_BANCO_S = 30
PERIODO_INTERNO_S = 30
PERIODO_EXTERNO_S = 60
PERIODO_META_S = 300


class EloDegradado(Exception):
    """A sonda passou, mas com ressalva (ex.: webhook com erros de entrega)."""


@dataclass
class Elo:
    id: str
    nome: str
    grupo: str  # banco | ia | canais | borda | interno
    periodo_s: int
    sonda: Callable[[], str | None]  # devolve detalhe (ou None); levanta em falha
    reconectar: Callable[[], None] | None = None
    auto_cura: bool = False


_lock = threading.Lock()
# id do elo → {estado, detalhe, erro, latencia_ms, verificado_em, falhas_seguidas,
#              desde (quando entrou no estado atual)}
_estado: dict[str, dict] = {}
_proxima: dict[str, float] = {}  # id → monotonic da próxima sonda


# ───────────────────────────── tradução de erro ──────────────────────────────


def _traduzir(e: Exception) -> str:
    """O erro da sonda em português de gente — rede × credencial × quota × banco."""
    if isinstance(e, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout)):
        return "sem resposta dentro do tempo limite (rede lenta ou serviço travado)"
    if isinstance(e, httpx.ConnectError):
        return "não foi possível conectar (rede fora ou serviço inacessível)"
    if isinstance(e, httpx.HTTPStatusError):
        st = e.response.status_code
        if st in (401, 403):
            return f"credencial recusada pelo serviço (HTTP {st})"
        if st == 429:
            return "limite de requisições atingido no serviço (quota)"
        return f"o serviço respondeu com erro (HTTP {st})"
    texto = str(e) or type(e).__name__
    if "couldn't get a connection" in texto:
        return "o pool não conseguiu emprestar uma conexão a tempo (banco fora ou congelado)"
    if "timeout" in texto.lower():
        return "sem resposta dentro do tempo limite"
    return texto[:300]


# ─────────────────────────────── sondas ──────────────────────────────────────


def _sonda_banco() -> str | None:
    with db.engine.connect() as conn:
        conn.execute(text("select 1"))
    return None


def _reconectar_banco() -> None:
    # Derruba TODAS as conexões do pool; as próximas consultas abrem conexões novas.
    db.engine.dispose()


def _sonda_memoria() -> str | None:
    if not memoria_conversa.esta_saudavel():
        raise RuntimeError(
            "memória de conversa em modo legado (checkpointer não subiu)"
        )
    memoria_conversa.sondar()
    return None


def _reconectar_memoria() -> None:
    memoria_conversa.reconectar()


def _sonda_fila() -> str | None:
    import fila

    if not fila.esta_saudavel():
        raise RuntimeError("pool de trabalhadores da fila está parado")
    return None


def _reconectar_fila() -> None:
    import fila

    if not fila.esta_saudavel():  # nunca duplicar trabalhadores vivos
        fila.iniciar()


def _sonda_agendador() -> str | None:
    import agendador

    if not agendador.esta_saudavel():
        raise RuntimeError("relógio dos gatilhos está parado")
    return None


def _reconectar_agendador() -> None:
    import agendador

    if not agendador.esta_saudavel():
        agendador.iniciar()


def _sonda_vigia_mensageria() -> str | None:
    from mensageria import sweeper

    ultima = sweeper.ULTIMA_VARREDURA_EM
    if ultima is None:
        raise EloDegradado("aguardando a primeira varredura desde o boot")
    atraso = (datetime.now(timezone.utc) - ultima).total_seconds()
    if atraso > 180:
        raise RuntimeError(
            f"a última varredura foi há {int(atraso // 60)} min (deveria ser a cada 1 min)"
        )
    return f"última varredura há {int(atraso)} s"


def _sonda_vigias_execucao() -> str | None:
    """Os vigias que soltam execução PAUSADA estão rodando?

    O padrão das Ondas 3 e 4 é: a execução pausa e um vigia a solta. Se o vigia morre,
    ela fica parada para sempre — e, sem esta sonda, em silêncio: o `agendador` continua
    "saudável" porque `_scheduler.running` só diz que o relógio gira, não que os jobs
    disparam. É a §12-A um nível acima: nenhum vigia sem quem o vigie."""
    import vigias

    quebrados = vigias.quebrados()
    if quebrados:
        raise RuntimeError(
            "; ".join(vigias.frase_do_atraso(n, a) for n, a in quebrados)
        )
    if vigias.nunca_rodaram():
        # No boot os jobs ainda não deram a primeira volta. Degradado (amarelo), não
        # quebrado: um app que acabou de subir não tem atraso nenhum a explicar.
        raise EloDegradado("aguardando a primeira volta desde o boot")
    return vigias.resumo_em_dia()


# Sondas dos provedores de IA: o endpoint de LISTAR MODELOS é grátis (não gera
# token) e valida rede + chave de uma vez. Só os provedores com chave no cofre
# viram elo (resolvidos pela cascata da consultoria, sem org).
_SONDAS_IA = {
    PROVEDOR_ANTHROPIC: lambda chave, cli: cli.get(
        "https://api.anthropic.com/v1/models?limit=1",
        headers={"x-api-key": chave, "anthropic-version": "2023-06-01"},
    ),
    PROVEDOR_OPENAI: lambda chave, cli: cli.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {chave}"},
    ),
    PROVEDOR_GOOGLE: lambda chave, cli: cli.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": chave, "pageSize": 1},
    ),
}


def _sonda_ia(provedor: str) -> Callable[[], str | None]:
    def sonda() -> str | None:
        sessao = CriadorDeSessao()
        try:
            chaves, _ = resolver_chaves_por_organizacao(sessao, None)
        finally:
            sessao.close()
        chave = chaves.get(provedor)
        if not chave:
            raise RuntimeError("nenhuma chave resolvível no cofre para este provedor")
        with httpx.Client(timeout=TIMEOUT_SONDA_S) as cli:
            r = _SONDAS_IA[provedor](chave, cli)
            r.raise_for_status()
        return None

    return sonda


def _sonda_telegram(instrumento_id, nome: str) -> Callable[[], str | None]:
    def sonda() -> str | None:
        from mensageria import telegram as tele

        sessao = CriadorDeSessao()
        try:
            token = (
                segredos_instrumento.decifrar(sessao, instrumento_id).get("token_bot")
                or ""
            )
        finally:
            sessao.close()
        if not token:
            raise RuntimeError("canal sem token de bot no cofre")
        with httpx.Client(timeout=TIMEOUT_SONDA_S) as cli:
            me = cli.post(f"{tele.API_BASE}/bot{token}/getMe")
            if me.status_code in (401, 404):
                raise RuntimeError("o Telegram recusou o token do bot (revogado?)")
            me.raise_for_status()
            info = cli.post(f"{tele.API_BASE}/bot{token}/getWebhookInfo")
            info.raise_for_status()
        dados = (info.json() or {}).get("result") or {}
        if not dados.get("url"):
            raise RuntimeError(
                "webhook não registrado — mensagens recebidas NÃO chegam ao Batuta"
            )
        # O Telegram conta os próprios erros ao ENTREGAR pra gente — é o sinal de
        # entrada quebrada sem precisar esperar alguém reclamar.
        erro_em = dados.get("last_error_date")
        if erro_em and (time.time() - erro_em) < 900:
            raise EloDegradado(
                "o Telegram está falhando ao entregar pra gente: "
                f"{dados.get('last_error_message') or 'erro não descrito'}"
            )
        pendentes = int(dados.get("pending_update_count") or 0)
        if pendentes > 20:
            raise EloDegradado(f"{pendentes} mensagens acumuladas sem entrega")
        return "bot ativo e webhook registrado"

    return sonda


def _reconectar_telegram(instrumento_id) -> Callable[[], None]:
    def reconectar() -> None:
        from mensageria import telegram as tele

        sessao = CriadorDeSessao()
        try:
            inst = sessao.get(Instrumento, instrumento_id)
            if inst is None:
                raise RuntimeError("canal não existe mais")
            segredo = getattr(inst, "webhook_secret", None)
            token = (
                segredos_instrumento.decifrar(sessao, instrumento_id).get("token_bot")
                or ""
            )
        finally:
            sessao.close()
        if not (token and segredo):
            raise RuntimeError("canal sem token/segredo — reative o canal pela tela")
        base = os.environ.get("CEREBRO_PUBLIC_URL", "http://localhost:8000").rstrip("/")
        url = f"{base}/mensageria/{instrumento_id}/entrada"
        resultado = tele.configurar_webhook(token, url, segredo)
        if not resultado.get("ok"):
            raise RuntimeError(
                f"o Telegram recusou o registro do webhook: {resultado.get('description')}"
            )

    return reconectar


def _sonda_storage() -> str | None:
    arquivos.sondar()
    return None


def _sonda_meta() -> str | None:
    # Alcançabilidade da Graph API (o token em si é renovado pelo job diário; aqui o
    # que se vigia é a REDE até a Meta). Qualquer resposta HTTP = alcançável.
    with httpx.Client(timeout=TIMEOUT_SONDA_S) as cli:
        cli.get("https://graph.facebook.com/v19.0/")
    return "Graph API alcançável (validade do token é vigiada pelo job diário)"


def _sonda_url(url: str, *, nome: str) -> Callable[[], str | None]:
    def sonda() -> str | None:
        with httpx.Client(timeout=TIMEOUT_SONDA_S, follow_redirects=True) as cli:
            r = cli.get(url)
            if r.status_code >= 500:
                raise RuntimeError(f"{nome} respondeu com erro (HTTP {r.status_code})")
        return None

    return sonda


# ─────────────────────────── registro dos elos ───────────────────────────────


def _na_railway() -> bool:
    return bool(os.environ.get("RAILWAY_GIT_COMMIT_SHA"))


def montar_elos() -> list[Elo]:
    """A lista VIVA de elos: os fixos + os dinâmicos (um por provedor com chave,
    um por canal Telegram). Reconstruída a cada varredura — canal novo entra
    sozinho, canal removido sai sozinho."""
    elos: list[Elo] = [
        Elo(
            "banco", "Banco de dados (pool principal)", "banco", PERIODO_BANCO_S,
            _sonda_banco, _reconectar_banco, auto_cura=True,
        ),
        Elo(
            "memoria_conversa", "Memória de conversa (checkpointer)", "banco",
            PERIODO_BANCO_S, _sonda_memoria, _reconectar_memoria, auto_cura=True,
        ),
        Elo(
            "fila", "Fila de execuções", "interno", PERIODO_INTERNO_S,
            _sonda_fila, _reconectar_fila,
        ),
        Elo(
            "agendador", "Agendador de gatilhos", "interno", PERIODO_INTERNO_S,
            _sonda_agendador, _reconectar_agendador,
        ),
        Elo(
            "vigia_mensageria", "Vigia das conversas", "interno", PERIODO_INTERNO_S,
            _sonda_vigia_mensageria, _reconectar_agendador,
        ),
        # As execuções que PAUSAM (passo "Esperar", passo "Chamar outra automação") e as
        # que travam dependem de um vigia periódico para voltar. Vigia morto = execução
        # parada para sempre, com o resto da página verde.
        Elo(
            "vigia_execucoes", "Vigia das execuções", "interno", PERIODO_INTERNO_S,
            _sonda_vigias_execucao, _reconectar_agendador,
        ),
    ]

    if arquivos.storage_configurado():
        elos.append(
            Elo("storage", "Arquivos (Supabase Storage)", "borda",
                PERIODO_EXTERNO_S, _sonda_storage)
        )

    # Borda pública e MCP: na Railway, sondamos os endereços conhecidos por padrão;
    # fora dela, só se a variável estiver definida (dev local não alarma à toa).
    url_borda = os.environ.get(
        "SAUDE_URL_BORDA", "https://api.batuta.team/saude" if _na_railway() else ""
    ).strip()
    if url_borda:
        elos.append(
            Elo("borda", "Borda pública (api.batuta.team)", "borda",
                PERIODO_EXTERNO_S, _sonda_url(url_borda, nome="a borda"))
        )
    url_mcp = os.environ.get(
        "SAUDE_URL_MCP",
        "https://batuta-production.up.railway.app/mcp" if _na_railway() else "",
    ).strip()
    if url_mcp:
        elos.append(
            Elo("mcp", "Serviço MCP (claude.ai)", "borda",
                PERIODO_EXTERNO_S, _sonda_url(url_mcp, nome="o MCP"))
        )

    # Dinâmicos: dependem do banco — se ele estiver fora, os fixos continuam valendo.
    try:
        sessao = CriadorDeSessao()
        try:
            from chaves import servicos_com_chave

            com_chave = servicos_com_chave(sessao, None)
            for provedor in (PROVEDOR_ANTHROPIC, PROVEDOR_OPENAI, PROVEDOR_GOOGLE):
                if provedor in com_chave:
                    elos.append(
                        Elo(f"ia_{provedor}", f"IA — {provedor.capitalize()}", "ia",
                            PERIODO_EXTERNO_S, _sonda_ia(provedor))
                    )

            canais = sessao.scalars(
                select(Instrumento).where(Instrumento.tipo == "enviar_telegram")
            ).all()
            for canal in canais:
                elos.append(
                    Elo(
                        f"telegram_{canal.id}", f"Telegram — {canal.nome}", "canais",
                        PERIODO_EXTERNO_S, _sonda_telegram(canal.id, canal.nome),
                        _reconectar_telegram(canal.id),
                    )
                )

            tem_instagram = sessao.scalar(
                select(Instrumento.id)
                .where(Instrumento.tipo.ilike("%instagram%"))
                .limit(1)
            )
            if tem_instagram is not None:
                elos.append(
                    Elo("meta", "Meta / Instagram (Graph API)", "canais",
                        PERIODO_META_S, _sonda_meta)
                )
        finally:
            sessao.close()
    except Exception:
        logger.warning("saude_elos: não deu para montar os elos dinâmicos", exc_info=True)

    return elos


# ───────────────────────────── o ciclo de sonda ──────────────────────────────


def _sondar_um(elo: Elo) -> dict:
    inicio = time.monotonic()
    try:
        detalhe = elo.sonda()
        estado, erro = "ok", None
    except EloDegradado as e:
        estado, detalhe, erro = "degradado", None, str(e)
    except Exception as e:  # noqa: BLE001 — toda falha de sonda vira estado, não crash
        estado, detalhe, erro = "caido", None, _traduzir(e)
    return {
        "estado": estado,
        "detalhe": detalhe,
        "erro": erro,
        "latencia_ms": int((time.monotonic() - inicio) * 1000),
        "verificado_em": datetime.now(timezone.utc).isoformat(),
    }


def _aplicar_resultado(elo: Elo, resultado: dict) -> None:
    """Atualiza o estado, registra transições no banco de logs e auto-cura."""
    with _lock:
        anterior = _estado.get(elo.id) or {}
        falhas = anterior.get("falhas_seguidas", 0)
        falhas = falhas + 1 if resultado["estado"] == "caido" else 0
        estado_anterior = anterior.get("estado")
        mudou = estado_anterior is not None and estado_anterior != resultado["estado"]
        desde = (
            anterior.get("desde")
            if estado_anterior == resultado["estado"]
            else resultado["verificado_em"]
        )
        _estado[elo.id] = {
            **resultado,
            "nome": elo.nome,
            "grupo": elo.grupo,
            "reconectavel": elo.reconectar is not None,
            "auto_cura": elo.auto_cura,
            "falhas_seguidas": falhas,
            "desde": desde,
        }

    if mudou:
        caiu = resultado["estado"] != "ok"
        registrar_evento(
            categoria="sistema",
            acao="elo.caiu" if caiu else "elo.voltou",
            nivel="error" if resultado["estado"] == "caido"
            else ("warning" if caiu else "info"),
            resultado="falha" if caiu else "sucesso",
            persistir=True,
            detalhe={
                "elo": elo.id, "nome": elo.nome, "de": estado_anterior,
                "para": resultado["estado"], "erro": resultado.get("erro"),
            },
        )

    # Auto-cura: falhas seguidas nos elos marcados → reconecta sozinho e re-sonda.
    if (
        elo.auto_cura
        and elo.reconectar is not None
        and resultado["estado"] == "caido"
        and falhas >= FALHAS_PARA_AUTOCURA
    ):
        try:
            elo.reconectar()
            novo = _sondar_um(elo)
            ok = novo["estado"] == "ok"
            registrar_evento(
                categoria="sistema", acao="elo.reconectado",
                nivel="info" if ok else "error",
                resultado="sucesso" if ok else "falha", persistir=True,
                detalhe={"elo": elo.id, "nome": elo.nome, "automatico": True,
                         "curado": ok, "erro": novo.get("erro")},
            )
            if ok:
                _aplicar_resultado(elo, novo)
        except Exception as e:  # noqa: BLE001
            registrar_evento(
                categoria="sistema", acao="elo.reconectado", nivel="error",
                resultado="falha", persistir=True,
                detalhe={"elo": elo.id, "nome": elo.nome, "automatico": True,
                         "curado": False, "erro": _traduzir(e)},
            )


def sondar_job() -> None:
    """Entrada do agendador (a cada 15 s): sonda os elos cujo período venceu."""
    agora = time.monotonic()
    for elo in montar_elos():
        if _proxima.get(elo.id, 0) > agora:
            continue
        _proxima[elo.id] = agora + elo.periodo_s
        _aplicar_resultado(elo, _sondar_um(elo))


# ─────────────────────────────── leitura/ação ────────────────────────────────


def foto() -> dict:
    """A foto completa para `GET /saude/elos` (lê o cache; não dispara sonda)."""
    with _lock:
        elos = [{"id": eid, **dados} for eid, dados in sorted(_estado.items())]
    caidos = [e["id"] for e in elos if e["estado"] == "caido"]
    degradados = [e["id"] for e in elos if e["estado"] == "degradado"]
    return {
        "agora": datetime.now(timezone.utc).isoformat(),
        "elos": elos,
        "caidos": caidos,
        "degradados": degradados,
        "saudavel": not caidos and not degradados,
    }


def resumo() -> dict:
    """Resumo barato para o `GET /saude` (o selo da sidebar)."""
    with _lock:
        caidos = sorted(e for e, d in _estado.items() if d["estado"] == "caido")
        degradados = sorted(e for e, d in _estado.items() if d["estado"] == "degradado")
    return {"elos_caidos": caidos, "elos_degradados": degradados}


def reconectar_elo(elo_id: str) -> dict:
    """Reconexão por botão: executa a cura do elo e re-sonda na hora. Levanta
    `KeyError` para elo desconhecido e `ValueError` para elo sem reconexão."""
    alvo = next((e for e in montar_elos() if e.id == elo_id), None)
    if alvo is None:
        raise KeyError(elo_id)
    if alvo.reconectar is None:
        raise ValueError("este elo não tem reconexão — só re-sonda")
    erro_cura: str | None = None
    try:
        alvo.reconectar()
    except Exception as e:  # noqa: BLE001 — a re-sonda abaixo conta a verdade
        erro_cura = _traduzir(e)
    novo = _sondar_um(alvo)
    _aplicar_resultado(alvo, novo)
    registrar_evento(
        categoria="sistema", acao="elo.reconectado",
        nivel="info" if novo["estado"] == "ok" else "error",
        resultado="sucesso" if novo["estado"] == "ok" else "falha", persistir=True,
        detalhe={"elo": elo_id, "nome": alvo.nome, "automatico": False,
                 "curado": novo["estado"] == "ok",
                 "erro": erro_cura or novo.get("erro")},
    )
    with _lock:
        return {"id": elo_id, **_estado[elo_id]}
