import { notFound } from "next/navigation";

import {
  type ChaveApiLer,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { ChavesCliente } from "./chaves-cliente";

async function carregar(organizacaoId: string): Promise<{
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  chaves: ChaveApiLer[];
} | null> {
  const [respOrg, eu] = await Promise.all([
    buscarCerebro(`/organizacoes/${organizacaoId}`),
    buscarMeuAcesso(),
  ]);
  if (respOrg.status === 404) return null;
  if (!respOrg.ok) throw new Error("Falha ao carregar a organização");

  const organizacao: Organizacao = await respOrg.json();
  const meuPapel = eu?.papeis[organizacaoId] ?? null;

  // Só admin gere as chaves (o cérebro devolve 403 aos demais).
  let chaves: ChaveApiLer[] = [];
  if (meuPapel === "admin") {
    const respChaves = await buscarCerebro(`/organizacoes/${organizacaoId}/chaves`);
    if (respChaves.ok) chaves = await respChaves.json();
  }

  return { organizacao, meuPapel, chaves };
}

export default async function ChavesOrgPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <ChavesCliente
      organizacao={dados.organizacao}
      meuPapel={dados.meuPapel}
      chaves={dados.chaves}
    />
  );
}
