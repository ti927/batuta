import { notFound } from "next/navigation";

import {
  type ConversaCriacao,
  type Execucao,
  type PapelAcesso,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { CriacaoCliente } from "./criacao-cliente";

async function carregar(id: string): Promise<{
  conversa: ConversaCriacao;
  meuPapel: PapelAcesso | null;
  execucoesRecentes: Execucao[];
} | null> {
  const [resp, eu] = await Promise.all([
    buscarCerebro(`/conversas-criacao/${id}`),
    buscarMeuAcesso(),
  ]);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error("Falha ao carregar a conversa");
  const conversa: ConversaCriacao = await resp.json();

  // Camada "últimas execuções" do painel de conhecimento (handoff §6.6): as
  // execuções recentes da automação do time, se já houver uma.
  let execucoesRecentes: Execucao[] = [];
  const autoId = conversa.time?.automacao?.id;
  if (autoId) {
    const r = await buscarCerebro(`/automacoes/${autoId}/execucoes`);
    if (r.ok) execucoesRecentes = ((await r.json()) as Execucao[]).slice(0, 5);
  }

  return {
    conversa,
    meuPapel: eu?.papeis[conversa.organizacao_id] ?? null,
    execucoesRecentes,
  };
}

export default async function ConversaCriacaoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const primeira = typeof sp.primeira === "string" ? sp.primeira : undefined;
  const dados = await carregar(id);
  if (!dados) notFound();
  return (
    <CriacaoCliente
      conversaInicial={dados.conversa}
      meuPapel={dados.meuPapel}
      primeiraMensagem={primeira}
      execucoesRecentes={dados.execucoesRecentes}
    />
  );
}
