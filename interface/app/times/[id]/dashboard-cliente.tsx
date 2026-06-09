"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Activity,
  Bot,
  ChevronRight,
  Clock,
  Gauge,
  GitBranch,
  MessageSquare,
  Settings2,
  Sparkles,
  Users,
  Wrench,
  X,
  Zap,
} from "lucide-react";

import { RobotFace } from "@/components/robot-face";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { podeOperar } from "@/lib/permissoes";
import {
  type Agente,
  type Automacao,
  type Cadeia,
  type Execucao,
  type Instrumento,
  type PapelAcesso,
  type ResumoUso,
  type Time,
} from "@/lib/api";

export type ExecucaoRecente = Execucao & { automacao_nome: string };

// ── Estados de execução: rótulo amigável + variante de cor (igual à tela de
// execuções, mas com rótulos em português para o hub do time). ──
type VarianteBadge = "neutral" | "info" | "success" | "warning" | "error";
const ESTADO: Record<string, { label: string; variante: VarianteBadge }> = {
  aguardando: { label: "na fila", variante: "neutral" },
  em_andamento: { label: "em andamento", variante: "warning" },
  aguardando_humano: { label: "aguardando você", variante: "info" },
  concluida: { label: "concluída", variante: "success" },
  falhou: { label: "falhou", variante: "error" },
  cancelada: { label: "cancelada", variante: "neutral" },
};

const ROTULO_GATILHO: Record<string, string> = {
  manual: "Manual",
  agendamento: "Por horário",
  webhook: "Por webhook",
};

