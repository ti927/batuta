import { notFound } from "next/navigation";

import { type Agente, type Automacao, type Execucao } from "@/lib/api";

import { AutomacaoDetalheCliente } from "./automacao-detalhe-cliente";

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function carregar(automacaoId: string): Promise<{
  automacao: Automacao;
  execucoes: Execucao[];
  agentes: Agente[];
} | null> {
  const respAuto = await fetch(`${BASE}/automacoes/${automacaoId}`, {
    cache: "no-store",
  });
  if (respAuto.status === 404) return null;
  if (!respAuto.ok) throw new Error("Falha ao carregar a automação");
  const automacao: Automacao = await respAuto.json();

  const [respExec, respAg] = await Promise.all([
    fetch(`${BASE}/automacoes/${automacaoId}/execucoes`, { cache: "no-store" }),
    fetch(`${BASE}/times/${automacao.time_id}/agentes`, { cache: "no-store" }),
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
