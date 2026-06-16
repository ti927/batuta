"use client";

import Link from "next/link";
import { useState } from "react";
import { Activity, ChevronRight } from "lucide-react";

import { type ExecucaoNaLista, type Time, type TimeResumo } from "@/lib/api";
import { ESTADO, formatarData } from "@/components/inspecao-execucao";
import { Badge } from "@/components/ui/badge";
import { EstadoVazio } from "@/components/ui/estado-vazio";

const FILTROS: { valor: string; rotulo: string; casa: (e: string) => boolean }[] = [
  { valor: "todas", rotulo: "Todas", casa: () => true },
  { valor: "concluida", rotulo: "Concluídas", casa: (e) => e === "concluida" },
  {
    valor: "aguardando_humano",
    rotulo: "Aguardando você",
    casa: (e) => e === "aguardando_humano",
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
}: {
  time: Time;
  inicial: ExecucaoNaLista[];
  resumo: TimeResumo | null;
}) {
  const [filtro, setFiltro] = useState("todas");
  const lista = inicial.filter((e) => FILTROS.find((f) => f.valor === filtro)!.casa(e.estado));

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
      </div>

      {lista.length === 0 ? (
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
