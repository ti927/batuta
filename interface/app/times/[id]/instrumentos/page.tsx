import { notFound } from "next/navigation";

import {
  type Instrumento,
  type PapelAcesso,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { InstrumentosCliente } from "./instrumentos-cliente";

async function carregar(timeId: string): Promise<{
  time: Time;
  instrumentos: Instrumento[];
  tipos: TipoInstrumento[];
  meuPapel: PapelAcesso | null;
} | null> {
  const [respTime, respInst, respTipos, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/instrumentos`),
    buscarCerebro(`/instrumentos/tipos`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respInst.ok || !respTipos.ok)
    throw new Error("Falha ao carregar instrumentos");
  const time: Time = await respTime.json();
  return {
    time,
    instrumentos: await respInst.json(),
    tipos: await respTipos.json(),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
  };
}

export default async function InstrumentosPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <InstrumentosCliente
      time={dados.time}
      inicial={dados.instrumentos}
      tipos={dados.tipos}
      meuPapel={dados.meuPapel}
    />
  );
}
