import { type Organizacao } from "@/lib/api";
import { buscarCerebro } from "@/lib/cerebro-servidor";

import { OrganizacoesCliente } from "./organizacoes-cliente";

// Server Component: busca a lista no cérebro a cada render. router.refresh()
// (no componente cliente) re-executa este fetch após cada mudança.
async function listar(): Promise<Organizacao[]> {
  const resposta = await buscarCerebro("/organizacoes");
  if (!resposta.ok) throw new Error("Falha ao carregar organizações");
  return resposta.json();
}

export default async function OrganizacoesPage() {
  const organizacoes = await listar();
  return <OrganizacoesCliente inicial={organizacoes} />;
}
