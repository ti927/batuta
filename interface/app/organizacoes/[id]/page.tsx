import { notFound } from "next/navigation";

import { type Organizacao, type Time } from "@/lib/api";

import { TimesCliente } from "./times-cliente";

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function carregar(
  organizacaoId: string,
): Promise<{ organizacao: Organizacao; times: Time[] } | null> {
  const [respOrg, respTimes] = await Promise.all([
    fetch(`${BASE}/organizacoes/${organizacaoId}`, { cache: "no-store" }),
    fetch(`${BASE}/organizacoes/${organizacaoId}/times`, { cache: "no-store" }),
  ]);
  if (respOrg.status === 404) return null;
  if (!respOrg.ok || !respTimes.ok) throw new Error("Falha ao carregar a organização");
  return { organizacao: await respOrg.json(), times: await respTimes.json() };
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
    <TimesCliente organizacao={dados.organizacao} inicial={dados.times} />
  );
}
