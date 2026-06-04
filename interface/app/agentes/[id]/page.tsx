import { notFound } from "next/navigation";

import { type Agente, type Instrumento, type PapelAcesso, type Time } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { CintoCliente } from "./cinto-cliente";

async function carregar(agenteId: string): Promise<{
  agente: Agente;
  cinto: Instrumento[];
  instrumentosDoTime: Instrumento[];
  meuPapel: PapelAcesso | null;
} | null> {
  const respAg = await buscarCerebro(`/agentes/${agenteId}`);
  if (respAg.status === 404) return null;
  if (!respAg.ok) throw new Error("Falha ao carregar o agente");
  const agente: Agente = await respAg.json();

  const [respCinto, respTime, respTimeObj, eu] = await Promise.all([
    buscarCerebro(`/agentes/${agenteId}/instrumentos`),
    buscarCerebro(`/times/${agente.time_id}/instrumentos`),
    buscarCerebro(`/times/${agente.time_id}`),
    buscarMeuAcesso(),
  ]);
  if (!respCinto.ok || !respTime.ok || !respTimeObj.ok)
    throw new Error("Falha ao carregar o cinto");

  const time: Time = await respTimeObj.json();
  return {
    agente,
    cinto: await respCinto.json(),
    instrumentosDoTime: await respTime.json(),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
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
      meuPapel={dados.meuPapel}
    />
  );
}
