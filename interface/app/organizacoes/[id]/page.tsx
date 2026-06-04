import { notFound } from "next/navigation";

import { type Organizacao, type PapelAcesso, type Time } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { TimesCliente } from "./times-cliente";

async function carregar(organizacaoId: string): Promise<{
  organizacao: Organizacao;
  times: Time[];
  meuPapel: PapelAcesso | null;
} | null> {
  const [respOrg, respTimes, eu] = await Promise.all([
    buscarCerebro(`/organizacoes/${organizacaoId}`),
    buscarCerebro(`/organizacoes/${organizacaoId}/times`),
    buscarMeuAcesso(),
  ]);
  if (respOrg.status === 404) return null;
  if (!respOrg.ok || !respTimes.ok) throw new Error("Falha ao carregar a organização");
  return {
    organizacao: await respOrg.json(),
    times: await respTimes.json(),
    meuPapel: eu?.papeis[organizacaoId] ?? null,
  };
}

export default async function OrganizacaoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <TimesCliente
      organizacao={dados.organizacao}
      inicial={dados.times}
      meuPapel={dados.meuPapel}
    />
  );
}
