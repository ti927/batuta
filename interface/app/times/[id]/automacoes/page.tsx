import { notFound } from "next/navigation";

import { type Agente, type Automacao, type Time } from "@/lib/api";

import { AutomacoesCliente } from "./automacoes-cliente";

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function carregar(timeId: string): Promise<{
  time: Time;
  automacoes: Automacao[];
  agentes: Agente[];
} | null> {
  const [respTime, respAuto, respAg] = await Promise.all([
    fetch(`${BASE}/times/${timeId}`, { cache: "no-store" }),
    fetch(`${BASE}/times/${timeId}/automacoes`, { cache: "no-store" }),
    fetch(`${BASE}/times/${timeId}/agentes`, { cache: "no-store" }),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respAuto.ok || !respAg.ok)
    throw new Error("Falha ao carregar automações");
  return {
    time: await respTime.json(),
    automacoes: await respAuto.json(),
    agentes: await respAg.json(),
  };
}

export default async function AutomacoesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <AutomacoesCliente
      time={dados.time}
      inicial={dados.automacoes}
      agentes={dados.agentes}
    />
  );
}
