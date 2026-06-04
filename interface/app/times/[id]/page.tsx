import { notFound } from "next/navigation";

import { type Agente, type Time } from "@/lib/api";
import { buscarCerebro } from "@/lib/cerebro-servidor";

import { AgentesCliente } from "./agentes-cliente";

async function carregar(
  timeId: string,
): Promise<{ time: Time; agentes: Agente[] } | null> {
  const [respTime, respAgentes] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/agentes`),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respAgentes.ok) throw new Error("Falha ao carregar o time");
  return { time: await respTime.json(), agentes: await respAgentes.json() };
}

export default async function TimePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return <AgentesCliente time={dados.time} inicial={dados.agentes} />;
}
