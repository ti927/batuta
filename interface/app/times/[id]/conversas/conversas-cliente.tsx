"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronLeft, Inbox } from "lucide-react";

import { type Conversa, type Time } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";

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
}: {
  time: Time;
  inicial: Conversa[];
}) {
  const [filtro, setFiltro] = useState("abertas");
  const lista = inicial.filter((c) => visivel(c, filtro));

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <Link
        href={`/times/${time.id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        {time.nome}
      </Link>
      <h1 className="mt-2 text-2xl font-medium text-foreground">Conversas</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">
        As conversas dos canais deste time. Abra uma para acompanhar, assumir o
        atendimento ou responder.
      </p>

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
