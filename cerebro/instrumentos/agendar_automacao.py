"""Instrumento "Agendar automação" — disparo FUTURO de uma automação por um agente.

Ao fim de um fluxo e conforme o resultado, um agente pode AGENDAR um disparo futuro
de uma automação: a MESMA (reprogramar-se, ex.: "+10 dias") ou a de OUTRO time da
organização (departamentos interdependentes). O ALVO (qual automação) é fixado na
CONFIG pelo HUMANO (escolhido num seletor das automações da organização); o agente
decide só o SE e o QUANDO. Isso mantém o escopo seguro e o agente sem poder de
apontar para a automação errada.

Grava uma linha na tabela `agendamentos` (estado `pendente`); um sweeper periódico
(agendador) pega os vencidos e cria a execução pelo motor. Como o instrumento não
recebe sessão/contexto da execução, ele abre a PRÓPRIA sessão (como fazem os jobs do
agendador) só para inserir o agendamento e conferir o teto. Reversível: dá para
cancelar o agendamento pela tela (por isso `acao_irreversivel=False`, como o webhook).
"""

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import func, select

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar
from modelos import Agendamento, Automacao
from sessao import CriadorDeSessao

# Fuso de Brasília (os prazos são pensados no Brasil). Absoluto sem fuso = BRT.
FUSO = ZoneInfo("America/Sao_Paulo")
MIN_ATRASO_S = 60  # piso: nada mais cedo que ~1 min (evita loop instantâneo)
TETO_PENDENTES = 50  # anti-loop: máximo de agendamentos pendentes por automação-alvo


class ConfigAgendar(BaseModel):
    """Configuração fixa (o humano preenche): QUAL automação será agendada."""

    automacao_alvo_id: str = Field(
        default="",
        title="Automação a agendar",
        description="A automação (deste ou de outro time da organização) que será disparada.",
        json_schema_extra={"ui": "automacao_alvo"},
    )


class ArgsAgendar(BaseModel):
    """O que a IA passa: daqui a quanto tempo (ou uma data) disparar, e a entrada."""

    dias: int = Field(default=0, ge=0, description="Daqui a quantos DIAS disparar.")
    horas: int = Field(default=0, ge=0, description="Daqui a quantas HORAS disparar.")
    minutos: int = Field(default=0, ge=0, description="Daqui a quantos MINUTOS disparar.")
    data_hora: str = Field(
        default="",
        description="Alternativa: data/hora exata (ISO 8601, ex.: '2026-08-01T09:00'). "
        "Se preenchida, ignora dias/horas/minutos (sem fuso = horário de Brasília).",
    )
    entrada: str = Field(
        default="", description="Texto de entrada (payload) para a execução agendada."
    )


def _quando(args: ArgsAgendar) -> datetime | None:
    """O instante do disparo (UTC-aware). None se não der para determinar."""
    dh = (args.data_hora or "").strip()
    if dh:
        try:
            q = datetime.fromisoformat(dh)
        except ValueError:
            return None
        if q.tzinfo is None:
            q = q.replace(tzinfo=FUSO)
        return q.astimezone(timezone.utc)
    total = timedelta(days=args.dias, hours=args.horas, minutes=args.minutos)
    if total.total_seconds() <= 0:
        return None
    return datetime.now(timezone.utc) + total


class AgendarAutomacao(TipoInstrumento):
    tipo = "agendar_automacao"
    categoria = "Integrações e dados"
    nome_exibicao = "Agendar automação"
    descricao = (
        "Agenda um disparo FUTURO de uma automação (a mesma ou a de outro time da "
        "organização — o alvo é fixado na configuração do instrumento pelo humano). Use "
        "ao fim de um fluxo para reprogramar um próximo passo: informe daqui a quanto "
        "tempo disparar (dias/horas/minutos) ou uma data/hora. A execução acontece na "
        "hora marcada; dá para ver e cancelar os agendamentos na tela da automação."
    )
    Config = ConfigAgendar
    Args = ArgsAgendar

    def executar(self, config: ConfigAgendar, args: ArgsAgendar) -> dict:
        try:
            alvo_id = uuid.UUID(str(config.automacao_alvo_id))
        except (ValueError, TypeError):
            raise FalhaInstrumento(
                "este instrumento não tem uma automação-alvo configurada — escolha, na "
                "configuração do instrumento, qual automação será agendada.",
                retentavel=False,
            )
        quando = _quando(args)
        if quando is None:
            raise FalhaInstrumento(
                "informe daqui a quanto tempo disparar (dias, horas ou minutos > 0) ou "
                "uma data/hora válida.",
                retentavel=False,
            )
        if quando < datetime.now(timezone.utc) + timedelta(seconds=MIN_ATRASO_S):
            raise FalhaInstrumento(
                "o horário do agendamento precisa estar no futuro (mínimo ~1 minuto).",
                retentavel=False,
            )
        sessao = CriadorDeSessao()
        try:
            alvo = sessao.get(Automacao, alvo_id)
            if alvo is None:
                raise FalhaInstrumento(
                    "a automação-alvo do agendamento não existe mais — reconfigure o "
                    "instrumento.",
                    retentavel=False,
                )
            pendentes = (
                sessao.scalar(
                    select(func.count())
                    .select_from(Agendamento)
                    .where(
                        Agendamento.automacao_id == alvo_id,
                        Agendamento.estado == "pendente",
                    )
                )
                or 0
            )
            if pendentes >= TETO_PENDENTES:
                raise FalhaInstrumento(
                    f"já há {pendentes} agendamentos pendentes para essa automação "
                    f"(teto {TETO_PENDENTES}) — cancele alguns antes de agendar mais.",
                    retentavel=False,
                )
            ag = Agendamento(
                automacao_id=alvo_id,
                quando_executar=quando,
                entrada=(args.entrada or None),
                estado="pendente",
            )
            sessao.add(ag)
            sessao.commit()
            ag_id = str(ag.id)
        finally:
            sessao.close()
        return {
            "ok": True,
            "agendamento_id": ag_id,
            "automacao_id": str(alvo_id),
            "quando_executar": quando.isoformat(),
        }


registrar(AgendarAutomacao())
