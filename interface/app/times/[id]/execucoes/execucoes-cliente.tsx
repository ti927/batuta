"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Activity,
  CalendarClock,
  ChevronRight,
  Clock,
  MessageCircle,
  X,
} from "lucide-react";
import { toast } from "sonner";

import {
  api,
  mensagemDeErro,
  type AgendamentoDoTime,
  type ExecucaoNaLista,
  type PapelAcesso,
  type Time,
  type TimeResumo,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { ESTADO, formatarData } from "@/components/inspecao-execucao";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";

// Horário sempre em Brasília (os prazos são pensados no Brasil).
const FMT_BRT = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo",
  dateStyle: "short",
  timeStyle: "short",
});

const FILTROS: { valor: string; rotulo: string; casa: (e: string) => boolean }[] = [
  { valor: "todas", rotulo: "Todas", casa: () => true },
  { valor: "concluida", rotulo: "Concluídas", casa: (e) => e === "concluida" },
  {
    valor: "aguardando_humano",
    rotulo: "Aguardando você",
    casa: (e) => e === "aguardando_humano",
  },
  {
    valor: "aguardando_tempo",
    rotulo: "Esperando o tempo",
    casa: (e) => e === "aguardando_tempo",
  },
  { valor: "falhou", rotulo: "Falhou", casa: (e) => e === "falhou" },
];

function duracaoExec(e: ExecucaoNaLista): string | null {
  if (!e.iniciada_em || !e.finalizada_em) return null;
  const ms = new Date(e.finalizada_em).getTime() - new Date(e.iniciada_em).getTime();
  if (Number.isNaN(ms) || ms < 0) return null;
  const seg = Math.round(ms / 1000);
  if (seg < 60) return `${seg}s`;
  const min = Math.floor(seg / 60);
  return `${min}min ${String(seg % 60).padStart(2, "0")}s`;
}