function formatarData(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

export function DashboardCliente({
  time,
  meuPapel,
  agentes,
  cintos,
  automacoes,
  recentes,
  aguardando,
  pendenteAutomacaoId,
  totalExecucoes,
  custo,
  conversaId,
}: {
  time: Time;
  meuPapel: PapelAcesso | null;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  automacoes: Automacao[];
  recentes: ExecucaoRecente[];
  aguardando: number;
  pendenteAutomacaoId: string | null;
  totalExecucoes: number;
  custo: ResumoUso | null;
  conversaId: string | null;
}) {
  const [agenteAberto, setAgenteAberto] = useState<Agente | null>(null);
  const souOperador = podeOperar(meuPapel);

  const ativo = automacoes.some((a) => a.ativa);
  const gatilhoLabel =
    automacoes.length === 0
      ? "Sem automação"
      : automacoes.length === 1
        ? (ROTULO_GATILHO[automacoes[0].tipo_gatilho] ?? automacoes[0].tipo_gatilho)
        : `${automacoes.length} automações`;

  return (
    <main className="mx-auto w-full max-w-[1000px] px-5 py-8 sm:px-8">
      {/* Cabeçalho */}
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-60 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-heading text-[27px] font-medium leading-tight text-foreground">
              {time.nome}
            </h1>
            <Badge variant={ativo ? "success" : "neutral"}>
              {ativo ? "ativo" : "em repouso"}
            </Badge>
          </div>
          {time.descricao && (
            <p className="mt-1.5 text-sm text-muted-foreground">{time.descricao}</p>
          )}
        </div>
        {souOperador && (
          <Link
            href={conversaId ? `/criar/${conversaId}` : "/criar"}
            className={buttonVariants({ variant: "outline" })}
          >
            <Sparkles className="size-4 text-primary" />
            Conversar sobre o projeto
          </Link>
        )}
      </div>

      {/* Atalhos de gestão */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm">
        <Link
          href={`/times/${time.id}/agentes`}
          className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
        >
          <Users className="size-3.5" /> Gerenciar agentes
        </Link>
        <Link
          href={`/times/${time.id}/instrumentos`}
          className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
        >
          <Settings2 className="size-3.5" /> Instrumentos
        </Link>
        <Link
          href={`/times/${time.id}/automacoes`}
          className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
        >
          <Zap className="size-3.5" /> Automações
        </Link>
      </div>

      {/* Stat cards */}
      <div className="mt-6 flex flex-wrap gap-3.5">
        <StatCard
          Icone={Clock}
          tom={{ bg: "#EFEAFF", fg: "#6D4AFF" }}
          rotulo="Gatilho"
          valor={gatilhoLabel}
          sub={ativo ? "disparando normalmente" : "ainda não ativado"}
        />
        <StatCard
          Icone={MessageSquare}
          tom={{ bg: "#FDF1E3", fg: "#E89638" }}
          rotulo="Aguardando você"
          valor={
            aguardando > 0
              ? `${aguardando} ${aguardando === 1 ? "pendência" : "pendências"}`
              : "Nada pendente"
          }
          sub={aguardando > 0 ? "um fluxo espera seu ok →" : "nenhum fluxo parado"}
          acento={aguardando > 0}
          href={
            aguardando > 0 && pendenteAutomacaoId
              ? `/automacoes/${pendenteAutomacaoId}`
              : undefined
          }
        />
        <StatCard
          Icone={Gauge}
          tom={{ bg: "#E6F4EA", fg: "#3DAA5C" }}
          rotulo="Custo acumulado"
          valor={custo ? `~US$ ${custo.custo_usd.toFixed(2)}` : "US$ 0,00"}
          sub={`${totalExecucoes} ${totalExecucoes === 1 ? "execução" : "execuções"} · estimado`}
        />
      </div>

      {/* Cadeia */}
      {automacoes.some((a) => a.cadeia?.inicio) && (
        <>
          <RotuloSecao Icone={GitBranch}>Cadeia · o caminho da tarefa</RotuloSecao>
          <div className="space-y-4">
            {automacoes
              .filter((a) => a.cadeia?.inicio)
              .map((a) => (
                <div
                  key={a.id}
                  className="rounded-xl border border-border bg-card p-4"
                >
                  {automacoes.length > 1 && (
                    <p className="mb-3 text-xs font-medium text-muted-foreground">
                      {a.nome}
                    </p>
                  )}
                  <CadeiaHorizontal cadeia={a.cadeia!} agentes={agentes} />
                </div>
              ))}
          </div>
        </>
      )}

      {/* Execuções recentes */}
      <RotuloSecao Icone={Activity}>Execuções recentes</RotuloSecao>
      {recentes.length === 0 ? (
        <EstadoVazio icone={Activity} titulo="Nenhuma execução ainda.">
          Quando este time rodar, as execuções aparecem aqui.
        </EstadoVazio>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          {recentes.map((e, i) => {
            const est = ESTADO[e.estado] ?? ESTADO.aguardando;
            return (
              <Link
                key={e.id}
                href={`/automacoes/${e.automacao_id}`}
                className={`flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent/50 ${
                  i > 0 ? "border-t border-border" : ""
                }`}
              >
                <Badge variant={est.variante}>{est.label}</Badge>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-foreground">
                    {e.automacao_nome}
                  </span>
                  {e.entrada?.texto && (
                    <span className="block truncate text-xs text-muted-foreground">
                      {e.entrada.texto}
                    </span>
                  )}
                </span>
                <span className="hidden whitespace-nowrap text-xs text-muted-foreground sm:block">
                  {formatarData(e.criado_em)}
                </span>
                <ChevronRight className="size-4 shrink-0 text-muted-foreground/60" />
              </Link>
            );
          })}
        </div>
      )}

      {/* Agentes */}
      <RotuloSecao Icone={Bot} contagem={agentes.length}>
        Agentes
      </RotuloSecao>
      {agentes.length === 0 ? (
        <EstadoVazio icone={Bot} titulo="Nenhum agente ainda.">
          {souOperador
            ? "Converse com a IA ou gerencie os agentes para montar o time."
            : "Os agentes deste time aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <div className="grid gap-2.5 sm:grid-cols-2">
          {agentes.map((a, i) => (
            <CardAgente
              key={a.id}
              agente={a}
              indice={i}
              cinto={cintos[a.id] ?? []}
              onAbrir={() => setAgenteAberto(a)}
            />
          ))}
        </div>
      )}

      {agenteAberto && (
        <DrawerAgente
          agente={agenteAberto}
          indice={agentes.indexOf(agenteAberto)}
          cinto={cintos[agenteAberto.id] ?? []}
          onFechar={() => setAgenteAberto(null)}
        />
      )}
    </main>
  );
}

// ───────────────────────── Stat card ─────────────────────────

function StatCard({
  Icone,
  tom,
  rotulo,
  valor,
  sub,
  acento,
  href,
}: {
  Icone: typeof Clock;
  tom: { bg: string; fg: string };
  rotulo: string;
  valor: string;
  sub: string;
  acento?: boolean;
  href?: string;
}) {
  const corpo = (
    <>
      <div className="mb-3 flex items-center gap-2.5">
        <span
          className="flex size-8 items-center justify-center rounded-lg"
          style={{ background: tom.bg }}
        >
          <Icone className="size-4.5" style={{ color: tom.fg }} />
        </span>
        <span className="text-[13px] text-muted-foreground">{rotulo}</span>
        {href && (
          <ChevronRight className="ml-auto size-4 text-muted-foreground/60" />
        )}
      </div>
      <div className="font-heading text-2xl font-medium leading-tight text-foreground">
        {valor}
      </div>
      <div
        className="mt-1 text-xs"
        style={{ color: acento ? "#E89638" : undefined }}
      >
        <span className={acento ? "" : "text-muted-foreground"}>{sub}</span>
      </div>
    </>
  );

  const classeBase = `min-w-52 flex-1 rounded-xl border bg-card p-4 ${
    acento ? "border-[#F0D9B8]" : "border-border"
  }`;

  if (href) {
    return (
      <Link
        href={href}
        className={`${classeBase} transition-all hover:-translate-y-px hover:border-[#D6D3E8]`}
      >
        {corpo}
      </Link>
    );
  }
  return <div className={classeBase}>{corpo}</div>;
}

// ───────────────────────── Cadeia horizontal ─────────────────────────

function ChipCadeia({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 whitespace-nowrap rounded-lg border border-border bg-background px-2.5 py-2">
      {children}
    </div>
  );
}

function CadeiaHorizontal({
  cadeia,
  agentes,
}: {
  cadeia: Cadeia;
  agentes: Agente[];
}) {
  // Segue a primeira saída de cada nó, do início ao fim/repetição (visão linear
  // do caminho principal; bifurcações completas vivem na tela de automação).
  const ordem: string[] = [];
  let atual = cadeia.inicio ?? null;
  const visto = new Set<string>();
  while (atual && cadeia.nos?.[atual] && !visto.has(atual)) {
    ordem.push(atual);
    visto.add(atual);
    atual = cadeia.nos[atual].saidas?.[0]?.destino ?? null;
  }

  const Chip = ChipCadeia;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Chip>
        <span className="flex size-6 items-center justify-center rounded-md bg-[#EFEAFF]">
          <Clock className="size-3.5 text-primary" />
        </span>
        <span className="text-[13px] font-medium text-foreground">Gatilho</span>
      </Chip>
      <ChevronRight className="size-4 text-[#C9C3E0]" />
      {ordem.map((id, i) => {
        const idx = agentes.findIndex((a) => a.id === id);
        const ag = agentes[idx];
        const pausa = cadeia.nos?.[id]?.pausa_humano;
        return (
          <div key={id} className="flex items-center gap-2">
            <Chip>
              <RobotFace size={24} indice={idx} lider={ag?.papel === "lider"} />
              <span className="text-[13px] font-medium text-foreground">
                {ag?.nome ?? "—"}
              </span>
            </Chip>
            {pausa && (
              <>
                <ChevronRight className="size-4 text-[#C9C3E0]" />
                <Chip>
                  <span className="flex size-6 items-center justify-center rounded-md bg-[#FDF1E3]">
                    <MessageSquare className="size-3.5 text-[#E89638]" />
                  </span>
                  <span className="text-[13px] font-medium text-[#E89638]">
                    Aprovação
                  </span>
                </Chip>
              </>
            )}
            {i < ordem.length - 1 && (
              <ChevronRight className="size-4 text-[#C9C3E0]" />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ───────────────────────── Card de agente ─────────────────────────

function CardAgente({
  agente,
  indice,
  cinto,
  onAbrir,
}: {
  agente: Agente;
  indice: number;
  cinto: Instrumento[];
  onAbrir: () => void;
}) {
  return (
    <button
      onClick={onAbrir}
      className="flex w-full items-start gap-3 rounded-xl border border-border bg-card p-3.5 text-left transition-all hover:border-[#D6D3E8] hover:shadow-sm"
    >
      <RobotFace size={40} indice={indice} lider={agente.papel === "lider"} />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="font-medium text-foreground">{agente.nome}</span>
          {agente.papel === "lider" && (
            <Badge variant="neutral" className="text-[10px]">
              líder
            </Badge>
          )}
        </span>
        {agente.agent_md && (
          <span className="mt-0.5 line-clamp-2 block text-sm text-muted-foreground">
            {agente.agent_md}
          </span>
        )}
        <span className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {agente.modelo_ia && (
            <span className="inline-flex items-center gap-1">
              <Sparkles className="size-3 text-primary" />
              {agente.modelo_ia}
            </span>
          )}
          {cinto.map((i) => (
            <span
              key={i.id}
              className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-accent-foreground"
            >
              <Wrench className="size-3" />
              {i.nome}
            </span>
          ))}
        </span>
      </span>
    </button>
  );
}

// ───────────────────────── Drawer do agente ─────────────────────────

const MARKDOWNS: { campo: keyof Agente; rotulo: string; arquivo: string }[] = [
  { campo: "agent_md", rotulo: "Quem é", arquivo: "agent.md" },
  { campo: "skill_md", rotulo: "Habilidades", arquivo: "skill.md" },
  { campo: "tools_md", rotulo: "Cinto de instrumentos", arquivo: "tools.md" },
  { campo: "soul_md", rotulo: "Personalidade", arquivo: "soul.md" },
];

function DrawerAgente({
  agente,
  indice,
  cinto,
  onFechar,
}: {
  agente: Agente;
  indice: number;
  cinto: Instrumento[];
  onFechar: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        className="absolute inset-0 bg-foreground/20"
        onClick={onFechar}
        aria-label="Fechar"
      />
      <aside className="relative flex h-full w-full max-w-[460px] flex-col overflow-y-auto border-l border-border bg-card shadow-xl">
        <header className="flex items-start gap-3 border-b border-border p-4">
          <RobotFace size={44} indice={indice} lider={agente.papel === "lider"} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="font-medium text-foreground">{agente.nome}</h2>
              {agente.papel === "lider" && (
                <Badge variant="neutral" className="text-[10px]">
                  líder
                </Badge>
              )}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
              {agente.modelo_ia && (
                <span className="inline-flex items-center gap-1">
                  <Sparkles className="size-3 text-primary" />
                  {agente.modelo_ia}
                </span>
              )}
              {cinto.map((i) => (
                <span
                  key={i.id}
                  className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-accent-foreground"
                >
                  <Wrench className="size-3" />
                  {i.nome}
                </span>
              ))}
            </div>
          </div>
          <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        </header>

        <div className="space-y-5 p-4">
          {MARKDOWNS.map(({ campo, rotulo, arquivo }) => {
            const valor = agente[campo] as string | null;
            return (
              <div key={campo}>
                <div className="mb-1.5 flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{rotulo}</span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {arquivo}
                  </span>
                </div>
                <p className="whitespace-pre-wrap rounded-md bg-background p-3 text-sm text-foreground">
                  {valor?.trim() || (
                    <span className="text-muted-foreground/70">(ainda não escrito)</span>
                  )}
                </p>
              </div>
            );
          })}
        </div>

        <div className="mt-auto border-t border-border p-4">
          <Link
            href={`/agentes/${agente.id}`}
            className={buttonVariants({ variant: "outline", className: "w-full" })}
          >
            Abrir o cinto de instrumentos
          </Link>
        </div>
      </aside>
    </div>
  );
}

// ───────────────────────── Rótulo de seção ─────────────────────────

function RotuloSecao({
  Icone,
  contagem,
  children,
}: {
  Icone: typeof Clock;
  contagem?: number;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-7 mb-3 flex items-center gap-2">
      <Icone className="size-4 text-primary" />
      <span className="text-sm font-medium text-foreground">{children}</span>
      {contagem != null && (
        <span className="text-sm text-muted-foreground">{contagem}</span>
      )}
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}
