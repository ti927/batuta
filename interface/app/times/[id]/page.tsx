import { notFound } from "next/navigation";

import {
  type Agente,
  type Automacao,
  type ConversaCriacaoResumo,
  type ExecucaoNaLista,
  type Instrumento,
  type PapelAcesso,
  type Time,
  type TimeResumo,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { DashboardCliente } from "./dashboard-cliente";

async function jsonOu<T>(resp: Response, padrao: T): Promise<T> {
  return resp.ok ? ((await resp.json()) as T) : padrao;
}

async function carregar(timeId: string): Promise<{
  time: Time;
  meuPapel: PapelAcesso | null;
  resumo: TimeResumo | null;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  instrumentos: Instrumento[];
  automacoes: Automacao[];
  recentes: ExecucaoNaLista[];
  conversaId: string | null;
} | null> {
  const [respTime, respResumo, respAgentes, respAutomacoes, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/resumo`),
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarCerebro(`/times/${timeId}/automacoes`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok) throw new Error("Falha ao carregar o time");

  const time: Time = await respTime.json();
  const agentes = await jsonOu<Agente[]>(respAgentes, []);
  const meuPapel = eu?.papeis[time.organizacao_id] ?? null;

  // Cinto de cada agente (chips + drawer), instrumentos do time (drawer do
  // cinto), execuções recentes e a conversa companheira — em paralelo.
  const [cintosPares, instrumentosResp, execResp, conversasResp] =
    await Promise.all([
      Promise.all(
        agentes.map(async (a) => {
          const r = await buscarCerebro(`/agentes/${a.id}/instrumentos`);
          return [a.id, await jsonOu<Instrumento[]>(r, [])] as const;
        }),
      ),
      buscarCerebro(`/times/${timeId}/instrumentos`),
      buscarCerebro(`/times/${timeId}/execucoes`),
      buscarCerebro(`/organizacoes/${time.organizacao_id}/conversas-criacao`),
    ]);

  const conversas = await jsonOu<ConversaCriacaoResumo[]>(conversasResp, []);
  return {
    time,
    meuPapel,
    resumo: respResumo.ok ? await respResumo.json() : null,
    agentes,
    cintos: Object.fromEntries(cintosPares),
    instrumentos: await jsonOu<Instrumento[]>(instrumentosResp, []),
    automacoes: await jsonOu<Automacao[]>(respAutomacoes, []),
    recentes: await jsonOu<ExecucaoNaLista[]>(execResp, []),
    conversaId: conversas.find((c) => c.time_id === timeId)?.id ?? null,
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
  return <DashboardCliente {...dados} />;
}
