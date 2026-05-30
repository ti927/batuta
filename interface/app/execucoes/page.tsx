import { type ExecucaoNaLista } from "@/lib/api";

import { ExecucoesCliente } from "./execucoes-cliente";

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function carregar(): Promise<ExecucaoNaLista[]> {
  const resp = await fetch(`${BASE}/execucoes`, { cache: "no-store" });
  if (!resp.ok) throw new Error("Falha ao carregar execuções");
  return resp.json();
}

export default async function ExecucoesPage() {
  const execucoes = await carregar();
  return <ExecucoesCliente inicial={execucoes} />;
}
