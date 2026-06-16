"use client";

import Link from "next/link";
import { useState } from "react";
import { Inbox } from "lucide-react";

import { type Conversa, type MetricasAtendimento, type Time } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";

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

export function ConversasCliente({
  time,
  inicial,
  metricas,
}: {
  time: Time;
  inicial: Conversa[];
  metricas: MetricasAtendimento | null;
}) {
  const [filtro, setFiltro] = useState("abertas");
  const lista = inicial.filter((c) => visivel(c, filtro));

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <h2 className="text-sm font-medium text-foreground">Conversas</h2>
        <p className="text-sm text-muted-foreground">
          As conversas dos canais deste time. Abra uma para acompanhar, assumir o
          atendimento ou responder.
        </p>
      </div>

      {metricas && metricas.total > 0 && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
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
          return (
            <Button
              key={f.valor}
              size="sm"
              variant={filtro === f.valor ? "default" : "outline"}
              onClick={() => setFiltro(f.valor)}
            >
              {f.rotulo} ({n})
            </Button>
          );
        })}
      </div>

      {lista.length === 0 ? (
        <EstadoVazio icone={Inbox} titulo="Nenhuma conversa neste filtro.">
          As conversas aparecem aqui quando alguém escreve para um canal (bot do
          Telegram) ligado a um agente deste time.
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {lista.map((c) => {
            const e = ESTADO_CONVERSA[c.estado] ?? {
              rotulo: c.estado,
              variante: "neutral" as VarianteBadge,
            };
            return (
              <li key={c.id}>
                <Link
                  href={`/times/${time.id}/conversas/${c.id}`}
                  className="flex items-center gap-3 p-3 text-sm hover:bg-muted/50"
                >
                  <Badge variant={e.variante}>{e.rotulo}</Badge>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-foreground">
                      {c.contato_nome || c.contato_chave}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {c.turnos} {c.turnos === 1 ? "turno" : "turnos"} · atualizada{" "}
                      {new Date(c.atualizado_em).toLocaleString("pt-BR")}
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
