import { notFound } from "next/navigation";

import {
  type ChaveApiLer,
  type ModelosDisponiveis,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { ChavesCliente } from "./chaves-cliente";

async function carregar(organizacaoId: string): Promise<{
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  chaves: ChaveApiLer[];
  disponiveis: ModelosDisponiveis | null;
} | null> {
  const [respOrg, eu] = await Promise.all([
    buscarCerebro(`/organizacoes/${organizacaoId}`),
    buscarMeuAcesso(),
  ]);
  if (respOrg.status === 404) return null;
  if (!respOrg.ok) throw new Error("Falha ao carregar a organização");

  const organizacao: Organizacao = await respOrg.json();
  const meuPapel = eu?.papeis[organizacaoId] ?? null;

  // Só admin gere chaves (o cérebro devolve 403 aos demais — nem buscamos).
  let chaves: ChaveApiLer[] = [];
  let disponiveis: ModelosDisponiveis | null = null;
  if (meuPapel === "admin") {
    const [respChaves, respDisp] = await Promise.all([
      buscarCerebro(`/organizacoes/${organizacaoId}/chaves`),
      buscarCerebro(`/organizacoes/${organizacaoId}/modelos-disponiveis`),
    ]);
    if (respChaves.ok) chaves = await respChaves.json();
    if (respDisp.ok) disponiveis = await respDisp.json();
  }

  return { organizacao, meuPapel, chaves, disponiveis };
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
      disponiveis={dados.disponiveis}
    />
  );
}
