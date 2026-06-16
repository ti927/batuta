import { notFound } from "next/navigation";

import {
  type Conversa,
  type MetricasAtendimento,
  type Time,
} from "@/lib/api";
import { buscarCerebro } from "@/lib/cerebro-servidor";

import { ConversasCliente } from "./conversas-cliente";

async function carregar(timeId: string): Promise<{
  time: Time;
  conversas: Conversa[];
  metricas: MetricasAtendimento | null;
} | null> {
  const [respTime, respConv, respMetricas] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/conversas`),
    buscarCerebro(`/times/${timeId}/conversas/metricas`),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respConv.ok) throw new Error("Falha ao carregar conversas");
  return {
    time: await respTime.json(),
    conversas: await respConv.json(),
    // As métricas são um plus; se falharem, a inbox ainda carrega.
    metricas: respMetricas.ok ? await respMetricas.json() : null,
  };
}

export default async function ConversasPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <ConversasCliente
      time={dados.time}
      inicial={dados.conversas}
      metricas={dados.metricas}
    />
  );
}
