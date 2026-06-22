import { notFound } from "next/navigation";

import {
  type ChaveApiLer,
  type Credencial,
  type Organizacao,
  type PapelAcesso,
  type TipoCredencial,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { ChavesCliente } from "./chaves-cliente";

async function carregar(organizacaoId: string): Promise<{
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  chaves: ChaveApiLer[];
  credenciais: Credencial[];
  tiposCredencial: TipoCredencial[];
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
  let credenciais: Credencial[] = [];
  let tiposCredencial: TipoCredencial[] = [];
  if (meuPapel === "admin") {
    const [respChaves, respCred, respTipos] = await Promise.all([
      buscarCerebro(`/organizacoes/${organizacaoId}/chaves`),
      buscarCerebro(`/organizacoes/${organizacaoId}/credenciais`),
      buscarCerebro(`/credenciais/tipos`),
    ]);
    if (respChaves.ok) chaves = await respChaves.json();
    if (respCred.ok) credenciais = await respCred.json();
    if (respTipos.ok) tiposCredencial = await respTipos.json();
  }

  return { organizacao, meuPapel, chaves, credenciais, tiposCredencial };
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
      credenciais={dados.credenciais}
      tiposCredencial={dados.tiposCredencial}
    />
  );
}
