import { notFound } from "next/navigation";

import { type ConversaCriacao, type PapelAcesso } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { CriacaoCliente } from "./criacao-cliente";

async function carregar(id: string): Promise<{
  conversa: ConversaCriacao;
  meuPapel: PapelAcesso | null;
} | null> {
  const [resp, eu] = await Promise.all([
    buscarCerebro(`/conversas-criacao/${id}`),
    buscarMeuAcesso(),
  ]);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error("Falha ao carregar a conversa");
  const conversa: ConversaCriacao = await resp.json();
  return {
    conversa,
    meuPapel: eu?.papeis[conversa.organizacao_id] ?? null,
  };
}

export default async function ConversaCriacaoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <CriacaoCliente conversaInicial={dados.conversa} meuPapel={dados.meuPapel} />
  );
}
