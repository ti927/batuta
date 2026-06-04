import { notFound } from "next/navigation";

import {
  type Agente,
  type Automacao,
  type Execucao,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { AutomacaoDetalheCliente } from "./automacao-detalhe-cliente";

async function carregar(automacaoId: string): Promise<{
  automacao: Automacao;
  execucoes: Execucao[];
  agentes: Agente[];
  meuPapel: PapelAcesso | null;
} | null> {
  const respAuto = await buscarCerebro(`/automacoes/${automacaoId}`);
  if (respAuto.status === 404) return null;
  if (!respAuto.ok) throw new Error("Falha ao carregar a automação");
  const automacao: Automacao = await respAuto.json();

  const [respExec, respAg, respTime, eu] = await Promise.all([
    buscarCerebro(`/automacoes/${automacaoId}/execucoes`),
    buscarCerebro(`/times/${automacao.time_id}/agentes`),
    buscarCerebro(`/times/${automacao.time_id}`),
    buscarMeuAcesso(),
  ]);
  if (!respExec.ok || !respAg.ok || !respTime.ok)
    throw new Error("Falha ao carregar execuções");

  const time: Time = await respTime.json();
  return {
    automacao,
    execucoes: await respExec.json(),
    agentes: await respAg.json(),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
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
      meuPapel={dados.meuPapel}
    />
  );
}
