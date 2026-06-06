import { type ExecucaoNaLista, type ResumoUso } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { ExecucoesCliente } from "./execucoes-cliente";

async function carregar(): Promise<ExecucaoNaLista[]> {
  const resp = await buscarCerebro("/execucoes");
  if (!resp.ok) throw new Error("Falha ao carregar execuções");
  return resp.json();
}

async function carregarUso(): Promise<ResumoUso | null> {
  const resp = await buscarCerebro("/uso/resumo");
  return resp.ok ? resp.json() : null;
}

export default async function ExecucoesPage() {
  const [execucoes, uso, eu] = await Promise.all([
    carregar(),
    carregarUso(),
    buscarMeuAcesso(),
  ]);
  return (
    <ExecucoesCliente inicial={execucoes} uso={uso} papeis={eu?.papeis ?? {}} />
  );
}