function CartaoMetrica({
  rotulo,
  valor,
  sub,
}: {
  rotulo: string;
  valor: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="text-xs text-muted-foreground">{rotulo}</div>
      <div className="mt-1 font-heading text-2xl font-medium leading-tight text-foreground">
        {valor}
      </div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export function ExecucoesCliente({
  time,
  inicial,
  resumo,
  meuPapel,
}: {
  time: Time;
  inicial: ExecucaoNaLista[];
  resumo: TimeResumo | null;
  meuPapel: PapelAcesso | null;
}) {
  const souOperador = podeOperar(meuPapel);
  const [filtro, setFiltro] = useState("todas");
  // Agendamentos do time (aba "Agendadas") — outra tabela, buscada no cliente (dinâmica).
  const [agendamentos, setAgendamentos] = useState<AgendamentoDoTime[]>([]);
  useEffect(() => {
    let vivo = true;
    api
      .get<AgendamentoDoTime[]>(`/times/${time.id}/agendamentos`)
      .then((d) => vivo && setAgendamentos(d))
      .catch(() => {
        /* seção complementar: silencia se falhar (a aba fica vazia) */
      });
    return () => {
      vivo = false;
    };
  }, [time.id]);
  const pendentes = agendamentos.filter((a) => a.estado === "pendente");
  const cancelados = agendamentos.filter((a) => a.estado === "cancelado");

  // Rastro-sombra das conversas do time (filtro "Conversas") — outra origem (execuções
  // modo='conversa'), buscada no cliente, igual às Agendadas. Não entra nos stat cards
  // nem nos filtros de estado (que são das automações), para não os poluir.
  const [conversas, setConversas] = useState<ExecucaoNaLista[]>([]);
  useEffect(() => {
    let vivo = true;
    api
      .get<ExecucaoNaLista[]>(`/times/${time.id}/conversas-rastro`)
      .then((d) => vivo && setConversas(d))
      .catch(() => {
        /* filtro complementar: silencia se falhar (a aba fica vazia) */
      });
    return () => {
      vivo = false;
    };
  }, [time.id]);

  async function cancelarAgendamento(id: string) {
    try {
      await api.delete(`/agendamentos/${id}`);
      setAgendamentos((l) =>
        l.map((a) =>
          a.id === id
            ? { ...a, estado: "cancelado", motivo: "Cancelado por você." }
            : a,
        ),
      );
      toast.success("Agendamento cancelado.");
    } catch (e) {
      toast.error(mensagemDeErro(e, "Não consegui cancelar o agendamento."));
    }
  }

  // "agendadas" não é um estado de execução — não está em FILTROS.
  const filtroExec = FILTROS.find((f) => f.valor === filtro);
  const lista = filtroExec ? inicial.filter((e) => filtroExec.casa(e.estado)) : [];

  // Agregados dos 4 stat cards.
  const total = inicial.length;
  const concluidas = inicial.filter((e) => e.estado === "concluida").length;
  const falhas = inicial.filter((e) => e.estado === "falhou").length;
  const finalizadas = concluidas + falhas;
  const taxa = finalizadas > 0 ? Math.round((100 * concluidas) / finalizadas) : null;
  const duracoes = inicial.map(duracaoExec).filter(Boolean).length;
  const segs = inicial
    .map((e) =>
      e.iniciada_em && e.finalizada_em
        ? (new Date(e.finalizada_em).getTime() - new Date(e.iniciada_em).getTime()) /
          1000
        : null,
    )
    .filter((s): s is number => s !== null && s >= 0);
  const mediaSeg = segs.length ? Math.round(segs.reduce((a, b) => a + b, 0) / segs.length) : null;
  const duracaoMedia =
    mediaSeg === null
      ? "—"
      : mediaSeg < 60
        ? `${mediaSeg}s`
        : `${Math.floor(mediaSeg / 60)}min ${String(mediaSeg % 60).padStart(2, "0")}s`;

  return (
    <main className="mx-auto w-full max-w-[1000px] px-5 py-8 sm:px-8">
      <div className="mb-6">
        <h2 className="text-sm font-medium text-foreground">Execuções</h2>
        <p className="text-sm text-muted-foreground">
          Todo disparo das automações do time. Abra uma para ver o passo a passo.
        </p>
      </div>

      {total > 0 && (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <CartaoMetrica rotulo="Total" valor={String(total)} sub="execuções" />
          <CartaoMetrica
            rotulo="Taxa de sucesso"
            valor={taxa === null ? "—" : `${taxa}%`}
            sub={`${concluidas} de ${finalizadas} concluídas`}
          />
          <CartaoMetrica
            rotulo="Duração média"
            valor={duracaoMedia}
            sub={duracoes > 0 ? "por execução" : "sem dados"}
          />
          <CartaoMetrica
            rotulo="Custo total"
            valor={`~US$ ${(resumo?.custo_acumulado_usd ?? 0).toFixed(2)}`}
            sub="estimado"
          />
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        {FILTROS.map((f) => {
          const n = inicial.filter((e) => f.casa(e.estado)).length;
          const ativo = filtro === f.valor;
          return (
            <button
              key={f.valor}
              onClick={() => setFiltro(f.valor)}
              className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                ativo
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card text-muted-foreground hover:text-foreground"
              }`}
            >
              {f.rotulo} ({n})
            </button>
          );
        })}
        {/* "Agendadas": disparos FUTUROS (outra tabela). Completa o ciclo de vida —
            agendada → aguardando → em andamento → concluída/cancelada. */}
        <button
          onClick={() => setFiltro("agendadas")}
          className={`rounded-full border px-3 py-1 text-sm transition-colors ${
            filtro === "agendadas"
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-card text-muted-foreground hover:text-foreground"
          }`}
        >
          Agendadas ({pendentes.length})
        </button>
        {/* "Conversas": o rastro dos atendimentos por canal (execuções modo='conversa').
            O passo a passo abre na MESMA tela de detalhe das execuções. */}
        <button
          onClick={() => setFiltro("conversas")}
          className={`rounded-full border px-3 py-1 text-sm transition-colors ${
            filtro === "conversas"
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-card text-muted-foreground hover:text-foreground"
          }`}
        >
          Conversas ({conversas.length})
        </button>
      </div>

      {filtro === "agendadas" ? (
        <Agendadas
          pendentes={pendentes}
          cancelados={cancelados}
          souOperador={souOperador}
          onCancelar={cancelarAgendamento}
        />
      ) : filtro === "conversas" ? (
        <Conversas conversas={conversas} timeId={time.id} />
      ) : lista.length === 0 ? (
        <EstadoVazio icone={Activity} titulo="Nenhuma execução neste filtro.">
          Quando o time rodar, as execuções aparecem aqui.
        </EstadoVazio>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          {lista.map((e, i) => {
            const dur = duracaoExec(e);
            return (
              <Link
                key={e.id}
                href={`/times/${time.id}/execucoes/${e.id}`}
                className={`flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent/50 ${
                  i > 0 ? "border-t border-border" : ""
                }`}
              >
                <Badge variant={ESTADO[e.estado]?.variante ?? "neutral"}>
                  {ESTADO[e.estado]?.label ?? e.estado}
                </Badge>
                <span className="hidden font-mono text-xs text-muted-foreground sm:block">
                  #{e.id.slice(0, 6)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-foreground">
                    {e.entrada?.texto || e.automacao_nome}
                  </span>
                </span>
                {dur && (
                  <span className="hidden whitespace-nowrap text-xs text-muted-foreground sm:block">
                    {dur}
                  </span>
                )}
                <span className="hidden whitespace-nowrap text-xs text-muted-foreground md:block">
                  {formatarData(e.criado_em)}
                </span>
                <ChevronRight className="size-4 shrink-0 text-muted-foreground/60" />
              </Link>
            );
          })}
        </div>
      )}
    </main>
  );
}

// Aba "Agendadas": os próximos disparos (pendentes, "no ar") + os que NÃO dispararam
// (cancelados, com o MOTIVO — §12-A: nada em silêncio). Um agendamento ainda não é uma
// execução (não há passo a passo), então a linha é só informativa + Cancelar.
function Agendadas({
  pendentes,
  cancelados,
  souOperador,
  onCancelar,
}: {
  pendentes: AgendamentoDoTime[];
  cancelados: AgendamentoDoTime[];
  souOperador: boolean;
  onCancelar: (id: string) => void;
}) {
  if (pendentes.length === 0 && cancelados.length === 0) {
    return (
      <EstadoVazio icone={CalendarClock} titulo="Nenhum disparo agendado.">
        Quando um agente agendar uma automação (instrumento “Agendar automação”), o
        próximo disparo aparece aqui.
      </EstadoVazio>
    );
  }
  const cancDesc = [...cancelados].sort(
    (a, b) =>
      new Date(b.quando_executar).getTime() - new Date(a.quando_executar).getTime(),
  );
  return (
    <div className="space-y-6">
      {pendentes.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          {pendentes.map((a, i) => (
            <div
              key={a.id}
              className={`flex items-center gap-3 px-4 py-3 ${
                i > 0 ? "border-t border-border" : ""
              }`}
            >
              <Badge variant="info" className="gap-1">
                <Clock className="size-3" /> agendada
              </Badge>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-foreground">
                  {a.automacao_nome}
                </span>
                <span className="text-xs text-muted-foreground">
                  dispara {FMT_BRT.format(new Date(a.quando_executar))}
                </span>
              </span>
              {souOperador && (
                <Button size="sm" variant="ghost" onClick={() => onCancelar(a.id)}>
                  <X className="size-4" /> Cancelar
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {cancDesc.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Não dispararam (últimos 7 dias)
          </p>
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            {cancDesc.map((a, i) => (
              <div
                key={a.id}
                className={`flex items-start gap-3 px-4 py-3 ${
                  i > 0 ? "border-t border-border" : ""
                }`}
              >
                <Badge variant="warning">cancelada</Badge>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-foreground">
                    {a.automacao_nome}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    era para {FMT_BRT.format(new Date(a.quando_executar))}
                  </span>
                  {a.motivo && (
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {a.motivo}
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Filtro "Conversas": o rastro-sombra dos atendimentos por canal (execuções
// modo='conversa'). Cada linha abre o MESMO detalhe das execuções (o passo a passo
// dos turnos do agente). Identificada pelo contato + canal, não por automação.
function Conversas({
  conversas,
  timeId,
}: {
  conversas: ExecucaoNaLista[];
  timeId: string;
}) {
  if (conversas.length === 0) {
    return (
      <EstadoVazio icone={MessageCircle} titulo="Nenhuma conversa ainda.">
        Quando um agente atender alguém por um canal (ex.: Telegram), o rastro do
        atendimento aparece aqui — com o passo a passo de cada resposta.
      </EstadoVazio>
    );
  }
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      {conversas.map((c, i) => (
        <Link
          key={c.id}
          href={`/times/${timeId}/execucoes/${c.id}`}
          className={`flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent/50 ${
            i > 0 ? "border-t border-border" : ""
          }`}
        >
          <Badge variant="info" className="gap-1">
            <MessageCircle className="size-3" /> conversa
          </Badge>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm text-foreground">
              {c.automacao_nome}
            </span>
          </span>
          <span className="hidden whitespace-nowrap text-xs text-muted-foreground md:block">
            {formatarData(c.criado_em)}
          </span>
          <ChevronRight className="size-4 shrink-0 text-muted-foreground/60" />
        </Link>
      ))}
    </div>
  );
}
