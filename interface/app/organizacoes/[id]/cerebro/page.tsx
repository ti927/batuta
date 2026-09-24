import { notFound } from "next/navigation";

import { type Organizacao, type PapelAcesso } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { type QuadroResumo } from "@/lib/quadros";

import { CerebroCliente } from "./cerebro-cliente";

// O cérebro da organização: a lista de quadros (e, depois, a Biblioteca). Todos os
// papéis leem; criar e mudar é de operador; excluir quadro, de admin.
export default async function CerebroPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [respOrg, respQuadros, eu] = await Promise.all([
    buscarCerebro(`/organizacoes/${id}`),
    buscarCerebro(`/organizacoes/${id}/quadros`),
    buscarMeuAcesso(),
  ]);
  if (respOrg.status === 404) notFound();
  if (!respOrg.ok) throw new Error("Não consegui carregar a organização.");
  const organizacao: Organizacao = await respOrg.json();
  const quadros: QuadroResumo[] = respQuadros.ok ? await respQuadros.json() : [];
  const meuPapel: PapelAcesso | null = eu?.papeis[id] ?? null;
  return (
    <CerebroCliente
      organizacao={organizacao}
      quadros={quadros}
      meuPapel={meuPapel}
      erroAoCarregar={!respQuadros.ok}
    />
  );
}
