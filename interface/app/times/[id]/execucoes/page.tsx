import { notFound } from "next/navigation";

import {
  type ExecucaoNaLista,
  type PapelAcesso,
  type Time,
  type TimeResumo,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { ExecucoesCliente } from "./execucoes-cliente";

async function jsonOu<T>(resp: Response, padrao: T): Promise<T> {
  return resp.ok ? ((await resp.json()) as T) : padrao;
}

async function carregar(timeId: string): Promise<{
  time: Time;
  execucoes: ExecucaoNaLista[];
  resumo: TimeResumo | null;
  meuPapel: PapelAcesso | null;
} | null> {
  const [respTime, respExec, respResumo, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/execucoes`),
    buscarCerebro(`/times/${timeId}/resumo`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok) throw new Error("Falha ao carregar o time");
  const time: Time = await respTime.json();
  return {
    time,
    execucoes: await jsonOu<ExecucaoNaLista[]>(respExec, []),
    resumo: respResumo.ok ? await respResumo.json() : null,
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
  };
}

export default async function ExecucoesTabPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <ExecucoesCliente
      time={dados.time}
      inicial={dados.execucoes}
      resumo={dados.resumo}
      meuPapel={dados.meuPapel}
    />
  );
}
