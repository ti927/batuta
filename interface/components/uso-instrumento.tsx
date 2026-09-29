"use client";

// "USADO POR" — quem depende deste instrumento (Fase 4, 2026-09-29).
//
// Com instrumentos da organização, um mesmo instrumento serve a vários times: mudar a
// configuração ou excluir afeta todos. Esta seção mostra quem depende dele, e o drawer
// consulta o mesmo endereço antes de excluir (o cérebro também recusa, com o motivo).

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export type UsoInstrumento = {
  times: { id: string; nome: string }[];
  agentes: { id: string; nome: string; time_id: string; time: string }[];
  automacoes: { id: string; nome: string; time_id: string }[];
  instrumentos: { id: string; nome: string; time_id: string }[];
};

export function buscarUso(instrumentoId: string): Promise<UsoInstrumento> {
  return api.get<UsoInstrumento>(`/instrumentos/${instrumentoId}/uso`);
}

export function emUso(uso: UsoInstrumento): boolean {
  return uso.agentes.length > 0 || uso.instrumentos.length > 0;
}

/** Frase curta com quem usa: "Revisor (Time A), Editor (Time B)". */
export function quemUsa(uso: UsoInstrumento): string {
  return [
    ...uso.agentes.map((a) => `${a.nome} (${a.time})`),
    ...uso.instrumentos.map((i) => `o pedido de aprovação “${i.nome}”`),
  ].join(", ");
}

export function UsadoPor({ instrumentoId }: { instrumentoId: string }) {
  const [uso, setUso] = useState<UsoInstrumento | null>(null);

  useEffect(() => {
    let vivo = true;
    buscarUso(instrumentoId)
      .then((u) => {
        if (vivo) setUso(u);
      })
      .catch(() => {
        /* informativo: sem a lista, o drawer segue funcionando */
      });
    return () => {
      vivo = false;
    };
  }, [instrumentoId]);

  if (!uso) return null;
  return (
    <section className="mt-6 border-t border-border pt-4">
      <h3 className="mb-2 text-sm font-medium text-foreground">Usado por</h3>
      {!emUso(uso) ? (
        <p className="text-xs text-muted-foreground">Nenhum agente usa este instrumento.</p>
      ) : (
        <div className="flex flex-col gap-2 text-xs">
          {uso.times.map((t) => (
            <div key={t.id}>
              <span className="font-medium text-foreground">{t.nome}</span>
              <span className="text-muted-foreground">
                {" — "}
                {[
                  ...uso.agentes.filter((a) => a.time_id === t.id).map((a) => a.nome),
                  ...uso.instrumentos
                    .filter((i) => i.time_id === t.id)
                    .map((i) => `pedido de aprovação “${i.nome}”`),
                ].join(", ")}
              </span>
            </div>
          ))}
          {uso.automacoes.length > 0 && (
            <div className="text-muted-foreground">
              Automações: {uso.automacoes.map((a) => a.nome).join(", ")}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
