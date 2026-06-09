import { notFound } from "next/navigation";

import {
  type Agente,
  type Automacao,
  type ConversaCriacaoResumo,
  type Execucao,
  type Instrumento,
  type PapelAcesso,
  type ResumoUso,
  type Time,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { DashboardCliente, type ExecucaoRecente } from "./dashboard-cliente";

async function jsonOu<T>(resp: Response, padrao: T): Promise<T> {
  return resp.ok ? ((await resp.json()) as T) : padrao;
}

async function carregar(timeId: string): Promise<{
  time: Time;
  meuPapel: PapelAcesso | null;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  automacoes: Automacao[];
  recentes: ExecucaoRecente[];
  aguardando: number;
  pendenteAutomacaoId: string | null;
  totalExecucoes: number;
  custo: ResumoUso | null;
  conversaId: string | null;
} | null> {
  const [respTime, respAgentes, respAutomacoes, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarCerebro(`/times/${timeId}/automacoes`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok) throw new Error("Falha ao carregar o time");

  const time: Time = await respTime.json();
  const agentes = await jsonOu<Agente[]>(respAgentes, []);
  const automacoes = await jsonOu<Automacao[]>(respAutomacoes, []);
  const meuPapel = eu?.papeis[time.organizacao_id] ?? null;

  // Cinto de cada agente, o custo do time, as execuções de cada automação e a
  // conversa (eterna) que mantém este time — tudo em paralelo.
  const [cintosPares, custoResp, execPorAutomacao, conversasResp] =
    await Promise.all([
      Promise.all(
        agentes.map(async (a) => {
          const r = await buscarCerebro(`/agentes/${a.id}/instrumentos`);
          return [a.id, await jsonOu<Instrumento[]>(r, [])] as const;
        }),
      ),
      buscarCerebro(`/uso/resumo?time_id=${timeId}`),
      Promise.all(
        automacoes.map(async (auto) => {
          const r = await buscarCerebro(`/automacoes/${auto.id}/execucoes`);
          const execs = await jsonOu<Execucao[]>(r, []);
          return execs.map((e) => ({ ...e, automacao_nome: auto.nome }));
        }),
      ),
      buscarCerebro(
        `/organizacoes/${time.organizacao_id}/conversas-criacao`,
      ),
    ]);

  const cintos = Object.fromEntries(cintosPares);
  const custo = await jsonOu<ResumoUso | null>(custoResp, null);

  const todas: ExecucaoRecente[] = execPorAutomacao
    .flat()
    .sort((a, b) => b.criado_em.localeCompare(a.criado_em));
  const aguardando = todas.filter((e) => e.estado === "aguardando_humano").length;
  const pendenteAutomacaoId =
    todas.find((e) => e.estado === "aguardando_humano")?.automacao_id ?? null;

  const conversas = await jsonOu<ConversaCriacaoResumo[]>(conversasResp, []);
  const conversaId = conversas.find((c) => c.time_id === timeId)?.id ?? null;

  return {
    time,
    meuPapel,
    agentes,
    cintos,
    automacoes,
    recentes: todas.slice(0, 8),
    aguardando,
    pendenteAutomacaoId,
    totalExecucoes: todas.length,
    custo,
    conversaId,
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
