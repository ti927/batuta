import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import {
  type Agente,
  type Automacao,
  type ExecucaoComPassos,
  type PapelAcesso,
  type Time,
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
  automacao: Automacao;
  agentes: Agente[];
  meuPapel: PapelAcesso | null;
} | null> {
  const respExec = await buscarCerebro(`/execucoes/${execId}`);
  if (respExec.status === 404) return null;
  if (!respExec.ok) throw new Error("Falha ao carregar a execução");
  const execucao: ExecucaoComPassos = await respExec.json();

  const [respAuto, respAgentes, respTime, eu] = await Promise.all([
    buscarCerebro(`/automacoes/${execucao.automacao_id}`),
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarCerebro(`/times/${timeId}`),
    buscarMeuAcesso(),
  ]);
  if (!respAuto.ok || !respTime.ok) return null;
  const automacao: Automacao = await respAuto.json();
  const time: Time = await respTime.json();
  return {
    execucao,
    automacao,
    agentes: await jsonOu<Agente[]>(respAgentes, []),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
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
        />
      </div>
    </main>
  );
}
