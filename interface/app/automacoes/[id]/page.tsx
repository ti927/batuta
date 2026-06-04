import { notFound } from "next/navigation";

import { type Agente, type Automacao, type Execucao } from "@/lib/api";
import { buscarCerebro } from "@/lib/cerebro-servidor";

import { AutomacaoDetalheCliente } from "./automacao-detalhe-cliente";

async function carregar(automacaoId: string): Promise<{
  automacao: Automacao;
  execucoes: Execucao[];
  agentes: Agente[];
} | null> {
  const respAuto = await buscarCerebro(`/automacoes/${automacaoId}`);
  if (respAuto.status === 404) return null;
  if (!respAuto.ok) throw new Error("Falha ao carregar a automação");
  const automacao: Automacao = await respAuto.json();

  const [respExec, respAg] = await Promise.all([
    buscarCerebro(`/automacoes/${automacaoId}/execucoes`),
    buscarCerebro(`/times/${automacao.time_id}/agentes`),
  ]);
  if (!respExec.ok || !respAg.ok) throw new Error("Falha ao carregar execuções");

  return {
    automacao,
    execucoes: await respExec.json(),
    agentes: await respAg.json(),
  };
}

export default async function AutomacaoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <AutomacaoDetalheCliente
      automacao={dados.automacao}
      execucoes={dados.execucoes}
      agentes={dados.agentes}
    />
  );
}
