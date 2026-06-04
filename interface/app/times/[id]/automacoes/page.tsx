import { notFound } from "next/navigation";

import {
  type Agente,
  type Automacao,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { AutomacoesCliente } from "./automacoes-cliente";

async function carregar(timeId: string): Promise<{
  time: Time;
  automacoes: Automacao[];
  agentes: Agente[];
  meuPapel: PapelAcesso | null;
} | null> {
  const [respTime, respAuto, respAg, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/automacoes`),
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respAuto.ok || !respAg.ok)
    throw new Error("Falha ao carregar automações");
  const time: Time = await respTime.json();
  return {
    time,
    automacoes: await respAuto.json(),
    agentes: await respAg.json(),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
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
      meuPapel={dados.meuPapel}
    />
  );
}
