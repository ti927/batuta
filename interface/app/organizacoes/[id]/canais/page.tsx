import { notFound } from "next/navigation";

import {
  type Canal,
  type IdentidadeCanal,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { CanaisCliente } from "./canais-cliente";

async function carregar(organizacaoId: string): Promise<{
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  canais: Canal[];
  identidadesPorCanal: Record<string, IdentidadeCanal[]>;
} | null> {
  const [respOrg, eu] = await Promise.all([
    buscarCerebro(`/organizacoes/${organizacaoId}`),
    buscarMeuAcesso(),
  ]);
  if (respOrg.status === 404) return null;
  if (!respOrg.ok) throw new Error("Falha ao carregar a organização");

  const organizacao: Organizacao = await respOrg.json();
  const meuPapel = eu?.papeis[organizacaoId] ?? null;

  // Observador+ vê os canais; o cérebro devolve 403 a quem não é membro.
  let canais: Canal[] = [];
  const respCanais = await buscarCerebro(`/organizacoes/${organizacaoId}/canais`);
  if (respCanais.ok) canais = await respCanais.json();

  // Carrega as identidades de cada canal (evita fetch no cliente).
  const identidadesPorCanal: Record<string, IdentidadeCanal[]> = {};
  await Promise.all(
    canais.map(async (c) => {
      const resp = await buscarCerebro(
        `/organizacoes/${organizacaoId}/canais/${c.id}/identidades`,
      );
      identidadesPorCanal[c.id] = resp.ok ? await resp.json() : [];
    }),
  );

  return { organizacao, meuPapel, canais, identidadesPorCanal };
}

export default async function CanaisOrgPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <CanaisCliente
      organizacao={dados.organizacao}
      meuPapel={dados.meuPapel}
      canais={dados.canais}
      identidadesPorCanal={dados.identidadesPorCanal}
    />
  );
}
