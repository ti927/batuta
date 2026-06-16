"use client";

import { useState } from "react";
import { Bot, Plus } from "lucide-react";

import {
  type Agente,
  type Instrumento,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { CardAgente } from "@/components/card-agente";
import { DrawerAgente } from "@/components/drawer-agente";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";

export function AgentesCliente({
  time,
  inicial,
  cintos,
  instrumentos,
  meuPapel,
  conversaId,
}: {
  time: Time;
  inicial: Agente[];
  cintos: Record<string, Instrumento[]>;
  instrumentos: Instrumento[];
  meuPapel: PapelAcesso | null;
  conversaId: string | null;
}) {
  const souOperador = podeOperar(meuPapel);
  // O drawer abre por id (não pelo objeto) para sobreviver ao router.refresh():
  // o agente é re-derivado da prop recarregada. `criando` abre o drawer vazio.
  const [abertoId, setAbertoId] = useState<string | null>(null);
  const [criando, setCriando] = useState(false);
  const agenteAberto = abertoId
    ? (inicial.find((a) => a.id === abertoId) ?? null)
    : null;

  return (
    <main className="mx-auto w-full max-w-[1000px] px-5 py-8 sm:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-foreground">Agentes do time</h2>
          <p className="text-sm text-muted-foreground">
            Cada agente é um especialista. Clique num card para editar quem ele é,
            o que sabe e o seu cinto.
          </p>
        </div>
        {souOperador && (
          <Button onClick={() => setCriando(true)}>
            <Plus className="size-4" /> Novo agente
          </Button>
        )}
      </div>

      {inicial.length === 0 ? (
        <EstadoVazio icone={Bot} titulo="Nenhum agente ainda.">
          {souOperador
            ? "Converse com a IA ou clique em Novo agente para montar o time."
            : "Os agentes deste time aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <div className="grid gap-2.5 sm:grid-cols-2">
          {inicial.map((a, i) => (
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

      {criando && (
        <DrawerAgente
          key="novo"
          agente={null}
          indice={inicial.length}
          cinto={[]}
          instrumentosTime={instrumentos}
          time={time}
          meuPapel={meuPapel}
          conversaId={conversaId}
          onFechar={() => setCriando(false)}
        />
      )}

      {agenteAberto && (
        <DrawerAgente
          key={agenteAberto.id}
          agente={agenteAberto}
          indice={inicial.indexOf(agenteAberto)}
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
