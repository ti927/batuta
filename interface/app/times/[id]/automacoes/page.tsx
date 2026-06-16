import { notFound } from "next/navigation";

import {
  type Agente,
  type Automacao,
  type Instrumento,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { AutomacoesCliente } from "./automacoes-cliente";

async function carregar(timeId: string): Promise<{
  time: Time;
  automacoes: Automacao[];
  agentes: Agente[];
  instrumentos: Instrumento[];
  meuPapel: PapelAcesso | null;
} | null> {
  const [respTime, respAuto, respAg, respInst, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/automacoes`),
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarCerebro(`/times/${timeId}/instrumentos`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respAuto.ok || !respAg.ok || !respInst.ok)
    throw new Error("Falha ao carregar automações");
  const time: Time = await respTime.json();
  return {
    time,
    automacoes: await respAuto.json(),
    agentes: await respAg.json(),
    instrumentos: await respInst.json(),
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
      instrumentos={dados.instrumentos}
      meuPapel={dados.meuPapel}
    />
  );
}
