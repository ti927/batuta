"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { type Conversa, type MetricasAtendimento, type Time } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

// Segundos → texto curto e humano ("12s", "3 min", "1.2 h", ou "—").
function formataDuracao(s: number | null): string {
  if (s === null || s === undefined) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  const min = Math.round(s / 60);
  return min < 60 ? `${min} min` : `${(min / 60).toFixed(1)} h`;
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
    <div className="rounded-xl border border-border bg-card p-3">
      <div className="text-xs text-muted-foreground">{rotulo}</div>
      <div className="mt-1 text-xl font-medium text-foreground">{valor}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

type VarianteBadge = "neutral" | "info" | "success" | "warning" | "error";

// Cada estado de conversa vira um selo (cor + rótulo em português).
export const ESTADO_CONVERSA: Record<
  string,
  { rotulo: string; variante: VarianteBadge }
> = {
  aberta: { rotulo: "Aberta", variante: "neutral" },
  bot_respondendo: { rotulo: "Bot respondendo", variante: "warning" },
  aguardando_resposta: { rotulo: "Aguardando resposta", variante: "info" },
  humano_assumiu: { rotulo: "Com humano", variante: "success" },
  fechada: { rotulo: "Fechada", variante: "neutral" },
};

const FILTROS: { valor: string; rotulo: string }[] = [
  { valor: "abertas", rotulo: "Em andamento" },
  { valor: "humano_assumiu", rotulo: "Com humano" },
  { valor: "fechada", rotulo: "Fechadas" },
  { valor: "todos", rotulo: "Todas" },
];

// "Em andamento" = tudo que não está fechado (o dia a dia da inbox).
function visivel(c: Conversa, filtro: string): boolean {
  if (filtro === "todos") return true;
  if (filtro === "abertas") return c.estado !== "fechada";
  return c.estado === filtro;
}

function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).slice(0, 2);
  return partes.map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
}

/**
 * Casca two-pane da aba Conversas: métricas + filtros no topo, lista à esquerda
 * e a conversa selecionada (`children`, vinda da rota /conversas/[convId]) à
 * direita. A conversa ativa vem da URL — selecionar é navegar.
 */
export function ConversasShell({
  time,
  inicial,
  metricas,
  children,
}: {
  time: Time;
  inicial: Conversa[];
  metricas: MetricasAtendimento | null;
  children: React.ReactNode;
}) {
  const [filtro, setFiltro] = useState("abertas");
  const pathname = usePathname();
  const ativaId = pathname.match(/\/conversas\/([^/]+)/)?.[1] ?? null;
  const lista = inicial.filter((c) => visivel(c, filtro));

  return (
    <main className="mx-auto w-full max-w-[1100px] px-5 py-6 sm:px-8">
      <div className="mb-4">
        <h2 className="text-sm font-medium text-foreground">Conversas</h2>
        <p className="text-sm text-muted-foreground">
          As conversas dos canais deste time. Abra uma para acompanhar, assumir o
          atendimento ou responder.
        </p>
      </div>

      {metricas && metricas.total > 0 && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <CartaoMetrica
            rotulo="Conversas"
            valor={String(metricas.total)}
            sub={`últimos ${metricas.periodo_dias} dias`}
          />
          <CartaoMetrica rotulo="Em andamento" valor={String(metricas.abertas)} />
          <CartaoMetrica
            rotulo="Foram p/ humano"
            valor={String(metricas.com_humano)}
            sub={`${metricas.percent_humano}%`}
          />
          <CartaoMetrica
            rotulo="1ª resposta (média)"
            valor={formataDuracao(metricas.tempo_resposta_medio_s)}
          />
          <CartaoMetrica
            rotulo="Custo de IA"
            valor={`~US$ ${metricas.custo_total_usd.toFixed(2)}`}
          />
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        {FILTROS.map((f) => {
          const n = inicial.filter((c) => visivel(c, f.valor)).length;
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
      </div>

      <div className="grid gap-4 lg:h-[70vh] lg:grid-cols-[340px_1fr]">
        {/* Pane esquerdo: a lista de conversas (rola por dentro). */}
        <div className="overflow-y-auto rounded-xl border border-border bg-card">
          {lista.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">
              Nenhuma conversa neste filtro.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {lista.map((c) => {
                const e = ESTADO_CONVERSA[c.estado] ?? {
                  rotulo: c.estado,
                  variante: "neutral" as VarianteBadge,
                };
                const ativa = c.id === ativaId;
                const nome = c.contato_nome || c.contato_chave;
                return (
                  <li key={c.id}>
                    <Link
                      href={`/times/${time.id}/conversas/${c.id}`}
                      className={`flex items-center gap-3 p-3 text-sm transition-colors ${
                        ativa
                          ? "bg-accent/60"
                          : "hover:bg-muted/50"
                      }`}
                    >
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-medium text-accent-foreground">
                        {iniciais(nome)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2">
                          <span className="truncate font-medium text-foreground">
                            {nome}
                          </span>
                          <Badge variant={e.variante} className="ml-auto shrink-0">
                            {e.rotulo}
                          </Badge>
                        </span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {c.turnos} {c.turnos === 1 ? "turno" : "turnos"} ·{" "}
                          {new Date(c.atualizado_em).toLocaleString("pt-BR")}
                        </span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Pane direito: a conversa selecionada (ou o estado-vazio). */}
        <div className="flex min-h-[55vh] flex-col overflow-hidden rounded-xl border border-border bg-card lg:min-h-0">
          {children}
        </div>
      </div>
    </main>
  );
}
