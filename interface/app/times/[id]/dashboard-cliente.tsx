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
  Pencil,
  Plus,
} from "lucide-react";

import { CardAgente } from "@/components/card-agente";
import { DrawerAgente } from "@/components/drawer-agente";
import { Rise } from "@/components/rise";
import { RobotFace } from "@/components/robot-face";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { podeOperar } from "@/lib/permissoes";
import {
  caminhoPrincipal,
  inicialDaCadeia,
  type Agente,
  type Automacao,
  type Cadeia,
  type ExecucaoNaLista,
  type Instrumento,
  type PapelAcesso,
  type Time,
  type TimeResumo,
} from "@/lib/api";

// ── Estados de execução: rótulo amigável + variante de cor. ──
type VarianteBadge = "neutral" | "info" | "success" | "warning" | "error";
const ESTADO: Record<string, { label: string; variante: VarianteBadge }> = {
  aguardando: { label: "na fila", variante: "neutral" },
  em_andamento: { label: "em andamento", variante: "warning" },
  aguardando_humano: { label: "aguardando você", variante: "info" },
  concluida: { label: "concluída", variante: "success" },
  falhou: { label: "falhou", variante: "error" },
  cancelada: { label: "cancelada", variante: "neutral" },
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
  resumo,
  agentes,
  cintos,
  instrumentos,
  automacoes,
  recentes,
  conversaId,
}: {
  time: Time;
  meuPapel: PapelAcesso | null;
  resumo: TimeResumo | null;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  instrumentos: Instrumento[];
  automacoes: Automacao[];
  recentes: ExecucaoNaLista[];
  conversaId: string | null;
}) {
  // O drawer abre por id (não pelo objeto) para sobreviver ao router.refresh().
  const [abertoId, setAbertoId] = useState<string | null>(null);
  const [criando, setCriando] = useState(false);
  const souOperador = podeOperar(meuPapel);

  const agenteAberto = abertoId
    ? (agentes.find((a) => a.id === abertoId) ?? null)
    : null;

  const pendencias = resumo?.pendencias ?? 0;
  const custo = resumo?.custo_acumulado_usd ?? 0;
  const totalExec = resumo?.execucoes ?? recentes.length;
  const taxa = resumo?.taxa_sucesso ?? null;

  return (
    <main className="mx-auto w-full max-w-[1000px] px-5 py-8 sm:px-8">
      <Rise>
        {/* Stat cards — a visão de saúde do time (só leitura). */}
        <div className="flex flex-wrap gap-3.5">
          <StatCard
            Icone={MessageSquare}
            tom={{ bg: "#FDF1E3", fg: "#E89638" }}
            rotulo="Aguardando você"
            valor={
              pendencias > 0
                ? `${pendencias} ${pendencias === 1 ? "pendente" : "pendentes"}`
                : "Nada pendente"
            }
            sub={
              pendencias > 0 ? "uma execução parou pra você →" : "nenhum fluxo parado"
            }
            acento={pendencias > 0}
            href={pendencias > 0 ? `/times/${time.id}/execucoes` : undefined}
          />
          <StatCard
            Icone={Gauge}
            tom={{ bg: "#E6F4EA", fg: "#3DAA5C" }}
            rotulo="Custo acumulado"
            valor={`~US$ ${custo.toFixed(2)}`}
            sub={`${totalExec} ${totalExec === 1 ? "execução" : "execuções"} · estimado`}
          />
          <StatCard
            Icone={Activity}
            tom={{ bg: "#E6F4EA", fg: "#3DAA5C" }}
            rotulo="Taxa de sucesso"
            valor={taxa === null ? "—" : `${Math.round(taxa * 100)}%`}
            sub={taxa === null ? "sem execuções finalizadas" : "das finalizadas"}
          />
        </div>

        {/* Cadeia */}
        {automacoes.some((a) => inicialDaCadeia(a.cadeia)) && (
          <>
            <RotuloSecao
              Icone={GitBranch}
              acao={
                <Link
                  href={`/times/${time.id}/automacoes`}
                  className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                >
                  <Pencil className="size-3.5" /> Editar a automação
                </Link>
              }
            >
              Cadeia · o caminho da tarefa
            </RotuloSecao>
            <div className="space-y-4">
              {automacoes
                .filter((a) => inicialDaCadeia(a.cadeia))
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

        {/* Execuções recentes — abrem o detalhe na aba Execuções. */}
        <RotuloSecao
          Icone={Activity}
          acao={
            recentes.length > 0 ? (
              <Link
                href={`/times/${time.id}/execucoes`}
                className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
              >
                Ver todas
              </Link>
            ) : undefined
          }
        >
          Execuções recentes
        </RotuloSecao>
        {recentes.length === 0 ? (
          <EstadoVazio icone={Activity} titulo="Nenhuma execução ainda.">
            Quando este time rodar, as execuções aparecem aqui.
          </EstadoVazio>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            {recentes.slice(0, 3).map((e, i) => {
              const est = ESTADO[e.estado] ?? ESTADO.aguardando;
              return (
                <Link
                  key={e.id}
                  href={`/times/${time.id}/execucoes/${e.id}`}
                  className={`flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent/50 ${
                    i > 0 ? "border-t border-border" : ""
                  }`}
                >
                  <Badge variant={est.variante}>{est.label}</Badge>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-foreground">
                      {e.entrada?.texto || e.automacao_nome}
                    </span>
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
        <RotuloSecao
          Icone={Bot}
          contagem={agentes.length}
          acao={
            souOperador ? (
              <Button size="sm" variant="outline" onClick={() => setCriando(true)}>
                <Plus className="size-4" /> Novo agente
              </Button>
            ) : undefined
          }
        >
          Agentes
        </RotuloSecao>
        {agentes.length === 0 ? (
          <EstadoVazio icone={Bot} titulo="Nenhum agente ainda.">
            {souOperador
              ? "Converse com a IA ou clique em Novo agente para montar o time."
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
                onAbrir={() => setAbertoId(a.id)}
              />
            ))}
          </div>
        )}
      </Rise>

      {/* Criar agente */}
      {criando && (
        <DrawerAgente
          key="novo"
          agente={null}
          indice={agentes.length}
          cinto={[]}
          instrumentosTime={instrumentos}
          time={time}
          meuPapel={meuPapel}
          conversaId={conversaId}
          onFechar={() => setCriando(false)}
        />
      )}

      {/* Ver/editar agente */}
      {agenteAberto && (
        <DrawerAgente
          key={agenteAberto.id}
          agente={agenteAberto}
          indice={agentes.indexOf(agenteAberto)}
          cinto={cintos[agenteAberto.id] ?? []}
          instrumentosTime={instrumentos}
          time={time}
          meuPapel={meuPapel}
          conversaId={conversaId}
          onFechar={() => setAbertoId(null)}
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
        {href && <ChevronRight className="ml-auto size-4 text-muted-foreground/60" />}
      </div>
      <div className="font-heading text-2xl font-medium leading-tight text-foreground">
        {valor}
      </div>
      <div className="mt-1 text-xs" style={{ color: acento ? "#E89638" : undefined }}>
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

function CadeiaHorizontal({ cadeia, agentes }: { cadeia: Cadeia; agentes: Agente[] }) {
  // Segue a primeira saída de cada nó, do início ao fim/repetição (visão linear
  // do caminho principal; bifurcações completas vivem na aba Automações).
  const ordem = caminhoPrincipal(cadeia);

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
      {ordem.map((no, i) => {
        const idx = agentes.findIndex((a) => a.id === no.ref);
        const ag = agentes[idx];
        const pausa = no.gate;
        const rotulo = no.tipo === "roteador" ? (no.nome ?? "Roteador") : (ag?.nome ?? "—");
        return (
          <div key={no.id} className="flex items-center gap-2">
            <Chip>
              <RobotFace size={24} indice={idx} lider={ag?.papel === "lider"} />
              <span className="text-[13px] font-medium text-foreground">
                {rotulo}
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

// ───────────────────────── Rótulo de seção ─────────────────────────

function RotuloSecao({
  Icone,
  contagem,
  acao,
  children,
}: {
  Icone: typeof Clock;
  contagem?: number;
  acao?: React.ReactNode;
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
      {acao}
    </div>
  );
}
