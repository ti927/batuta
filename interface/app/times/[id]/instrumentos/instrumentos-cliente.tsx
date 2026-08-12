"use client";

import { useState } from "react";
import { Pencil, Plus, ShieldCheck, Wrench } from "lucide-react";

import {
  type Instrumento,
  type PapelAcesso,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { ConstrutorInstrumento } from "@/components/construtor-instrumento";
import { DrawerInstrumento } from "@/components/drawer-instrumento";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";

export function InstrumentosCliente({
  time,
  inicial,
  tipos,
  usadoPor,
  meuPapel,
}: {
  time: Time;
  inicial: Instrumento[];
  tipos: TipoInstrumento[];
  usadoPor: Record<string, string[]>;
  meuPapel: PapelAcesso | null;
}) {
  const souOperador = podeOperar(meuPapel);
  // null = fechado; "novo" = criando; instrumento = editando.
  const [aberto, setAberto] = useState<null | "novo" | Instrumento>(null);
  // Construtor de Instrumento (conector): overlay de tela cheia, separado do
  // formulário genérico. "novo" = criar; instrumento = editar um conector.
  const [construtor, setConstrutor] = useState<null | "novo" | Instrumento>(null);

  return (
    <main className="mx-auto w-full max-w-[1000px] px-5 py-8 sm:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-foreground">
            Instrumentos do time
          </h2>
          <p className="text-sm text-muted-foreground">
            As ferramentas que os agentes podem usar. Um instrumento pode exigir sua
            aprovação antes de agir.
          </p>
        </div>
        {souOperador && (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setConstrutor("novo")}>
              🌟 Criar instrumento
            </Button>
            <Button
              variant="outline"
              onClick={() => setAberto("novo")}
              disabled={tipos.length === 0}
            >
              <Plus className="size-4" /> Instrumento pronto
            </Button>
          </div>
        )}
      </div>

      {inicial.length === 0 ? (
        <EstadoVazio icone={Wrench} titulo="Nenhum instrumento ainda.">
          {souOperador
            ? "Crie instrumentos para os agentes usarem (APIs, banco, web…)."
            : "Os instrumentos deste time aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          {inicial.map((inst, i) => {
            const usos = usadoPor[inst.id] ?? [];
            return (
              <button
                key={inst.id}
                onClick={() =>
                  souOperador &&
                  (inst.tipo === "conector" ? setConstrutor(inst) : setAberto(inst))
                }
                disabled={!souOperador}
                className={`flex w-full items-center gap-3 px-4 py-3 text-left transition-colors ${
                  souOperador ? "hover:bg-accent/50" : "cursor-default"
                } ${i > 0 ? "border-t border-border" : ""}`}
              >
                <span className="flex size-8 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                  <IconeInstrumento icone={inst.icone} className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-foreground">
                      {inst.nome}
                    </span>
                    {inst.acao_irreversivel && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-[#FDF1E3] px-2 py-0.5 text-xs text-[#A05E16]">
                        <ShieldCheck className="size-3" /> exige aprovação
                      </span>
                    )}
                  </span>
                  <span className="block truncate font-mono text-xs text-muted-foreground">
                    {inst.tipo}
                    {usos.length > 0 && (
                      <span className="font-sans"> · usado por {usos.join(", ")}</span>
                    )}
                  </span>
                </span>
                {souOperador && (
                  <Pencil className="size-4 shrink-0 text-muted-foreground/60" />
                )}
              </button>
            );
          })}
        </div>
      )}

      {aberto && (
        <DrawerInstrumento
          key={aberto === "novo" ? "novo" : aberto.id}
          instrumento={aberto === "novo" ? null : aberto}
          tipos={tipos}
          time={time}
          meuPapel={meuPapel}
          onFechar={() => setAberto(null)}
          onSalvou={(salvo) => setAberto(salvo)}
        />
      )}

      {construtor && (
        <ConstrutorInstrumento
          key={construtor === "novo" ? "novo" : construtor.id}
          time={time}
          instrumento={construtor === "novo" ? null : construtor}
          onFechar={() => setConstrutor(null)}
          onSalvou={(salvo) => setConstrutor(salvo)}
        />
      )}
    </main>
  );
}
