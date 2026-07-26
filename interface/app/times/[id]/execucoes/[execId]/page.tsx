import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import {
  type Agente,
  type Automacao,
  type ConversaCriacaoResumo,
  type ExecucaoComPassos,
  type Instrumento,
  type PapelAcesso,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { InspecaoExecucao } from "@/components/inspecao-execucao";

async function jsonOu<T>(resp: Response, padrao: T): Promise<T> {
  return resp.ok ? ((await resp.json()) as T) : padrao;
}

async function carregar(
  timeId: string,
  execId: string,
): Promise<{
  execucao: ExecucaoComPassos;
  automacao: Automacao | null;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  instrumentos: Instrumento[];
  tipos: TipoInstrumento[];
  time: Time;
  meuPapel: PapelAcesso | null;
  conversaId: string | null;
} | null> {
  const respExec = await buscarCerebro(`/execucoes/${execId}`);
  if (respExec.status === 404) return null;
  if (!respExec.ok) throw new Error("Falha ao carregar a execução");
  const execucao: ExecucaoComPassos = await respExec.json();
  // Rastro-sombra de conversa (Fatia 1b): sem automação de origem. A MESMA tela de
  // detalhe renderiza o passo a passo dos turnos — só não há automação a carregar.
  const ehConversa = execucao.automacao_id == null;

  const [respAgentes, respTime, respInst, respTipos, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/instrumentos`),
    buscarCerebro(`/instrumentos/tipos`),
    buscarMeuAcesso(),
  ]);
  if (!respTime.ok) return null;
  const time: Time = await respTime.json();

  let automacao: Automacao | null = null;
  if (!ehConversa) {
    const respAuto = await buscarCerebro(`/automacoes/${execucao.automacao_id}`);
    if (!respAuto.ok) return null;
    automacao = await respAuto.json();
  }
  const agentes = await jsonOu<Agente[]>(respAgentes, []);

  // Cinto de cada agente e a conversa (eterna) — para o editor de agente aberto
  // pelo lápis de um passo (gerir cinto, "Ajustar com a IA"), sem sair da execução.
  const [cintosPares, conversasResp] = await Promise.all([
    Promise.all(
      agentes.map(async (a) => {
        const r = await buscarCerebro(`/agentes/${a.id}/instrumentos`);
        return [a.id, await jsonOu<Instrumento[]>(r, [])] as const;
      }),
    ),
    buscarCerebro(`/organizacoes/${time.organizacao_id}/conversas-criacao`),
  ]);
  const conversas = await jsonOu<ConversaCriacaoResumo[]>(conversasResp, []);

  return {
    execucao,
    automacao,
    agentes,
    cintos: Object.fromEntries(cintosPares),
    instrumentos: await jsonOu<Instrumento[]>(respInst, []),
    tipos: await jsonOu<TipoInstrumento[]>(respTipos, []),
    time,
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
    conversaId: conversas.find((c) => c.time_id === timeId)?.id ?? null,
  };
}

export default async function ExecucaoDetalhePage({
  params,
}: {
  params: Promise<{ id: string; execId: string }>;
}) {
  const { id, execId } = await params;
  const dados = await carregar(id, execId);
  if (!dados) notFound();
  return (
    <main className="mx-auto w-full max-w-[1000px] px-5 py-8 sm:px-8">
      <Link
        href={`/times/${id}/execucoes`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Todas as execuções
      </Link>
      <div className="mt-3">
        <InspecaoExecucao
          execucaoId={execId}
          automacao={dados.automacao}
          agentes={dados.agentes}
          meuPapel={dados.meuPapel}
          inicial={dados.execucao}
          cintos={dados.cintos}
          instrumentosTime={dados.instrumentos}
          tipos={dados.tipos}
          time={dados.time}
          conversaId={dados.conversaId}
        />
      </div>
    </main>
  );
}
