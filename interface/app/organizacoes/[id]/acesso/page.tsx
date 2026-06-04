import { notFound } from "next/navigation";

import {
  type ConviteLer,
  type MembroLer,
  type MeuAcesso,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { buscarCerebro } from "@/lib/cerebro-servidor";

import { AcessoCliente } from "./acesso-cliente";

async function carregar(organizacaoId: string): Promise<{
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  meuId: string;
  membros: MembroLer[];
  convites: ConviteLer[];
} | null> {
  const [respOrg, respEu, respMembros] = await Promise.all([
    buscarCerebro(`/organizacoes/${organizacaoId}`),
    buscarCerebro("/eu"),
    buscarCerebro(`/organizacoes/${organizacaoId}/membros`),
  ]);
  if (respOrg.status === 404 || respMembros.status === 404) return null;
  if (!respOrg.ok || !respEu.ok || !respMembros.ok)
    throw new Error("Falha ao carregar a gestão de acesso");

  const organizacao: Organizacao = await respOrg.json();
  const eu: MeuAcesso = await respEu.json();
  const membros: MembroLer[] = await respMembros.json();
  const meuPapel = eu.papeis[organizacaoId] ?? null;

  // Só admin enxerga convites (o cérebro devolve 403 para os demais).
  let convites: ConviteLer[] = [];
  if (meuPapel === "admin") {
    const respConv = await buscarCerebro(`/organizacoes/${organizacaoId}/convites`);
    if (respConv.ok) convites = await respConv.json();
  }

  return { organizacao, meuPapel, meuId: eu.id, membros, convites };
}

export default async function AcessoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <AcessoCliente
      organizacao={dados.organizacao}
      meuPapel={dados.meuPapel}
      meuId={dados.meuId}
      membros={dados.membros}
      convites={dados.convites}
    />
  );
}
