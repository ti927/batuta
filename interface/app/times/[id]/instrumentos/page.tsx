import { notFound } from "next/navigation";

import {
  type Instrumento,
  type PapelAcesso,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { InstrumentosCliente } from "./instrumentos-cliente";

async function jsonOu<T>(resp: Response, padrao: T): Promise<T> {
  return resp.ok ? ((await resp.json()) as T) : padrao;
}

async function carregar(timeId: string): Promise<{
  time: Time;
  instrumentos: Instrumento[];
  tipos: TipoInstrumento[];
  meuPapel: PapelAcesso | null;
} | null> {
  // Quem usa cada instrumento já vem na lista (o cérebro monta de uma vez).
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
    instrumentos: await jsonOu<Instrumento[]>(respInst, []),
    tipos: await jsonOu<TipoInstrumento[]>(respTipos, []),
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
  // SEM `key` de versão aqui (de propósito): remontar a aba a cada save/connect
  // zerava o estado local e FECHAVA o drawer no meio da edição. A lista é
  // renderizada direto da prop `inicial`, então o router.refresh já a atualiza
  // sem remontar — e o drawer (decisão do maestro) fica aberto até fechar à mão.
  return (
    <InstrumentosCliente
      time={dados.time}
      inicial={dados.instrumentos}
      tipos={dados.tipos}
      meuPapel={dados.meuPapel}
    />
  );
}
