import { type Organizacao } from "@/lib/api";

import { OrganizacoesCliente } from "./organizacoes-cliente";

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

// Server Component: busca a lista no cérebro a cada render. router.refresh()
// (no componente cliente) re-executa este fetch após cada mudança.
async function listar(): Promise<Organizacao[]> {
  const resposta = await fetch(`${BASE}/organizacoes`, { cache: "no-store" });
  if (!resposta.ok) throw new Error("Falha ao carregar organizações");
  return resposta.json();
}

export default async function OrganizacoesPage() {
  const organizacoes = await listar();
  return <OrganizacoesCliente inicial={organizacoes} />;
}
