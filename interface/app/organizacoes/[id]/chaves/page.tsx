import { notFound } from "next/navigation";

import {
  type ChaveApiLer,
  type CredencialInstrumento,
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
  credenciais: CredencialInstrumento[];
} | null> {
  const [respOrg, eu] = await Promise.all([
    buscarCerebro(`/organizacoes/${organizacaoId}`),
    buscarMeuAcesso(),
  ]);
  if (respOrg.status === 404) return null;
  if (!respOrg.ok) throw new Error("Falha ao carregar a organização");

  const organizacao: Organizacao = await respOrg.json();
  const meuPapel = eu?.papeis[organizacaoId] ?? null;

  // Só admin gere chaves e credenciais (o cérebro devolve 403 aos demais).
  let chaves: ChaveApiLer[] = [];
  let disponiveis: ModelosDisponiveis | null = null;
  let credenciais: CredencialInstrumento[] = [];
  if (meuPapel === "admin") {
    const [respChaves, respDisp, respCred] = await Promise.all([
      buscarCerebro(`/organizacoes/${organizacaoId}/chaves`),
      buscarCerebro(`/organizacoes/${organizacaoId}/modelos-disponiveis`),
      buscarCerebro(`/organizacoes/${organizacaoId}/credenciais`),
    ]);
    if (respChaves.ok) chaves = await respChaves.json();
    if (respDisp.ok) disponiveis = await respDisp.json();
    if (respCred.ok) credenciais = await respCred.json();
  }

  return { organizacao, meuPapel, chaves, disponiveis, credenciais };
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
      credenciais={dados.credenciais}
    />
  );
}
