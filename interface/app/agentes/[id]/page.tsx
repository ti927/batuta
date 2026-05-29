import { notFound } from "next/navigation";

import { type Agente, type Instrumento } from "@/lib/api";

import { CintoCliente } from "./cinto-cliente";

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function carregar(agenteId: string): Promise<{
  agente: Agente;
  cinto: Instrumento[];
  instrumentosDoTime: Instrumento[];
} | null> {
  const respAg = await fetch(`${BASE}/agentes/${agenteId}`, { cache: "no-store" });
  if (respAg.status === 404) return null;
  if (!respAg.ok) throw new Error("Falha ao carregar o agente");
  const agente: Agente = await respAg.json();

  const [respCinto, respTime] = await Promise.all([
    fetch(`${BASE}/agentes/${agenteId}/instrumentos`, { cache: "no-store" }),
    fetch(`${BASE}/times/${agente.time_id}/instrumentos`, { cache: "no-store" }),
  ]);
  if (!respCinto.ok || !respTime.ok)
    throw new Error("Falha ao carregar o cinto");

  return {
    agente,
    cinto: await respCinto.json(),
    instrumentosDoTime: await respTime.json(),
  };
}

export default async function AgentePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <CintoCliente
      agente={dados.agente}
      cinto={dados.cinto}
      instrumentosDoTime={dados.instrumentosDoTime}
    />
  );
}
