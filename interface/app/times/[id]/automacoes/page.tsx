import { notFound } from "next/navigation";

import { type Agente, type Automacao, type Time } from "@/lib/api";
import { buscarCerebro } from "@/lib/cerebro-servidor";

import { AutomacoesCliente } from "./automacoes-cliente";

async function carregar(timeId: string): Promise<{
  time: Time;
  automacoes: Automacao[];
  agentes: Agente[];
} | null> {
  const [respTime, respAuto, respAg] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/automacoes`),
    buscarCerebro(`/times/${timeId}/agentes`),
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
