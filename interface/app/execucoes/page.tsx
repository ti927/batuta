import { type ExecucaoNaLista } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { ExecucoesCliente } from "./execucoes-cliente";

async function carregar(): Promise<ExecucaoNaLista[]> {
  const resp = await buscarCerebro("/execucoes");
  if (!resp.ok) throw new Error("Falha ao carregar execuções");
  return resp.json();
}

export default async function ExecucoesPage() {
  const [execucoes, eu] = await Promise.all([carregar(), buscarMeuAcesso()]);
  return <ExecucoesCliente inicial={execucoes} papeis={eu?.papeis ?? {}} />;
}
