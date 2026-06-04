import { notFound } from "next/navigation";

import { type Agente, type PapelAcesso, type Time } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { AgentesCliente } from "./agentes-cliente";

async function carregar(timeId: string): Promise<{
  time: Time;
  agentes: Agente[];
  meuPapel: PapelAcesso | null;
} | null> {
  const [respTime, respAgentes, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respAgentes.ok) throw new Error("Falha ao carregar o time");
  const time: Time = await respTime.json();
  return {
    time,
    agentes: await respAgentes.json(),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
  };
}

export default async function TimePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <AgentesCliente
      time={dados.time}
      inicial={dados.agentes}
      meuPapel={dados.meuPapel}
    />
  );
}
