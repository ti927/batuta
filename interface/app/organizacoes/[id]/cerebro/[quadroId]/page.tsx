import { notFound } from "next/navigation";

import { type PapelAcesso } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { type QuadroDetalhe } from "@/lib/quadros";

import { QuadroCliente } from "./quadro-cliente";

export default async function QuadroPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string; quadroId: string }>;
  searchParams: Promise<{ importar?: string }>;
}) {
  const { id, quadroId } = await params;
  const { importar } = await searchParams;
  const [resp, eu] = await Promise.all([
    buscarCerebro(`/organizacoes/${id}/quadros/${quadroId}`),
    buscarMeuAcesso(),
  ]);
  if (resp.status === 404) notFound();
  if (!resp.ok) throw new Error("Não consegui carregar o quadro.");
  const detalhe: QuadroDetalhe = await resp.json();
  const meuPapel: PapelAcesso | null = eu?.papeis[id] ?? null;
  return (
    <QuadroCliente
      organizacaoId={id}
      detalheInicial={detalhe}
      meuPapel={meuPapel}
      abrirImportacao={importar === "1"}
    />
  );
}
