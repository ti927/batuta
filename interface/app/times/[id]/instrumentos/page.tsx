import { notFound } from "next/navigation";

import { type Instrumento, type TipoInstrumento, type Time } from "@/lib/api";

import { InstrumentosCliente } from "./instrumentos-cliente";

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function carregar(timeId: string): Promise<{
  time: Time;
  instrumentos: Instrumento[];
  tipos: TipoInstrumento[];
} | null> {
  const [respTime, respInst, respTipos] = await Promise.all([
    fetch(`${BASE}/times/${timeId}`, { cache: "no-store" }),
    fetch(`${BASE}/times/${timeId}/instrumentos`, { cache: "no-store" }),
    fetch(`${BASE}/instrumentos/tipos`, { cache: "no-store" }),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respInst.ok || !respTipos.ok)
    throw new Error("Falha ao carregar instrumentos");
  return {
    time: await respTime.json(),
    instrumentos: await respInst.json(),
    tipos: await respTipos.json(),
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
    />
  );
}
