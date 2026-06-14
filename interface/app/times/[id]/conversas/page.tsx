import { notFound } from "next/navigation";

import { type Conversa, type PapelAcesso, type Time } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { ConversasCliente } from "./conversas-cliente";

async function carregar(timeId: string): Promise<{
  time: Time;
  conversas: Conversa[];
  meuPapel: PapelAcesso | null;
} | null> {
  const [respTime, respConv, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/conversas`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respConv.ok) throw new Error("Falha ao carregar conversas");
  const time: Time = await respTime.json();
  return {
    time,
    conversas: await respConv.json(),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
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
  return <ConversasCliente time={dados.time} inicial={dados.conversas} />;
}
